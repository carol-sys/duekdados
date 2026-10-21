"""Tratamento, rótulos e análises dos vídeos coletados."""
from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict

import numpy as np
import pandas as pd

DIAS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
FAIXAS_HORA = ["madrugada", "manhã", "tarde", "noite"]


# =================================================================== texto
def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


PARADAS = set(sem_acento(w) for w in """a o as os e é de da do das dos em no na nos nas um uma uns umas que pra para por com sem se
não nao mais mas ao à às eu ele ela eles elas isso isto esse essa este esta aquele aquela meu minha seu sua nosso nossa
já ja tem ter foi ser são sao vai vou como quando onde porque muito muita bem só so também tambem aqui lá la está esta estão
pelo pela pelos pelas sobre todo toda todos todas até ate num numa ou nem quem qual quais cada outro outra mesmo mesma
kwai video vídeo from curtidas comentários comentarios like likes comment comments make everyone shine quot amp""".split())

CATEGORIAS = {
    "Oferta/promoção": ["promoção", "promocao", "oferta", "desconto", "cupom", "grátis", "gratis", "frete", "liquidação",
                        "liquidacao", "black friday", "preço", "preco", "por apenas", "só hoje", "aproveite", "off"],
    "Serviço público": ["inscrição", "inscricao", "inscrições", "inscricoes", "matrícula", "matricula", "edital", "vacina",
                        "vacinação", "vacinacao", "atendimento", "agendamento", "documento", "cadastro", "benefício",
                        "beneficio", "prazo", "gratuito", "gratuita", "secretaria", "prefeitura", "governo", "posto", "unidade"],
    "Dica/educativo": ["dica", "dicas", "como fazer", "saiba", "aprenda", "passo a passo", "tutorial", "você sabia",
                       "voce sabia", "entenda", "confira", "guia", "erro", "erros", "segredo"],
    "Novidade/lançamento": ["novo", "nova", "novidade", "lançamento", "lancamento", "chegou", "estreia", "inauguração",
                            "inauguracao", "inaugura", "primeira vez"],
    "Evento/data": ["evento", "feira", "festival", "show", "palestra", "curso", "oficina", "workshop", "dia das",
                    "dia dos", "natal", "páscoa", "pascoa", "carnaval", "aniversário", "aniversario"],
    "Prova social": ["cliente", "clientes", "depoimento", "avaliação", "avaliacao", "resultado", "antes e depois",
                     "satisfeito", "recomendo", "sucesso", "mil pessoas", "atendidos"],
    "Bastidores/equipe": ["bastidores", "equipe", "time", "nossa história", "nossa historia", "por trás", "por tras",
                          "colaborador", "colaboradores", "servidor", "servidores", "dia a dia"],
    "Utilidade/aviso": ["atenção", "atencao", "aviso", "importante", "alerta", "comunicado", "horário", "horario",
                        "funcionamento", "endereço", "endereco", "fechado", "aberto", "mudança", "mudanca"],
}
CHAMADAS = ["comente", "comenta", "compartilhe", "compartilha", "curta", "siga", "segue", "inscreva", "inscreva-se", "assista",
            "veja", "confira", "clique", "acesse", "compre", "peça", "peca", "encomende", "agende", "reserve", "garanta",
            "baixe", "chame", "chama", "fale", "ligue", "visite", "venha", "participe", "marque", "link na bio",
            "saiba mais", "manda"]
URGENCIA = ["agora", "hoje", "urgente", "última", "ultima", "últimos", "ultimos", "só hoje", "corre", "rápido", "rapido",
            "imperdível", "imperdivel", "ao vivo", "amanhã", "amanha", "termina", "encerra", "prazo", "vagas limitadas"]
POSITIVAS = ["amor", "alegria", "feliz", "felicidade", "orgulho", "obrigado", "obrigada", "parabéns", "parabens", "conquista",
             "sonho", "juntos", "melhor", "lindo", "linda", "incrível", "incrivel", "maravilhoso", "sucesso", "qualidade",
             "cuidado", "bem-estar", "fácil", "facil", "economia", "seguro", "segurança", "seguranca"]
