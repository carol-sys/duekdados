"""Kwai Insights — app Streamlit.

Rodar no computador:  streamlit run app.py
"""
from __future__ import annotations

import base64
import html
import re
from datetime import datetime
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

import config as C

try:   # estrutura com pastas (kwai/coleta.py)
    from kwai import analise as A
    from kwai.coleta import FUSO_BR, coletar_perfil, normalizar_perfil
except ImportError:   # todos os arquivos soltos na raiz do repositório
    import analise as A
    from coleta import FUSO_BR, coletar_perfil, normalizar_perfil

RAIZ = Path(__file__).parent
st.set_page_config(page_title=C.NOME_APP, page_icon="📊", layout="wide", initial_sidebar_state="expanded")

DEGRADE = f"linear-gradient(100deg, #FF8E0D 0%, {C.LARANJA_VITORIA} 45%, {C.ROSA_VITORIA} 100%)"


# ================================================================ estilo
def _logo_html(item: dict, altura: int = 46) -> str:
    for ext, mime in ((".png", "image/png"), (".jpg", "image/jpeg"), (".jpeg", "image/jpeg"), (".svg", "image/svg+xml")):
        for p in (RAIZ / "assets" / f"{item['arquivo']}{ext}", RAIZ / f"{item['arquivo']}{ext}"):
            if p.exists():
                b64 = base64.b64encode(p.read_bytes()).decode()
                return f'<img src="data:{mime};base64,{b64}" alt="{item["nome"]}" style="height:{altura}px">'
    return f'<span class="logo-texto">{item["nome"]}</span>'


