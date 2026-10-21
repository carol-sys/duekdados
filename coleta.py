"""Coleta de dados públicos de perfis do Kwai.

1) Selenium abre o perfil e rola a grade para pegar os IDs dos vídeos.
2) `requests` abre a página de cada vídeo (4 ao mesmo tempo) e extrai
   curtidas, comentários, legenda, data/hora e duração.
"""
from __future__ import annotations

import html as html_lib
import os
import random
import re
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Callable

import requests

FUSO_BR = timezone(timedelta(hours=-3))
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Referer": "https://www.kwai.com/",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}
PAGINA_GENERICA = "Make Everyone Shine"   # o Kwai devolve isso quando nega a página

Aviso = Callable[[str, float | None], None]


def _sem_aviso(msg: str, progresso: float | None = None) -> None:
    pass


# ---------------------------------------------------------------- utilidades
def normalizar_perfil(texto: str) -> tuple[str | None, str | None]:
    """Aceita link, '@conta' ou 'conta' e devolve (url do perfil, conta)."""
    texto = (texto or "").strip().strip('"').strip("'")
    texto = re.sub(r"\$\d+$", "", texto)
    m = re.search(r"@([\w.\-]+)", texto)
    if m:
        conta = m.group(1)
    elif re.fullmatch(r"[\w.\-]+", texto):
        conta = texto
    else:
        return None, None
    conta = conta.rstrip(".")
    return f"https://www.kwai.com/@{conta}", conta


def contagem_para_int(texto) -> int | None:
    """'208' → 208 | '2.8K' → 2800 | '1,2 mil' → 1200 | '3.4M' → 3400000."""
    if texto is None:
        return None
    t = str(texto).strip().lower().replace(" ", "").replace(" ", "")
    m = re.fullmatch(r"(\d+(?:[.,]\d+)*)(k|m|b|mil|mi|bi)?", t)
    if not m:
        return None
    numero, sufixo = m.groups()
    if sufixo:
        mult = {"k": 1e3, "mil": 1e3, "m": 1e6, "mi": 1e6, "b": 1e9, "bi": 1e9}[sufixo]
        return int(round(float(numero.replace(",", ".")) * mult))
    return int(numero.replace(".", "").replace(",", ""))


def _meta(html: str, nome: str) -> str | None:
    padroes = [
        r'<meta[^>]*?(?:name|property)=["\']' + re.escape(nome) + r'["\'][^>]*?content=["\']([^"\']*)["\']',
        r'<meta[^>]*?content=["\']([^"\']*)["\'][^>]*?(?:name|property)=["\']' + re.escape(nome) + r'["\']',
    ]
    for p in padroes:
        m = re.search(p, html, re.IGNORECASE | re.DOTALL)
        if m:
            return html_lib.unescape(m.group(1))
    return None