NEGATIVAS = ["problema", "erro", "golpe", "fraude", "cuidado com", "perigo", "risco", "multa", "reclamação", "reclamacao",
             "atraso", "falta", "crise", "medo", "pior", "prejuízo", "prejuizo", "fechado", "suspenso", "cancelado"]
RE_EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF⭐❤]")
RE_PRECO = re.compile(r"r\$\s?\d|\d+\s?%|\d+,\d{2}\b")
RE_CONTATO = re.compile(r"whats|zap|\(\d{2}\)|\d{4,5}-\d{4}|www\.|\.com|\.gov|\.br|link na bio|site")

_cache_re: dict[str, re.Pattern] = {}


def _re_termo(w: str) -> re.Pattern:
    if w not in _cache_re:
        _cache_re[w] = re.compile(r"(?<!\w)" + re.escape(sem_acento(w.lower())) + r"(?!\w)")
    return _cache_re[w]


def tem_algum(texto_sa: str, lista) -> bool:
    return any(_re_termo(w).search(texto_sa) for w in lista)


def conta_termos(texto_sa: str, lista) -> int:
    return sum(len(_re_termo(w).findall(texto_sa)) for w in lista)


def tipo_gancho(leg: str) -> str:
    ini = leg.strip()[:60]
    p = ini.split()
    if not p:
        return "vazio"
    s = sem_acento(ini.lower())
    if "?" in ini:
        return "pergunta"
    if RE_PRECO.search(s):
        return "preço/%"
    if re.match(r"^[\d°º]", ini):
        return "número/lista"
    if tem_algum(s[:25], ["atenção", "atencao", "aviso", "importante", "alerta", "urgente"]):
        return "alerta"
    if sem_acento(p[0].lower().strip(".,!:")) in {sem_acento(c) for c in CHAMADAS}:
        return "chamada para ação"
    if tem_algum(s[:25], ["novo", "nova", "novidade", "chegou", "lançamento", "lancamento"]):
        return "novidade"
    if sum(c.isupper() for c in ini) / max(1, sum(c.isalpha() for c in ini)) > 0.7:
        return "MAIÚSCULAS"
    if sem_acento(p[0].lower()) in ("voce", "voces", "vc", "gente", "pessoal", "galera", "amigos", "cliente"):
        return "fala direta"
    return "frase comum"


# Nome da coluna no CSV → descrição. A ordem é a ordem de exibição.
ROTULOS = {
    "tem_pergunta": "Tem pergunta (?)",
    "tem_chamada_acao": "Chamada para ação (agende, compre, link na bio…)",
    "tem_urgencia": "Urgência/prazo (hoje, últimos dias…)",
    "tem_preco": "Preço, % ou valor",
    "tem_contato": "Contato/link (whats, site, telefone)",
    "fala_com_voce": "Fala com 'você'",
    "fala_em_nos": "Fala em 'nós' (a marca)",
    "tem_emoji": "Tem emoji",
    "tem_hashtag": "Tem hashtag",
    "tem_exclamacao": "Tem exclamação",
    "caixa_alta": "Quase tudo em MAIÚSCULAS (>70%)",
}
ROTULOS_CATEGORIA = {f"cat_{sem_acento(k).lower().replace('/', '_').replace(' ', '_')}": k for k in CATEGORIAS}