_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600&family=Inter:wght@400;500;600&display=swap');
:root {{
  --azul: {C.AZUL_DUE}; --azul-m: {C.AZUL_DUE_MEDIO}; --azul-c: {C.AZUL_DUE_CLARO};
  --laranja: {C.LARANJA_VITORIA}; --rosa: {C.ROSA_VITORIA}; --grafite: {C.GRAFITE};
  --cinza: {C.CINZA_DUE}; --fundo: {C.FUNDO}; --linha: #E3E7EF; --degrade: {DEGRADE};
}}
html, body, .stApp, .stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea, .stApp button {{
  font-family: 'Inter', system-ui, sans-serif;
}}
.stApp {{ background: var(--fundo); color: var(--grafite); }}
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .titulo-card, .valor-grande, .perfil .nome {{
  font-family: 'Outfit', 'Inter', sans-serif; color: var(--grafite); letter-spacing: -0.01em;
}}
header[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stAppDeployButton"], #MainMenu, footer {{ display: none !important; }}
.block-container {{ padding: 2.2rem 2.4rem 3rem; max-width: 1380px; }}

/* ---------- barra lateral (azul DUE) ---------- */
section[data-testid="stSidebar"] {{ background: var(--azul); border-right: none; }}
section[data-testid="stSidebar"] > div {{ background: var(--azul); }}
section[data-testid="stSidebar"] * {{ color: #FFFFFF; }}
section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] svg {{ fill: #fff; }}
.marca {{ background: #fff; border-radius: 20px; padding: 16px 14px; display: flex; flex-direction: column;
          align-items: center; gap: 10px; margin: 4px 0 26px; }}
.marca img {{ width: 78%; height: auto !important; object-fit: contain; }}
.marca .sep {{ width: 60%; height: 1px; background: var(--linha); }}
.rotulo-lateral {{ font-size: .82rem; opacity: .72; margin: 18px 6px 6px; }}
section[data-testid="stSidebar"] [data-testid="stRadioGroup"], section[data-testid="stSidebar"] [role="radiogroup"] {{ gap: 4px; width: 100%; align-items: stretch; }}
section[data-testid="stSidebar"] [data-testid="stElementContainer"]:has(.stRadio),
section[data-testid="stSidebar"] .stRadio, section[data-testid="stSidebar"] .stRadio > div,
section[data-testid="stSidebar"] [data-testid="stRadioGroup"] > div {{ width: 100% !important; }}
section[data-testid="stSidebar"] [data-testid="stRadioGroup"] {{ display: flex; flex-direction: column; }}
section[data-testid="stSidebar"] [data-testid="stRadioOption"] {{ display: flex !important; align-self: stretch; }}
section[data-testid="stSidebar"] [data-testid="stRadioOption"] > div {{ flex: 1; }}
section[data-testid="stSidebar"] [data-testid="stRadioOption"] {{
  width: 100%; box-sizing: border-box; padding: 12px 20px; border-radius: 999px; margin: 0; cursor: pointer;
  transition: background .15s;
}}
section[data-testid="stSidebar"] [data-testid="stRadioOption"] > div > div:first-child:not([data-testid="stMarkdownContainer"]) {{ display: none; }}
section[data-testid="stSidebar"] [data-testid="stRadioOption"]:hover {{ background: rgba(255,255,255,.10); }}
section[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] {{ background: #FFFFFF; }}
section[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] p {{ color: var(--azul) !important; font-weight: 600; }}
section[data-testid="stSidebar"] [data-testid="stRadioOption"] p {{ font-size: 1rem; }}
section[data-testid="stSidebar"] .stButton button {{
  background: transparent; border: 1px solid rgba(255,255,255,.45); border-radius: 999px;
}}
section[data-testid="stSidebar"] .stButton button:hover {{ background: rgba(255,255,255,.12); border-color: #fff; }}
section[data-testid="stSidebar"] hr {{ border-color: rgba(255,255,255,.18); }}
.assinatura {{ margin-top: 28px; padding: 14px 6px 0; border-top: 1px solid rgba(255,255,255,.18);
               font-size: .85rem; line-height: 1.5; }}
.assinatura span {{ opacity: .7; }}

/* ---------- cabeçalho da página ---------- */
.cab h1 {{ font-size: 2rem; font-weight: 500; margin: 0; padding: 0; }}
.cab .trilha {{ color: var(--cinza); font-size: .92rem; margin-top: 4px; }}
.cab .trilha b {{ color: var(--grafite); font-weight: 500; }}

/* ---------- cartões ---------- */
[class*="st-key-card"] {{ background: #FFFFFF; border-radius: 26px; padding: 26px 28px; border: none; }}
[class*="st-key-card"] [data-testid="stVerticalBlockBorderWrapper"] {{ border: none; }}
.titulo-card {{ font-size: 1.35rem; font-weight: 500; margin: 0 0 2px; }}
.sub-card {{ color: var(--cinza); font-size: .9rem; margin-bottom: 14px; }}
.ladrilhos {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-top: 14px; }}
.ladrilho {{ background: #F1F3F8; border-radius: 18px; padding: 16px 18px; }}
.ladrilho .r {{ color: var(--cinza); font-size: .86rem; }}
.ladrilho .v {{ font-weight: 600; font-size: 1.02rem; margin-top: 4px; }}
.valor-grande {{ font-size: 3.2rem; font-weight: 400; line-height: 1; }}
.valor-grande small {{ font-family: 'Inter'; font-size: 1.05rem; color: var(--grafite); margin-left: 8px; }}
.lista {{ display: grid; grid-template-columns: auto 1fr; gap: 12px 22px; margin-top: 22px; font-size: .95rem; }}
.lista dt {{ color: var(--cinza); }} .lista dd {{ margin: 0; font-weight: 500; }}
.frase {{ margin: 6px 0; line-height: 1.55; }}

/* ---------- cartão do perfil ---------- */
.perfil {{ text-align: center; }}
.avatar {{ width: 92px; height: 92px; border-radius: 50%; margin: 4px auto 14px; background: var(--degrade);
           display: flex; align-items: center; justify-content: center; color: #fff;
           font-size: 2.4rem; font-weight: 500; box-shadow: 0 0 0 6px #FDEBDD; font-family: 'Outfit', 'Inter', sans-serif; }}
.avatar.b {{ background: linear-gradient(135deg, {C.AZUL_DUE_MEDIO}, #7D9DCE); box-shadow: 0 0 0 6px var(--azul-c); }}
.perfil .nome {{ font-size: 1.4rem; font-weight: 500; }}
.perfil .handle {{ color: var(--cinza); margin: 2px 0 12px; }}
.chips {{ display: flex; gap: 6px; justify-content: center; flex-wrap: wrap; }}
.chip {{ border-radius: 999px; padding: 3px 12px; font-size: .82rem; font-weight: 500; }}
.chip.azul {{ background: var(--azul-c); color: var(--azul); }}
.chip.rosa {{ background: #FDE6EF; color: #B5245C; }}
.chip.laranja {{ background: #FEEBDD; color: #B44A05; }}
.perfil .lista {{ text-align: left; border-top: 1px solid var(--linha); padding-top: 18px; }}
.botao-link {{ display: block; margin-top: 22px; padding: 11px 0; border-radius: 999px; background: var(--azul);
               color: #fff !important; text-decoration: none !important; font-weight: 500; text-align: center; }}
.botao-link:hover {{ background: var(--azul-m); }}
.nota {{ display: flex; gap: 10px; font-size: .88rem; color: var(--grafite); margin: 8px 0; line-height: 1.45; }}
.nota .p {{ width: 8px; height: 8px; border-radius: 50%; background: var(--azul-m); margin-top: 6px; flex: none; }}

/* ---------- abas como pílulas ---------- */
.stTabs [role="tablist"] {{ gap: 8px; border: none !important; box-shadow: none; flex-wrap: wrap; }}
.stTabs [role="tablist"]::after, .stTabs [role="tablist"]::before {{ display: none; }}
.stTabs .react-aria-SelectionIndicator, .stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{ display: none !important; }}
.stTabs [role="tab"] {{ background: #FFFFFF; border-radius: 999px; padding: 9px 22px; height: auto; border: none; }}
.stTabs [role="tab"] p {{ font-size: .95rem; color: var(--grafite) !important; }}
.stTabs [role="tab"]:hover {{ background: #F7F8FC; }}
.stTabs [role="tab"][aria-selected="true"] {{ background: var(--azul); }}
.stTabs [role="tab"][aria-selected="true"] p {{ color: #fff !important; font-weight: 500; }}
.stTabs [role="tabpanel"] {{ padding-top: 16px; }}
/* ---------- botões e campos ---------- */
.stButton button, .stDownloadButton button {{ border-radius: 999px; padding: 8px 22px; font-weight: 500; }}
.stButton button[kind="primary"], .stDownloadButton button[kind="primary"] {{
  background: var(--degrade); border: none; color: #fff;
}}
.stButton button[kind="primary"]:hover, .stDownloadButton button[kind="primary"]:hover {{ filter: brightness(1.05); color: #fff; }}
.stButton button[kind="primary"]:disabled {{ opacity: .45; }}
[data-testid="stTextInputRootElement"], .stTextInput [data-baseweb="input"] {{
  border-radius: 999px !important; background: #fff !important; border: 1px solid var(--linha) !important; overflow: hidden;
}}
[data-testid="stTextInputRootElement"] input {{ background: #fff !important; padding: 12px 20px !important; }}
.stTextArea [data-testid="stTextAreaRootElement"], .stTextArea [data-baseweb="textarea"] {{
  border-radius: 18px !important; background: #F6F7FB !important; border: 1px solid var(--linha) !important;
}}
.stTextArea textarea {{ background: transparent !important; }}
[data-testid="stDataFrame"] {{ border-radius: 14px; overflow: hidden; }}
.placar {{ width: 100%; border-collapse: collapse; font-size: .93rem; border: none !important; }}
.placar th, .placar td {{ border-left: none !important; border-right: none !important; border-top: none !important; background: transparent !important; }}
.placar th {{ text-align: left; color: var(--cinza); font-weight: 400; padding: 8px 6px; border-bottom: 1px solid var(--linha); }}
.placar td {{ padding: 10px 6px; border-bottom: 1px solid #F1F3F8; }}
.placar tr:last-child td {{ border-bottom: none; }}
.placar td:first-child {{ color: var(--grafite); }}
.pt {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 8px; background: transparent; }}
.pt.a {{ background: {C.COR_A}; }} .pt.b {{ background: {C.COR_B}; }}
.placar-total {{ display: flex; gap: 22px; margin: 0 0 10px; font-size: .95rem; }}
.logo-texto {{ font-family: 'Outfit'; font-weight: 600; font-size: 1.2rem; color: var(--grafite); }}
</style>
"""
# Linhas em branco e comentários quebram o bloco HTML do markdown: remove antes de injetar.
_CSS = re.sub(r"/\*.*?\*/", "", _CSS)
st.markdown("\n".join(l for l in _CSS.splitlines() if l.strip()), unsafe_allow_html=True)


def _tema_graficos():
    return {"config": {
        "background": "transparent", "font": "Inter",
        "view": {"stroke": None},
        "axis": {"labelColor": C.CINZA_DUE, "titleColor": C.CINZA_DUE, "titleFontWeight": 400, "labelFontSize": 11,
                 "gridColor": "#EDF0F5", "domain": False, "ticks": False},
        "title": {"font": "Outfit", "fontSize": 15, "fontWeight": 500, "color": C.GRAFITE, "anchor": "start"},
        "legend": {"labelColor": C.GRAFITE, "orient": "top"},
        "range": {"category": [C.COR_A, C.COR_B, C.ROSA_VITORIA, "#7D9DCE"]},
    }}


try:   # Altair 5.5+
    alt.theme.register("kwai", enable=True)(lambda: alt.theme.ThemeConfig(_tema_graficos()))
except AttributeError:   # Altair mais antigo
    alt.themes.register("kwai", _tema_graficos)
    alt.themes.enable("kwai")


# ============================================================ formatação
def fmt(n, casas: int = 0) -> str:
    if n is None or (isinstance(n, float) and np.isnan(n)):
        return "–"
    return f"{n:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(x, sinal: bool = True) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "–"
    return (f"{x * 100:+.0f}%" if sinal else f"{x * 100:.0f}%").replace(".", ",")


def data_br(d) -> str:
    return "–" if d is None or pd.isna(d) else f"{d:%d/%m/%Y}"


def data_curta(d) -> str:
    return "–" if d is None or pd.isna(d) else f"{d:%d/%m/%y}"


def esc(s) -> str:
    return html.escape(str(s))


def cabecalho(pagina: str) -> None:
    st.markdown(f"<div class='cab'><h1>{pagina}</h1>"
                f"<div class='trilha'>{C.NOME_APP} / <b>{pagina}</b></div></div>", unsafe_allow_html=True)


def titulo(texto: str, sub: str | None = None) -> None:
    st.markdown(f"<div class='titulo-card'>{texto}</div>" + (f"<div class='sub-card'>{sub}</div>" if sub else
                "<div style='height:10px'></div>"), unsafe_allow_html=True)


# ================================================================ coleta
def obter(perfil: str, max_videos: int, forcar: bool = False) -> tuple[pd.DataFrame, dict] | None:
    """Coleta (ou reaproveita da memória da sessão) e trata um perfil."""
    _, conta = normalizar_perfil(perfil)
    if not conta:
        st.error(f"Não reconheci o perfil {perfil}. Cole um link como https://www.kwai.com/@Embelleze")
        return None
    cache = st.session_state.setdefault("coletas", {})
    chave = (conta.lower(), max_videos)
    if chave in cache and not forcar:
        return cache[chave]
    barra = st.progress(0.0, text=f"Preparando @{conta}…")
    try:
        linhas, info = coletar_perfil(perfil, max_videos,
                                      lambda m, p=None: barra.progress(min(1.0, p or 0.0), text=m))
    except Exception as e:
        barra.empty()
        st.error(f"Não consegui coletar @{conta}: {e}")
        return None
    barra.empty()
    df = A.tratar(linhas)
    cache[chave] = (df, info)
    return df, info


# ============================================================== gráficos
def grafico_linha_tempo(df: pd.DataFrame, cores: dict) -> alt.Chart:
    v = df[df["valido"] & df["data_ok"]].sort_values("data").copy()
    v["mediana_movel"] = v.groupby("conta")["interacoes"].transform(lambda s: s.rolling(7, min_periods=1).median())
    v["leg_curta"] = v["legenda"].str.slice(0, 80)
    escala = alt.Scale(domain=list(cores), range=list(cores.values()))
    base = alt.Chart(v).encode(x=alt.X("data:T", title=None, axis=alt.Axis(format="%d/%m/%y")))
    pontos = base.mark_circle(size=38, opacity=.35).encode(
        y=alt.Y("interacoes:Q", title="interações (escala log)", scale=alt.Scale(type="symlog")),
        color=alt.Color("conta:N", scale=escala, title=None,
                        legend=alt.Legend() if len(cores) > 1 else None),
        tooltip=[alt.Tooltip("conta:N"), alt.Tooltip("data:T", format="%d/%m/%Y"),
                 alt.Tooltip("interacoes:Q", format=",.0f"), alt.Tooltip("leg_curta:N", title="legenda")],
        href="link:N")
    linha = base.mark_line(strokeWidth=2.6, interpolate="monotone").encode(
        y="mediana_movel:Q", color=alt.Color("conta:N", scale=escala, legend=None))
    return (pontos + linha).properties(height=300)


def grafico_grupo(g: pd.DataFrame, col: str, ordem, cores: dict, titulo_: str) -> alt.Chart:
    escala = alt.Scale(domain=list(cores), range=list(cores.values()))
    multi = g["conta"].nunique() > 1
    enc = dict(
        x=alt.X(f"{col}:N", sort=ordem, title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("indice:Q", title="índice (1 = vídeo típico)"),
        color=alt.Color("conta:N", scale=escala, legend=None if not multi else alt.Legend(title=None)),
        tooltip=[alt.Tooltip("conta:N"), alt.Tooltip(f"{col}:N"), alt.Tooltip("videos:Q", title="vídeos"),
                 alt.Tooltip("indice:Q", format=".2f", title="índice"),
                 alt.Tooltip("interacoes:Q", format=",.0f", title="interações (mediana)")])
    if multi:
        enc["xOffset"] = "conta:N"
    barras = alt.Chart(g).mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6).encode(**enc)
    regra = alt.Chart(pd.DataFrame({"y": [1]})).mark_rule(strokeDash=[4, 4], color=C.CINZA_DUE, opacity=.6).encode(y="y:Q")
    return (barras + regra).properties(height=230, title=titulo_)


def grafico_efeitos(ef: pd.DataFrame, cores: dict) -> alt.Chart:
    e = ef.copy()
    e["sinal"] = np.where(e["efeito"] >= 0, "ajuda", "atrapalha")
    e["efeito_pct"] = e["efeito"] * 100
    multi = e["conta"].nunique() > 1
    cor = (alt.Color("conta:N", scale=alt.Scale(domain=list(cores), range=list(cores.values())), title=None)
           if multi else alt.Color("sinal:N", scale=alt.Scale(domain=["ajuda", "atrapalha"],
                                                              range=[C.AZUL_DUE_MEDIO, C.ROSA_VITORIA]), legend=None))
    enc = dict(y=alt.Y("característica:N", sort=alt.EncodingSortField("efeito", order="descending"), title=None),
               x=alt.X("efeito_pct:Q", title="efeito no engajamento (%), vídeos com vs. sem"),
               color=cor, opacity=alt.condition("datum['vídeos com'] >= 5", alt.value(1), alt.value(.4)),
               tooltip=["conta", "característica", alt.Tooltip("vídeos com:Q"),
                        alt.Tooltip("efeito_pct:Q", format="+.0f", title="efeito %"), "confiança"])
    if multi:
        enc["yOffset"] = "conta:N"
    return (alt.Chart(e).mark_bar(cornerRadiusEnd=5).encode(**enc)
            .properties(height=max(260, 24 * e["característica"].nunique() * (2 if multi else 1))))


# ======================================================== blocos de tela
def melhores_momentos(df: pd.DataFrame) -> dict:
    out = {}
    for col, ordem in (("dia_semana", A.DIAS), ("faixa_horario", A.FAIXAS_HORA),
                       ("periodo_mes", ["início (1–10)", "meio (11–20)", "fim (21–31)"])):
        g = A.por_grupo(df, col, ordem)
        if g.empty:
            out[col] = "–"
            continue
        ok = g[g["videos"] >= 3] if (g["videos"] >= 3).sum() >= 1 else g
        out[col] = str(ok.loc[ok["indice"].idxmax(), col])
    return out


def cartao_perfil(r: dict, info: dict, classe_avatar: str = "", chip_tendencia: str = "rosa") -> str:
    conta = r["conta"]
    nome = info.get("nome") or conta
    tend = r["tendencia"]
    chip_t = (f"<span class='chip {chip_tendencia}'>Tendência {pct(tend)}</span>" if tend is not None else "")
    return f"""
<div class='perfil'>
  <div class='avatar {classe_avatar}'>{esc(nome[:1].upper())}</div>
  <div class='nome'>{esc(nome)}</div>
  <div class='handle'>@{esc(conta)}</div>
  <div class='chips'><span class='chip azul'>{r['videos_validos']} vídeos válidos</span>{chip_t}</div>
  <dl class='lista'>
    <dt>Seguidores</dt><dd>{fmt(r['seguidores'])}</dd>
    <dt>Período</dt><dd>{data_curta(r['inicio'])} a {data_curta(r['fim'])}</dd>
    <dt>Coletado em</dt><dd>{esc(info.get('coletado_em', '–'))}</dd>
    <dt>Tempo de coleta</dt><dd>{info.get('segundos', '–')} s</dd>
  </dl>
  <a class='botao-link' href='{esc(info.get('url', '#'))}' target='_blank'>Abrir perfil no Kwai</a>
</div>"""


def cartao_resumo(r: dict) -> None:
    with st.container(key=f"card_resumo_{r['conta']}"):
        titulo("Vídeo típico", "Mediana de curtidas + comentários por vídeo")
        st.markdown(f"""
<div class='valor-grande'>{fmt(r['mediana_interacoes'])}<small>interações</small></div>
<dl class='lista'>
  <dt>Por 1.000 seguidores</dt><dd>{fmt(r['eng_mil_seg'], 2)}</dd>
  <dt>Posts por semana</dt><dd>{fmt(r['posts_semana'], 1)}</dd>
  <dt>Comentários a cada 100 curtidas</dt><dd>{fmt(r['coment_100_curtidas'], 1)}</dd>
  <dt>Vídeos fora da curva</dt><dd>{pct(r['pct_fora_da_curva'], False)}</dd>
</dl>""", unsafe_allow_html=True)


def cartao_momentos(df: pd.DataFrame, r: dict) -> None:
    with st.container(key=f"card_momentos_{r['conta']}"):
        titulo("Quando postar", "Calculado sobre o vídeo típico de cada dia, horário e período")
        frases = A.recomendacoes_quando(df)
        for f in frases:
            st.markdown(f"<div class='frase'>{_md_para_html(f)}</div>", unsafe_allow_html=True)
        m = melhores_momentos(df)
        st.markdown(f"""
<div class='ladrilhos'>
  <div class='ladrilho'><div class='r'>Melhor dia</div><div class='v'>{esc(m['dia_semana'])}</div></div>
  <div class='ladrilho'><div class='r'>Melhor horário</div><div class='v'>{esc(m['faixa_horario'])}</div></div>
  <div class='ladrilho'><div class='r'>Melhor período do mês</div><div class='v'>{esc(m['periodo_mes'])}</div></div>
  <div class='ladrilho'><div class='r'>Intervalo entre posts</div><div class='v'>{fmt(r['intervalo_mediano'], 1)} dia(s)</div></div>
</div>""", unsafe_allow_html=True)


def _md_para_html(s: str) -> str:
    s = esc(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    return re.sub(r"\*(.+?)\*", r"<i>\1</i>", s)


def notas_qualidade(df: pd.DataFrame) -> str:
    inval = int((~df["valido"]).sum())
    susp = int(df["data_suspeita"].sum())
    sem_leg = int((df["valido"] & ~df["legenda_propria"]).sum())
    itens = []
    if inval:
        itens.append(f"{inval} vídeo(s) não vieram do Kwai mesmo após novas tentativas e ficaram fora das análises.")
    if susp:
        itens.append(f"{susp} vídeo(s) com data incoerente com a grade ficaram fora das análises de data.")
    if sem_leg:
        itens.append(f"{sem_leg} vídeo(s) sem legenda própria ficaram fora da análise de legendas.")
    if not itens:
        itens.append("Todos os vídeos vieram completos.")
    return "".join(f"<div class='nota'><span class='p'></span><span>{t}</span></div>" for t in itens)


def tabela_top(df: pd.DataFrame, n: int = 10) -> None:
    v = df[df["valido"]].sort_values("interacoes", ascending=False).head(n)
    t = v[["data", "interacoes", "indice", "coment_por_100_curtidas", "legenda", "link"]].copy()
    t["legenda"] = t["legenda"].where(t["legenda"].ne(""), "(sem legenda própria)").str.slice(0, 110)
    st.dataframe(t, hide_index=True, width="stretch", column_config={
        "data": st.column_config.DateColumn("data", format="DD/MM/YYYY"),
        "interacoes": st.column_config.NumberColumn("interações", format="%d"),
        "indice": st.column_config.NumberColumn("× vídeo típico", format="%.1f×"),
        "coment_por_100_curtidas": st.column_config.NumberColumn("coment./100 curt.", format="%.1f"),
        "link": st.column_config.LinkColumn("vídeo", display_text="abrir")})


def bloco_quando(df: pd.DataFrame, cores: dict) -> None:
    cols = st.columns(3)
    for coluna, (col, ordem, nome) in zip(cols, (
            ("dia_semana", A.DIAS, "Dia da semana"),
            ("faixa_horario", A.FAIXAS_HORA, "Horário"),
            ("periodo_mes", ["início (1–10)", "meio (11–20)", "fim (21–31)"], "Período do mês"))):
        g = A.por_grupo(df, col, ordem)
        with coluna:
            if g.empty:
                st.caption(f"{nome}: o Kwai não informou as datas.")
            else:
                g[col] = g[col].astype(str)
                st.altair_chart(grafico_grupo(g, col, ordem, cores, nome), width="stretch")
    st.caption("Índice 1,0 = vídeo típico da conta. A mediana evita que um viral isolado distorça o resultado.")


CFG_TAB = {"índice": st.column_config.NumberColumn(format="%.2f"),
           "conversa": st.column_config.NumberColumn("coment./100", format="%.1f"),
           "vs geral": st.column_config.NumberColumn(format="percent")}


def bloco_legendas(df: pd.DataFrame, chave: str) -> None:
    L = df[df["valido"] & df["legenda_propria"]]
    if len(L) < 6:
        st.caption("Há poucas legendas próprias para analisar. São necessárias pelo menos 6.")
        return
    ef = A.efeitos_legenda(df)
    with st.container(key=f"card_efeitos_{chave}"):
        titulo("O que nas legendas acompanha mais engajamento",
               f"{len(L)} legendas analisadas. Compara o vídeo típico com e sem cada característica; "
               "barras claras têm poucos vídeos.")
        if len(ef):
            ef["conta"] = df["conta"].iloc[0]
            st.altair_chart(grafico_efeitos(ef, {df['conta'].iloc[0]: C.COR_A}), width="stretch")

    c1, c2, c3 = st.columns(3)
    for coluna, (col, nome), k in zip((c1, c2, c3), (("categoria_principal", "Tipo de conteúdo"),
                                                     ("gancho", "Como a legenda começa"), ("tom", "Tom")), "abc"):
        with coluna, st.container(key=f"card_cat_{k}_{chave}"):
            titulo(nome)
            st.dataframe(A.tabela_categorica(df, col), hide_index=True, width="stretch", column_config=CFG_TAB)

    pal = A.palavras(df)
    if len(pal):
        c1, c2, c3 = st.columns(3)
        for coluna, (nome, ordem, asc), k in zip((c1, c2, c3), (
                ("Palavras que puxam engajamento", "índice", False),
                ("Palavras que esfriam", "índice", True),
                ("Palavras que puxam comentário", "conversa", False)), "abc"):
            with coluna, st.container(key=f"card_pal_{k}_{chave}"):
                titulo(nome)
                st.dataframe(pal.sort_values(ordem, ascending=asc).head(10), hide_index=True, width="stretch",
                             column_config=CFG_TAB)

    tm = A.temas(df)
    if len(tm):
        with st.container(key=f"card_temas_{chave}"):
            titulo("Temas encontrados", "Legendas agrupadas automaticamente pelo vocabulário")
            st.dataframe(tm, hide_index=True, width="stretch", column_config=CFG_TAB)

    with st.container(key=f"card_sim_{chave}"):
        titulo("Simulador de legenda", "Escreva uma legenda e veja o que ela tem que costuma funcionar nesta conta")
        texto = st.text_area("Legenda", "Você sabia? Últimos dias para garantir o seu! Link na bio 👇",
                             key=f"sim_{chave}", label_visibility="collapsed")
        if texto.strip():
            r = A.testar_legenda(texto, ef)
            linhas = [f"Gancho: <b>{esc(r['gancho'])}</b>"]
            for nome, e in r["tem"]:
                linhas.append(f"{esc(nome)}: <b>{pct(e)}</b>")
            for nome, e in r["sugestoes"]:
                linhas.append(f"Considere incluir: {esc(nome)} ({pct(e)})")
            st.markdown("".join(f"<div class='nota'><span class='p'></span><span>{l}</span></div>" for l in linhas),
                        unsafe_allow_html=True)
            st.caption("São correlações nos vídeos analisados, não garantia de resultado.")


def bloco_dados(df: pd.DataFrame, nome_arquivo: str, chave: str) -> None:
    with st.container(key=f"card_dados_{chave}"):
        c1, c2 = st.columns([3, 1])
        with c1:
            titulo("Dados tratados e rotulados",
                   "Uma linha por vídeo, com métricas, datas, rótulos da legenda (sim/não) e marcações de qualidade. "
                   "O CSV usa ponto e vírgula e vírgula decimal, e abre direto no Excel em português.")
        c2.download_button("Baixar CSV", A.para_csv(df), file_name=nome_arquivo, mime="text/csv",
                           type="primary", key=f"dl_{chave}", width="stretch")
        cols = [c for c in A.COLUNAS_CSV if c in df.columns]
        st.dataframe(df[cols], hide_index=True, width="stretch", height=380,
                     column_config={"link": st.column_config.LinkColumn("link", display_text="abrir")})


# ============================================================== páginas
def pagina_perfil(max_videos: int) -> None:
    cab, campo, botao = st.columns([2.2, 2.4, .8], vertical_alignment="center")
    with cab:
        cabecalho("Analisar perfil")
    perfil = campo.text_input("Perfil", placeholder="Cole o link do perfil, ex.: https://www.kwai.com/@Embelleze",
                              label_visibility="collapsed")
    if botao.button("Analisar", type="primary", width="stretch", disabled=not perfil):
        st.session_state["perfil_ok"] = perfil
    st.write("")

    if "perfil_ok" not in st.session_state:
        with st.container(key="card_vazio"):
            titulo("Comece por um perfil",
                   "Cole acima o link de qualquer perfil público do Kwai, ou só o @, e clique em Analisar. "
                   "A coleta leva cerca de 1 minuto a cada 100 vídeos.")
        return
    res = obter(st.session_state["perfil_ok"], max_videos)
    if not res:
        return
    df, info = res
    r = A.resumo(df)

    esq, dir_ = st.columns([1, 2.7], gap="medium")
    with esq:
        with st.container(key="card_perfil"):
            st.markdown(cartao_perfil(r, info), unsafe_allow_html=True)
        with st.container(key="card_qualidade"):
            titulo("Qualidade dos dados")
            st.markdown(notas_qualidade(df), unsafe_allow_html=True)
    with dir_:
        a, b = st.columns([1.55, 1], gap="medium")
        with a:
            cartao_momentos(df, r)
        with b:
            cartao_resumo(r)

        abas = st.tabs(["Desempenho", "Quando postar", "Legendas", "Dados e CSV"])
        with abas[0], st.container(key="card_desempenho"):
            titulo("Interações ao longo do tempo", "Cada ponto é um vídeo (clique para abrir); a linha é a mediana de 7 vídeos")
            if df["data_ok"].sum() >= 2:
                st.altair_chart(grafico_linha_tempo(df, {r["conta"]: C.COR_A}), width="stretch")
            titulo("Top 10 vídeos")
            tabela_top(df)
        with abas[1], st.container(key="card_quando"):
            bloco_quando(df, {r["conta"]: C.COR_A})
        with abas[2]:
            bloco_legendas(df, "perfil")
        with abas[3]:
            bloco_dados(df, f"kwai_{r['conta']}_{datetime.now(FUSO_BR):%Y-%m-%d}.csv", "perfil")


def placar_html(ra: dict, rb: dict) -> str:
    t = placar(ra, rb)
    ca, cb = f"@{ra['conta']}", f"@{rb['conta']}"
    linhas = []
    for _, l in t.iterrows():
        va = f"<b>{l[ca]}</b>" if l["vantagem"] == ca else l[ca]
        vb = f"<b>{l[cb]}</b>" if l["vantagem"] == cb else l[cb]
        da = "<span class='pt a'></span>" if l["vantagem"] == ca else "<span class='pt'></span>"
        db = "<span class='pt b'></span>" if l["vantagem"] == cb else "<span class='pt'></span>"
        linhas.append(f"<tr><td>{esc(l['indicador'])}</td><td>{da}{va}</td><td>{db}{vb}</td></tr>")
    vit_a = int((t["vantagem"] == ca).sum()); vit_b = int((t["vantagem"] == cb).sum())
    return (f"<div class='placar-total'><span><span class='pt a'></span>{esc(ca)} <b>{vit_a}</b></span>"
            f"<span><span class='pt b'></span>{esc(cb)} <b>{vit_b}</b></span></div>"
            f"<table class='placar'><thead><tr><th>Indicador</th><th>{esc(ca)}</th><th>{esc(cb)}</th></tr></thead>"
            f"<tbody>{''.join(linhas)}</tbody></table>")


def placar(ra: dict, rb: dict) -> pd.DataFrame:
    itens = [("Seguidores", "seguidores", 0, True), ("Vídeo típico (interações)", "mediana_interacoes", 0, True),
             ("Engajamento por 1.000 seguidores", "eng_mil_seg", 2, True), ("Posts por semana", "posts_semana", 1, True),
             ("Comentários a cada 100 curtidas", "coment_100_curtidas", 1, True),
             ("Vídeos fora da curva", "pct_fora_da_curva", None, True),
             ("Tendência recente", "tendencia", None, True), ("Maior pausa sem postar (dias)", "maior_pausa", 0, False)]
    linhas = []
    for rotulo, k, casas, maior_melhor in itens:
        a, b = ra.get(k), rb.get(k)
        f = (lambda x: pct(x, k == "tendencia")) if casas is None else (lambda x, c=casas: fmt(x, c))
        venc = "empate"
        if a is not None and b is not None and not (pd.isna(a) or pd.isna(b)) and a != b:
            venc = "@" + (ra["conta"] if (a > b) == maior_melhor else rb["conta"])
        linhas.append({"indicador": rotulo, f"@{ra['conta']}": f(a), f"@{rb['conta']}": f(b), "vantagem": venc})
    return pd.DataFrame(linhas)


def pagina_competicao(max_videos: int) -> None:
    cabecalho("Competição")
    st.write("")
    with st.container(key="card_entrada_comp"):
        titulo("Compare dois perfis lado a lado",
               "Os índices são relativos ao vídeo típico de cada conta, então dá para comparar contas de tamanhos diferentes.")
        c1, c2, c3 = st.columns([2, 2, .8], vertical_alignment="bottom")
        pa = c1.text_input("Perfil A", placeholder="https://www.kwai.com/@marcaA", key="comp_a")
        pb = c2.text_input("Perfil B (concorrente)", placeholder="https://www.kwai.com/@marcaB", key="comp_b")
        if c3.button("Comparar", type="primary", width="stretch", disabled=not (pa and pb)):
            st.session_state["comp_ok"] = (pa, pb)
    if "comp_ok" not in st.session_state:
        return
    pa, pb = st.session_state["comp_ok"]
    ra_ = obter(pa, max_videos)
    rb_ = obter(pb, max_videos) if ra_ else None
    if not (ra_ and rb_):
        return
    (da, ia), (db, ib) = ra_, rb_
    if da["conta"].iloc[0].lower() == db["conta"].iloc[0].lower():
        st.warning("Os dois links são do mesmo perfil. Troque um deles.")
        return
    ra, rb = A.resumo(da), A.resumo(db)
    cores = {ra["conta"]: C.COR_A, rb["conta"]: C.COR_B}
    df = pd.concat([da, db], ignore_index=True)

    pa_col, placar_col, pb_col = st.columns([1, 1.9, 1], gap="medium")
    with pa_col, st.container(key="card_comp_a"):
        st.markdown(cartao_perfil(ra, ia, "b", "azul"), unsafe_allow_html=True)
    with pb_col, st.container(key="card_comp_b"):
        st.markdown(cartao_perfil(rb, ib, "", "laranja"), unsafe_allow_html=True)
    with placar_col, st.container(key="card_placar"):
        titulo("Placar", "Quem leva vantagem em cada indicador")
        st.markdown(placar_html(ra, rb), unsafe_allow_html=True)

    abas = st.tabs(["Desempenho", "Quando postar", "Legendas", "Top vídeos", "Dados e CSV"])
    with abas[0], st.container(key="card_c_desemp"):
        titulo("Interações ao longo do tempo", "Cada ponto é um vídeo; a linha é a mediana de 7 vídeos")
        st.altair_chart(grafico_linha_tempo(df, cores), width="stretch")
    with abas[1]:
        a, b = st.columns(2, gap="medium")
        for col, d, r, k in ((a, da, ra, "a"), (b, db, rb, "b")):
            with col:
                cartao_momentos(d, r)
        with st.container(key="card_c_quando"):
            bloco_quando(df, cores)
    with abas[2]:
        efs = []
        for d in (da, db):
            e = A.efeitos_legenda(d)
            if len(e):
                e["conta"] = d["conta"].iloc[0]
                efs.append(e)
        with st.container(key="card_c_efeitos"):
            titulo("O que nas legendas acompanha mais engajamento em cada conta")
            if efs:
                st.altair_chart(grafico_efeitos(pd.concat(efs), cores), width="stretch")
            else:
                st.caption("Há poucas legendas próprias para comparar.")
        a, b = st.columns(2, gap="medium")
        for col, d, k in ((a, da, "a"), (b, db, "b")):
            with col, st.container(key=f"card_c_cat_{k}"):
                titulo(f"@{esc(d['conta'].iloc[0])}", "Tipo de conteúdo")
                st.dataframe(A.tabela_categorica(d, "categoria_principal"), hide_index=True, width="stretch",
                             column_config=CFG_TAB)
                top = A.palavras_top(d)
                if top:
                    st.caption("Palavras mais comuns nos 25% que mais engajam: " + ", ".join(f"{w} ({n})" for w, n in top))
    with abas[3]:
        a, b = st.columns(2, gap="medium")
        for col, d, k in ((a, da, "a"), (b, db, "b")):
            with col, st.container(key=f"card_c_top_{k}"):
                titulo(f"@{esc(d['conta'].iloc[0])}")
                tabela_top(d, 8)
    with abas[4]:
        bloco_dados(df, f"kwai_competicao_{ra['conta']}_x_{rb['conta']}_{datetime.now(FUSO_BR):%Y-%m-%d}.csv", "comp")


def pagina_como_funciona() -> None:
    cabecalho("Como funciona")
    st.write("")
    a, b = st.columns(2, gap="medium")
    with a, st.container(key="card_cf_coleta"):
        titulo("Como os dados são coletados")
        st.markdown("""
1. Um navegador invisível abre o perfil e rola a grade de vídeos para pegar os links.
2. A página pública de cada vídeo é lida, 4 de cada vez: curtidas, comentários, legenda, data, hora e duração.
3. Quando o Kwai devolve uma página genérica, o app tenta de novo até 3 vezes. O que não vier fica marcado como inválido.
""")
        titulo("Como ler")
        st.markdown("Tudo usa **mediana**, para que um viral isolado não distorça o resultado. "
                    "Os efeitos são correlações: mostram o que acompanha o engajamento, não garantem causa.")
    with b, st.container(key="card_cf_trat"):
        titulo("Como os dados são tratados")
        st.markdown("""
- **Interações** = curtidas + comentários.
- **Índice** = interações do vídeo ÷ mediana da conta. 1,0 é o vídeo típico e 2,0 é o dobro.
- **Data suspeita**: a grade vem do mais novo ao mais antigo. Uma data que foge mais de 45 dias da dos vizinhos sai das análises de tempo.
- **Legenda própria**: vídeos sem legenda ficam fora da análise de texto.
- **Rótulos da legenda**: pergunta, chamada para ação, urgência, preço, contato, "você", "nós", emoji, hashtag, exclamação, maiúsculas, 8 tipos de conteúdo, gancho e tom.
""")


# ================================================================== tela
with st.sidebar:
    st.markdown("<div class='marca'>" + "<div class='sep'></div>".join(_logo_html(l) for l in C.LOGOS) + "</div>",
                unsafe_allow_html=True)
    st.markdown("<div class='rotulo-lateral'>Menu</div>", unsafe_allow_html=True)
    pagina = st.radio("Menu", ["Analisar perfil", "Competição", "Como funciona"], label_visibility="collapsed")
    st.markdown("<div class='rotulo-lateral'>Ajustes</div>", unsafe_allow_html=True)
    max_videos = st.slider("Vídeos mais recentes por perfil", 30, 300, C.MAX_VIDEOS_PADRAO, 10,
                           help="Mais vídeos deixam a análise mais confiável, mas a coleta demora mais (cerca de 1 min a cada 100).")
    if st.button("Limpar dados em memória", width="stretch"):
        st.session_state.pop("coletas", None)
        st.session_state.pop("comp_ok", None)
        st.session_state.pop("perfil_ok", None)
        st.rerun()
    st.markdown(f"<div class='assinatura'><span>Desenvolvido por</span><br><b>{esc(C.AUTOR)}</b><br>"
                f"<span>{esc(C.CRIADO_EM)}</span>"
                + (f"<br><span>{esc(C.CONTATO_AUTOR)}</span>" if C.CONTATO_AUTOR else "")
                + "</div>", unsafe_allow_html=True)

if pagina == "Analisar perfil":
    pagina_perfil(max_videos)
elif pagina == "Competição":
    pagina_competicao(max_videos)
else:
    pagina_como_funciona()