# ------------------------------------------------------------ navegador
def montar_driver():
    """Chrome/Chromium headless. Funciona no Colab, no PC e no Streamlit Cloud."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service

    opcoes = Options()
    for arg in ("--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
                "--window-size=430,900", f"--user-data-dir=/tmp/chrome-perfil-{random.randint(1, 999999)}",
                "user-agent=Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"):
        opcoes.add_argument(arg)
    for caminho in ("/usr/bin/chromium", "/usr/bin/chromium-browser",
                    "/usr/bin/google-chrome-stable", "/usr/bin/google-chrome"):
        if os.path.exists(caminho):
            opcoes.binary_location = caminho
            break
    driver_sistema = shutil.which("chromedriver") or next(
        (p for p in ("/usr/bin/chromedriver", "/usr/lib/chromium/chromedriver") if os.path.exists(p)), None)
    if driver_sistema:
        return webdriver.Chrome(service=Service(driver_sistema), options=opcoes)
    return webdriver.Chrome(options=opcoes)   # Selenium Manager baixa o driver sozinho


ROTULOS_PERFIL = {
    "seguidores": ("seguidores", "seguidor", "followers", "follower", "fãs", "fas", "fans"),
    "seguindo": ("seguindo", "following"),
    "curtidas_total": ("curtidas", "likes", "like"),
}
_NUM = r"(\d+(?:[.,]\d+)*\s*(?:k|m|b|mil|mi|bi)?)"


def extrair_info_perfil(texto: str, html: str) -> dict:
    info: dict = {}
    linhas = [l.strip().lower() for l in texto.split("\n") if l.strip()][:120]
    for i, linha in enumerate(linhas):
        for chave, nomes in ROTULOS_PERFIL.items():
            if chave in info:
                continue
            for nome in nomes:
                n = re.escape(nome)
                m = re.fullmatch(_NUM + r"\s*" + n, linha) or re.fullmatch(n + r"\s*:?\s*" + _NUM, linha)
                valor = m.group(1) if m else None
                if valor is None and linha == nome:
                    for vizinha in (linhas[i - 1] if i else "", linhas[i + 1] if i + 1 < len(linhas) else ""):
                        if re.fullmatch(_NUM, vizinha):
                            valor = vizinha
                            break
                if valor is not None and contagem_para_int(valor) is not None:
                    info[chave] = contagem_para_int(valor)
                    break
    if "seguidores" not in info:
        for p in (r'"?fans?_count"?\s*:\s*"?(\d+)', r'"?fansCount"?\s*:\s*"?(\d+)',
                  r'"?follower_?[cC]ount"?\s*:\s*"?(\d+)', r'"?fan"?\s*:\s*"?(\d+)'):
            m = re.search(p, html)
            if m:
                info["seguidores"] = int(m.group(1))
                break
    m = re.search(r'<title>\s*([^<(]+?)\s*\(@', html)
    if m:
        info["nome"] = html_lib.unescape(m.group(1)).strip()
    return info


def _rolar(driver) -> None:
    altura = driver.execute_script("return window.innerHeight;") or 900
    for _ in range(6):
        driver.execute_script(f"window.scrollBy(0, {altura // 2});")
        driver.execute_script("window.dispatchEvent(new Event('scroll'));")
        time.sleep(0.5)
    time.sleep(3)


def ler_grade_do_perfil(url_perfil: str, conta: str, max_videos: int,
                        avisar: Aviso = _sem_aviso) -> tuple[list[str], dict]:
    avisar("Abrindo o navegador…", 0.0)
    driver = montar_driver()
    ids: list[str] = []
    vistos: set[str] = set()
    info: dict = {}
    sem_novidade = 0
    try:
        avisar(f"Carregando o perfil @{conta}…", 0.02)
        driver.get(url_perfil)
        time.sleep(3)
        try:
            texto = driver.execute_script("return document.body.innerText;") or ""
            info.update(extrair_info_perfil(texto, driver.page_source or ""))
        except Exception:
            pass

        for _ in range(100):
            hrefs = driver.execute_script(
                "return Array.from(document.querySelectorAll('a[href*=\"/video/\"]'))"
                ".map(a => a.getAttribute('href'));"
            ) or []
            ids_dom = re.findall(r"/video/(\d{8,})", " ".join(h for h in hrefs if h))
            html = driver.page_source
            ids_html = re.findall(r"/video/(\d{8,})", html)
            ids_html += re.findall(r'"photoId"\s*:\s*"?(\d{8,})"?', html)

            antes = len(ids)
            for vid in ids_dom + ids_html:
                if vid not in vistos and len(ids) < max_videos:
                    vistos.add(vid)
                    ids.append(vid)
            avisar(f"Rolando a grade de @{conta}: {len(ids)}/{max_videos} vídeos", 0.5 * len(ids) / max_videos)
            if len(ids) >= max_videos:
                break
            sem_novidade = sem_novidade + 1 if len(ids) == antes else 0
            if sem_novidade >= 8:
                break
            _rolar(driver)
    finally:
        driver.quit()
    return ids[:max_videos], info


# ------------------------------------------------- página de cada vídeo
def _duracao_iso(html: str) -> int | None:
    m = re.search(r'"duration"\s*:\s*"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?"', html)
    if not m or not any(m.groups()):
        return None
    h, mi, se = (float(x) if x else 0 for x in m.groups())
    total = round(h * 3600 + mi * 60 + se)
    return total if total > 0 else None


def _duracao_perto_do_id(html: str, video_id: str) -> int | None:
    padrao = re.compile(r'\b(?:duration|videoDuration|video_duration|photoDuration)"?\s*:\s*"?(\d+(?:\.\d+)?)')
    melhor = None
    for m_id in re.finditer(re.escape(video_id), html):
        ini = max(0, m_id.start() - 1500)
        janela = html[ini:m_id.end() + 1500]
        pos = m_id.start() - ini
        for m in padrao.finditer(janela):
            d = abs(m.start() - pos)
            if melhor is None or d < melhor[0]:
                melhor = (d, float(m.group(1)))
    if melhor is None:
        return None
    v = melhor[1] / 1000 if melhor[1] > 3600 else melhor[1]
    return round(v) if 1 <= v <= 3600 else None


def _data_publicacao(html: str, video_id: str) -> tuple[str, int | None, str]:
    """Data e hora da publicação, procuradas perto do ID do vídeo no HTML.

    Não usa mais a data que aparece no link do .mp4: esse link é gerado na hora
    pelo servidor e traz a data do dia da coleta, não a da publicação.
    """
    candidatos = []
    p_hora = re.compile(r'\b(?:time|uploadDate)"?\s*:\s*"(\d{4}-\d{2}-\d{2})[ T](\d{2}):\d{2}:\d{2}')
    p_ts = re.compile(r'\b(?:timestamp|createTime|create_time|publishTime)"?\s*:\s*"?(\d{10,13})\b')
    for m_id in re.finditer(re.escape(video_id), html):
        ini = max(0, m_id.start() - 800)
        janela = html[ini:m_id.end() + 800]
        pos = m_id.start() - ini
        for m in p_ts.finditer(janela):
            v = int(m.group(1))
            v = v / 1000 if v > 10 ** 12 else v
            try:
                dt = datetime.fromtimestamp(v, tz=FUSO_BR)
            except (ValueError, OSError, OverflowError):
                continue
            if 2015 <= dt.year <= 2100:
                candidatos.append((abs(m.start() - pos) - 0.5, dt.strftime("%Y-%m-%d"), dt.hour, "timestamp"))
        for m in p_hora.finditer(janela):
            candidatos.append((abs(m.start() - pos), m.group(1), int(m.group(2)), "campo de data"))
    if candidatos:
        _, data, hora, fonte = min(candidatos, key=lambda c: c[0])
        return data, hora, fonte
    return "", None, ""


def _legenda(html: str) -> tuple[str, bool]:
    """Devolve (legenda, é_legenda_própria). Tira o prefixo automático do Kwai
    ('53 Curtidas, 7 Comentários. Kwai video from X(@x): "...")."""
    for bruto in (_meta(html, "og:description"), _meta(html, "description")):
        texto = (bruto or "").strip()
        if not texto or texto == PAGINA_GENERICA:
            continue
        m = re.search(r'Kwai video from [^:]*?:\s*["“](.*)["”]\s*$', texto, re.DOTALL)
        if m:
            texto = m.group(1).strip()
        if re.search(r"\d+\s*(?:Curtidas|Like\(s\))", texto, re.IGNORECASE) and "Kwai video from" in texto:
            continue
        if texto:
            return texto, True
    return "", False


PADROES_CAMPOS = {
    "curtidas": [r'"?like_count"?\s*:\s*(\d+)', r'"?likeCount"?\s*:\s*(\d+)', r'"?realLikeCount"?\s*:\s*(\d+)'],
    "comentarios": [r'"?comment_count"?\s*:\s*(\d+)', r'"?commentCount"?\s*:\s*(\d+)'],
}


def metricas_da_pagina(link: str, video_id: str) -> dict:
    html = requests.get(link, headers=HEADERS, timeout=25).text
    generica = (_meta(html, "og:description") or "").strip() == PAGINA_GENERICA
    legenda, propria = _legenda(html)
    out = {"curtidas": None, "comentarios": None, "legenda": legenda,
           "legenda_propria": propria, "pagina_generica": generica}

    desc = _meta(html, "description") or ""
    padroes_lc = [
        r'(\d[\d.,]*\s*[KkMm]?)\s*Like\(s\).*?(\d[\d.,]*\s*[KkMm]?)\s*Comment\(s\)',
        r'(\d[\d.,]*\s*[KkMm]?)\s*Curtida\(s\).*?(\d[\d.,]*\s*[KkMm]?)\s*Coment[aá]rio\(s\)',
        r'(\d[\d.,]*\s*[KkMm]?)\s*curtidas?.*?(\d[\d.,]*\s*[KkMm]?)\s*coment[aá]rios?',
    ]
    for fonte in (desc, html):
        for p in padroes_lc:
            m = re.search(p, fonte, re.IGNORECASE)
            if m:
                out["curtidas"] = contagem_para_int(m.group(1))
                out["comentarios"] = contagem_para_int(m.group(2))
                break
        if out["curtidas"] is not None:
            break
    for campo, padroes in PADROES_CAMPOS.items():
        if out.get(campo) is not None:
            continue
        for p in padroes:
            m = re.search(p, html)
            if m:
                out[campo] = int(m.group(1))
                break

    out["data_publicacao"], out["hora_publicacao"], out["fonte_data"] = _data_publicacao(html, video_id)
    out["duracao_segundos"] = _duracao_iso(html) or _duracao_perto_do_id(html, video_id)
    return out


def _uma_pagina(conta: str, pos: int, vid: str, tentativas: int = 3) -> dict:
    link = f"https://www.kwai.com/@{conta}/video/{vid}"
    m: dict = {}
    for t in range(tentativas):
        try:
            m = metricas_da_pagina(link, vid)
            if not m.get("pagina_generica") and m.get("curtidas") is not None:
                break
        except Exception as e:   # rede, timeout…
            m = {"erro": str(e)}
        time.sleep(1.5 * (t + 1) + random.random())   # espera e tenta de novo
    return {"conta": conta, "posicao": pos, "id_video": vid, "link": link, **m}


def coletar_perfil(perfil: str, max_videos: int = 300, avisar: Aviso = _sem_aviso) -> tuple[list[dict], dict]:
    """Coleta um perfil inteiro. Devolve (linhas brutas, info do perfil)."""
    url, conta = normalizar_perfil(perfil)
    if not conta:
        raise ValueError(f"Link inválido: {perfil!r}. Use algo como https://www.kwai.com/@Embelleze")
    t0 = time.time()
    ids, info = ler_grade_do_perfil(url, conta, max_videos, avisar)
    if not ids:
        raise RuntimeError(f"Nenhum vídeo encontrado em @{conta}. O perfil existe e é público?")
    linhas = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        futuros = [ex.submit(_uma_pagina, conta, p, v) for p, v in enumerate(ids, 1)]
        for i, fut in enumerate(as_completed(futuros), 1):
            linhas.append(fut.result())
            if i % 5 == 0 or i == len(ids):
                avisar(f"Lendo vídeos de @{conta}: {i}/{len(ids)}", 0.5 + 0.5 * i / len(ids))
    info.update({"conta": conta, "url": url, "coletado_em": datetime.now(FUSO_BR).strftime("%Y-%m-%d %H:%M"),
                 "segundos": round(time.time() - t0)})
    for l in linhas:
        l["seguidores_perfil"] = info.get("seguidores")
    return sorted(linhas, key=lambda l: l["posicao"]), info