def caracteristicas(texto: str) -> dict:
    """Marcações (rótulos) de UMA legenda."""
    s = sem_acento(texto.lower())
    letras = max(1, sum(c.isalpha() for c in texto))
    c = {
        "tem_pergunta": "?" in texto,
        "tem_chamada_acao": tem_algum(s, CHAMADAS),
        "tem_urgencia": tem_algum(s, URGENCIA),
        "tem_preco": bool(RE_PRECO.search(s)),
        "tem_contato": bool(RE_CONTATO.search(s)),
        "fala_com_voce": bool(re.search(r"(?<!\w)(?:voce|voces|vc|seu|sua|te)(?!\w)", s)),
        "fala_em_nos": bool(re.search(r"(?<!\w)(?:nosso|nossa|nossos|nossas|estamos|somos)(?!\w)", s)),
        "tem_emoji": bool(RE_EMOJI.search(texto)),
        "tem_hashtag": "#" in texto,
        "tem_exclamacao": "!" in texto,
        "caixa_alta": sum(ch.isupper() for ch in texto) / letras > 0.7,
    }
    for col, cat in ROTULOS_CATEGORIA.items():
        c[col] = tem_algum(s, CATEGORIAS[cat])
    return c


# =============================================================== tratamento
def tratar(linhas: list[dict]) -> pd.DataFrame:
    """Lista bruta da coleta → tabela tratada e rotulada (uma linha por vídeo)."""
    df = pd.DataFrame(linhas)
    for c in ("curtidas", "comentarios", "duracao_segundos", "hora_publicacao", "seguidores_perfil"):
        df[c] = pd.to_numeric(df.get(c), errors="coerce")
    for c in ("legenda", "data_publicacao", "fonte_data"):
        df[c] = df.get(c, pd.Series("", index=df.index)).fillna("").astype(str)
    for c in ("legenda_propria", "pagina_generica"):
        df[c] = df.get(c, pd.Series(False, index=df.index)).fillna(False).astype(bool)

    df["valido"] = ~df["pagina_generica"] & df["curtidas"].notna()
    df["data"] = pd.to_datetime(df["data_publicacao"], errors="coerce")
    df = df.sort_values(["conta", "posicao"]).reset_index(drop=True)

    # A grade do perfil vem do mais novo para o mais antigo. Uma data muito
    # diferente da dos vídeos vizinhos na grade é erro de leitura da página.
    df["data_suspeita"] = False
    for _, idx in df.groupby("conta").groups.items():
        d = df.loc[idx, "data"]
        dias = (d - pd.Timestamp("1970-01-01")).dt.total_seconds() / 86_400
        vizinhos = dias.rolling(9, center=True, min_periods=3).median()
        dif_dias = (dias - vizinhos).abs()
        df.loc[idx, "data_suspeita"] = (dif_dias > 45).fillna(False).values
    df.loc[df["data_suspeita"], ["data"]] = pd.NaT
    df["data_ok"] = df["data"].notna()

    df["interacoes"] = df["curtidas"].fillna(0) + df["comentarios"].fillna(0)
    df["dia_semana"] = df["data"].dt.dayofweek.map(lambda d: DIAS[int(d)] if pd.notna(d) else "")
    df["faixa_horario"] = pd.cut(df["hora_publicacao"].where(df["data_ok"]), [-1, 5, 11, 17, 23], labels=FAIXAS_HORA).astype(str).replace("nan", "")
    df["periodo_mes"] = pd.cut(df["data"].dt.day, [0, 10, 20, 31], labels=["início (1–10)", "meio (11–20)", "fim (21–31)"]).astype(str).replace("nan", "")
    df["mes"] = df["data"].dt.strftime("%Y-%m").fillna("")
    df["faixa_duracao"] = pd.cut(df["duracao_segundos"], [0, 15, 30, 60, 180, 1e9],
                                 labels=["até 15s", "15–30s", "30s–1min", "1–3min", "3min+"]).astype(str).replace("nan", "")

    med = df[df["valido"]].groupby("conta")["interacoes"].median()
    df["indice"] = df["interacoes"] / df["conta"].map(med).replace(0, np.nan)   # 1,0 = vídeo típico da conta
    df["fora_da_curva"] = df["indice"] >= 2
    df["coment_por_100_curtidas"] = df["comentarios"] / df["curtidas"].where(df["curtidas"] > 0) * 100
    df["eng_por_mil_seguidores"] = df["interacoes"] / df["seguidores_perfil"].where(df["seguidores_perfil"] > 0) * 1000

    # rótulos da legenda
    leg = df["legenda"].where(df["legenda_propria"], "")
    marc = pd.DataFrame([caracteristicas(t) if t else {k: False for k in caracteristicas("")} for t in leg], index=df.index)
    df = pd.concat([df, marc], axis=1)
    sa = leg.map(lambda s: sem_acento(s.lower()))
    df["n_caracteres"] = leg.str.len()
    df["n_palavras"] = leg.map(lambda s: len(re.findall(r"\w+", s)))
    df["n_emojis"] = leg.map(lambda s: len(RE_EMOJI.findall(s)))
    df["n_hashtags"] = leg.str.count(r"#\w+")
    df["pct_maiusculas"] = leg.map(lambda s: sum(c.isupper() for c in s) / max(1, sum(c.isalpha() for c in s)))
    pos, neg = sa.map(lambda s: conta_termos(s, POSITIVAS)), sa.map(lambda s: conta_termos(s, NEGATIVAS))
    df["tom"] = np.where(~df["legenda_propria"], "", np.select([pos > neg, neg > pos], ["positivo", "negativo/alerta"], "neutro"))
    df["gancho"] = np.where(df["legenda_propria"], leg.map(tipo_gancho), "")
    cats = list(ROTULOS_CATEGORIA)
    df["categoria_principal"] = np.where(
        df["legenda_propria"],
        df[cats].apply(lambda r: ROTULOS_CATEGORIA[r.index[r.values.argmax()]] if r.any() else "sem categoria", axis=1),
        "")
    return df


COLUNAS_CSV = ["conta", "posicao", "data_publicacao", "hora_publicacao", "dia_semana", "faixa_horario", "periodo_mes",
               "mes", "duracao_segundos", "faixa_duracao", "curtidas", "comentarios", "interacoes", "indice",
               "fora_da_curva", "coment_por_100_curtidas", "eng_por_mil_seguidores", "seguidores_perfil",
               "legenda", "legenda_propria", "gancho", "tom", "categoria_principal",
               *ROTULOS, *ROTULOS_CATEGORIA, "n_caracteres", "n_palavras", "n_emojis", "n_hashtags",
               "valido", "data_suspeita", "fonte_data", "id_video", "link"]


def para_csv(df: pd.DataFrame) -> bytes:
    """CSV pronto para abrir no Excel em português (; e vírgula decimal)."""
    out = df[[c for c in COLUNAS_CSV if c in df.columns]].copy()
    for c in out.columns:
        if out[c].dtype == bool:
            out[c] = out[c].map({True: "sim", False: "não"})
    out["indice"] = out["indice"].round(2)
    for c in ("coment_por_100_curtidas", "eng_por_mil_seguidores"):
        out[c] = out[c].round(2)
    return out.to_csv(index=False, sep=";", decimal=",", encoding="utf-8-sig").encode("utf-8-sig")


# ================================================================ análises
def resumo(d: pd.DataFrame) -> dict:
    """Números principais de UMA conta (só vídeos válidos)."""
    v = d[d["valido"]]
    t = v[v["data_ok"]].sort_values("data")
    seg = v["seguidores_perfil"].max()
    med = v["interacoes"].median() if len(v) else np.nan
    r = {"conta": d["conta"].iloc[0], "videos_coletados": len(d), "videos_validos": len(v),
         "seguidores": seg if pd.notna(seg) else None,
         "mediana_interacoes": med, "mediana_curtidas": v["curtidas"].median(),
         "mediana_comentarios": v["comentarios"].median(),
         "eng_mil_seg": med / seg * 1000 if seg and seg > 0 else None,
         "coment_100_curtidas": v["comentarios"].sum() / v["curtidas"].sum() * 100 if v["curtidas"].sum() else None,
         "pct_fora_da_curva": v["fora_da_curva"].mean() if len(v) else None,
         "pct_legenda_propria": v["legenda_propria"].mean() if len(v) else None,
         "inicio": t["data"].min(), "fim": t["data"].max(), "posts_semana": None,
         "intervalo_mediano": None, "maior_pausa": None, "tendencia": None, "tendencia_rec": None, "tendencia_ant": None}
    if len(t) >= 2:
        dias = (t["data"].max() - t["data"].min()).days + 1
        r["posts_semana"] = len(t) / max(dias / 7, 1 / 7)
        gaps = t["data"].diff().dt.days.dropna()
        r["intervalo_mediano"], r["maior_pausa"] = gaps.median(), int(gaps.max())
    if len(t) >= 8:
        k = min(10, len(t) // 2)
        rec, ant = t["interacoes"].tail(k).median(), t["interacoes"].iloc[-2 * k:-k].median()
        r["tendencia"] = rec / ant - 1 if ant else None
        r["tendencia_rec"], r["tendencia_ant"], r["tendencia_k"] = rec, ant, k
    return r


def por_grupo(d: pd.DataFrame, col: str, ordem: list[str] | None = None) -> pd.DataFrame:
    v = d[d["valido"] & d[col].astype(str).ne("")]
    if v.empty:
        return pd.DataFrame()
    g = v.groupby(["conta", col], observed=True).agg(
        videos=("id_video", "count"), interacoes=("interacoes", "median"), indice=("indice", "median"),
        curtidas=("curtidas", "median"), comentarios=("comentarios", "median")).reset_index()
    if ordem:
        g[col] = pd.Categorical(g[col], ordem, ordered=True)
        g = g.sort_values(["conta", col])
    return g


def recomendacoes_quando(d: pd.DataFrame) -> list[str]:
    """Frases do tipo 'posta mais em X, mas engaja mais em Y'."""
    frases = []
    for col, rotulo, ordem in (("dia_semana", "dia", DIAS), ("faixa_horario", "horário", FAIXAS_HORA),
                               ("periodo_mes", "período do mês", None)):
        g = por_grupo(d, col, ordem)
        if len(g) < 2:
            continue
        ok = g[g["videos"] >= 3] if (g["videos"] >= 3).sum() >= 2 else g
        mais = g.loc[g["videos"].idxmax(), col]
        melhor = ok.loc[ok["indice"].idxmax(), col]
        if mais != melhor:
            ganho = ok.loc[ok[col] == melhor, "indice"].iloc[0] / g.loc[g[col] == mais, "indice"].iloc[0] - 1
            frases.append(f"**{rotulo.capitalize()}:** posta mais em *{mais}*, mas engaja mais em *{melhor}* ({ganho:+.0%}).")
        else:
            frases.append(f"**{rotulo.capitalize()}:** posta mais e engaja mais em *{melhor}*.")
    return frases


def efeitos_legenda(d: pd.DataFrame) -> pd.DataFrame:
    """Para cada rótulo: índice mediano dos vídeos COM vs SEM."""
    L = d[d["valido"] & d["legenda_propria"]]
    linhas = []
    for col, nome in {**ROTULOS, **{k: f"Conteúdo: {v}" for k, v in ROTULOS_CATEGORIA.items()}}.items():
        com, sem = L[L[col]], L[~L[col]]
        if len(com) < 2 or len(sem) < 2:
            continue
        linhas.append({"chave": col, "característica": nome, "vídeos com": len(com),
                       "índice com": com["indice"].median(), "índice sem": sem["indice"].median(),
                       "efeito": com["indice"].median() / sem["indice"].median() - 1,
                       "conversa com": com["coment_por_100_curtidas"].median(),
                       "conversa sem": sem["coment_por_100_curtidas"].median(),
                       "confiança": "ok" if len(com) >= 5 else "poucos vídeos"})
    return pd.DataFrame(linhas).sort_values("efeito", ascending=False) if linhas else pd.DataFrame()


def tabela_categorica(d: pd.DataFrame, col: str) -> pd.DataFrame:
    L = d[d["valido"] & d["legenda_propria"]]
    if L.empty:
        return pd.DataFrame()
    return (L.groupby(col).agg(vídeos=("indice", "count"), índice=("indice", "median"),
                               conversa=("coment_por_100_curtidas", "median"))
             .sort_values("índice", ascending=False).reset_index())


def _termos(s: str) -> set[str]:
    w = [x for x in re.findall(r"[a-z0-9]+", sem_acento(s.lower())) if len(x) >= 3 and x not in PARADAS]
    return set(w) | {f"{a} {b}" for a, b in zip(w, w[1:])}


def palavras(d: pd.DataFrame, minimo: int = 3) -> pd.DataFrame:
    L = d[d["valido"] & d["legenda_propria"]].reset_index(drop=True)
    idx = defaultdict(list)
    for i, ts in enumerate(L["legenda"].map(_termos)):
        for t in ts:
            idx[t].append(i)
    med = L["indice"].median()
    tab = [{"termo": t, "legendas": L.loc[ii, "legenda"].nunique(), "índice": L.loc[ii, "indice"].median(),
            "conversa": L.loc[ii, "coment_por_100_curtidas"].median()}
           for t, ii in idx.items() if L.loc[ii, "legenda"].nunique() >= minimo]
    out = pd.DataFrame(tab)
    if len(out):
        out["vs geral"] = out["índice"] / med - 1
    return out


def temas(d: pd.DataFrame) -> pd.DataFrame:
    from sklearn.cluster import KMeans
    from sklearn.feature_extraction.text import TfidfVectorizer

    L = d[d["valido"] & d["legenda_propria"]].reset_index(drop=True)
    if len(L) < 8:
        return pd.DataFrame()
    k = max(2, min(6, len(L) // 6))
    vec = TfidfVectorizer(preprocessor=lambda s: sem_acento(s.lower()), token_pattern=r"[a-z]{3,}",
                          stop_words=list(PARADAS), ngram_range=(1, 2), min_df=2, max_df=0.6)
    try:
        X = vec.fit_transform(L["legenda"])
    except ValueError:
        return pd.DataFrame()
    rot = KMeans(n_clusters=k, n_init=10, random_state=0).fit_predict(X)
    vocab = np.array(vec.get_feature_names_out())
    linhas = []
    for c in range(k):
        sub = L[rot == c]
        centro = np.asarray(X[np.where(rot == c)[0]].mean(axis=0)).ravel()
        linhas.append({"tema": " · ".join(vocab[centro.argsort()[::-1][:4]]), "vídeos": len(sub),
                       "índice": sub["indice"].median(), "conversa": sub["coment_por_100_curtidas"].median(),
                       "melhor exemplo": sub.sort_values("indice", ascending=False)["legenda"].iloc[0][:90]})
    return pd.DataFrame(linhas).sort_values("índice", ascending=False)


def testar_legenda(texto: str, efeitos: pd.DataFrame) -> dict:
    c = caracteristicas(texto)
    tem, sugestoes = [], []
    if len(efeitos):
        for _, r in efeitos.iterrows():
            if c.get(r["chave"]):
                tem.append((r["característica"], r["efeito"]))
        forma = efeitos["chave"].isin(list(ROTULOS)) & efeitos["chave"].ne("tem_preco")
        for _, r in efeitos[(efeitos["efeito"] > 0.2) & forma].iterrows():
            if not c.get(r["chave"]):
                sugestoes.append((r["característica"], r["efeito"]))
    return {"gancho": tipo_gancho(texto), "tem": tem, "sugestoes": sugestoes[:3]}


def palavras_top(d: pd.DataFrame, n: int = 10) -> list[tuple[str, int]]:
    L = d[d["valido"] & d["legenda_propria"]]
    if L.empty:
        return []
    top = L[L["indice"] >= L["indice"].quantile(0.75)]
    cont = Counter(w for s in top["legenda"] for w in {x for x in re.findall(r"[a-z]{4,}", sem_acento(s.lower()))
                                                         if x not in PARADAS})
    return cont.most_common(n)
