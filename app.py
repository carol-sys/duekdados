"""Kwai Insights — app Streamlit.

Rodar no computador:  streamlit run app.py
"""
from __future__ import annotations

import base64
from datetime import datetime
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

import config

try:   # estrutura com pastas (kwai/coleta.py)
    from kwai import analise as A
    from kwai.coleta import FUSO_BR, coletar_perfil, normalizar_perfil
except ImportError:   # todos os arquivos soltos na raiz do repositório
    import analise as A
    from coleta import FUSO_BR, coletar_perfil, normalizar_perfil

RAIZ = Path(__file__).parent
st.set_page_config(page_title=config.NOME_APP, page_icon="📊", layout="wide")


# ================================================================ visual
def _logo_html(item: dict, altura: int = 54) -> str:
    for ext, mime in ((".png", "image/png"), (".jpg", "image/jpeg"), (".jpeg", "image/jpeg"), (".svg", "image/svg+xml")):
        for p in (RAIZ / "assets" / f"{item['arquivo']}{ext}", RAIZ / f"{item['arquivo']}{ext}"):
            if not p.exists():
                continue
            b64 = base64.b64encode(p.read_bytes()).decode()
            return f'<img src="data:{mime};base64,{b64}" alt="{item["nome"]}" style="height:{altura}px;max-width:180px;object-fit:contain">'
    return f'<span class="logo-texto">{item["nome"]}</span>'


st.markdown(f"""
<style>
  .block-container {{padding-top: 1.6rem; max-width: 1300px;}}
  .topo {{display:flex; align-items:center; gap:22px; flex-wrap:wrap; padding:14px 18px;
          border:1px solid rgba(128,128,128,.25); border-radius:14px; margin-bottom:10px}}
  .topo .logos {{display:flex; align-items:center; gap:18px}}
  .topo .sep {{width:1px; height:44px; background:rgba(128,128,128,.35)}}
  .topo h1 {{font-size:1.75rem; margin:0; line-height:1.15}}
  .topo p {{margin:2px 0 0; opacity:.75; font-size:.95rem}}
  .logo-texto {{font-weight:800; font-size:1.35rem; letter-spacing:.04em; padding:6px 12px;
                border:2px solid currentColor; border-radius:8px}}
  .assinatura {{margin-left:auto; text-align:right; font-size:.85rem; opacity:.8}}
  .assinatura b {{font-size:.95rem}}
  .rodape {{text-align:center; opacity:.6; font-size:.85rem; margin-top:40px; padding-top:14px;
            border-top:1px solid rgba(128,128,128,.25)}}
  div[data-testid="stMetricValue"] {{font-size:1.55rem}}
</style>
<div class="topo">
  <div class="logos">{'<div class="sep"></div>'.join(_logo_html(l) for l in config.LOGOS)}</div>
  <div><h1>{config.NOME_APP}</h1><p>{config.SUBTITULO}</p></div>
  <div class="assinatura">Desenvolvido por<br><b>{config.AUTOR}</b><br>{config.CRIADO_EM}</div>
</div>
""", unsafe_allow_html=True)


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


# ================================================================ coleta
def obter(perfil: str, max_videos: int, forcar: bool = False) -> tuple[pd.DataFrame, dict] | None:
    """Coleta (ou reaproveita da memória da sessão) e trata um perfil."""
    _, conta = normalizar_perfil(perfil)
    if not conta:
        st.error(f"Não reconheci o perfil **{perfil}**. Cole um link como `https://www.kwai.com/@Embelleze`.")
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
    esc = alt.Scale(domain=list(cores), range=list(cores.values()))
    base = alt.Chart(v).encode(x=alt.X("data:T", title=None))
    pontos = base.mark_circle(size=34, opacity=.45).encode(
        y=alt.Y("interacoes:Q", title="interações (escala log)", scale=alt.Scale(type="symlog")),
        color=alt.Color("conta:N", scale=esc, title=None),
        tooltip=[alt.Tooltip("conta:N"), alt.Tooltip("data:T", format="%d/%m/%Y"),
                 alt.Tooltip("interacoes:Q", format=",.0f"), alt.Tooltip("leg_curta:N", title="legenda")],
        href="link:N")
    linha = base.mark_line(strokeWidth=2.2).encode(y="mediana_movel:Q", color=alt.Color("conta:N", scale=esc))
    return (pontos + linha).properties(height=300)


def grafico_grupo(g: pd.DataFrame, col: str, ordem, cores: dict, titulo: str) -> alt.Chart:
    esc = alt.Scale(domain=list(cores), range=list(cores.values()))
    multi = g["conta"].nunique() > 1
    enc = dict(
        x=alt.X(f"{col}:N", sort=ordem, title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("indice:Q", title="índice (1 = vídeo típico)"),
        color=alt.Color("conta:N", scale=esc, legend=None if not multi else alt.Legend(title=None)),
        tooltip=[alt.Tooltip("conta:N"), alt.Tooltip(f"{col}:N"), alt.Tooltip("videos:Q", title="vídeos"),
                 alt.Tooltip("indice:Q", format=".2f", title="índice"),
                 alt.Tooltip("interacoes:Q", format=",.0f", title="interações (mediana)")])
    if multi:
        enc["xOffset"] = "conta:N"
    barras = alt.Chart(g).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(**enc)
    regra = alt.Chart(pd.DataFrame({"y": [1]})).mark_rule(strokeDash=[4, 4], opacity=.5).encode(y="y:Q")
    return (barras + regra).properties(height=230, title=titulo)


def grafico_efeitos(ef: pd.DataFrame, cores: dict) -> alt.Chart:
    e = ef.copy()
    e["sinal"] = np.where(e["efeito"] >= 0, "ajuda", "atrapalha")
    e["efeito_pct"] = e["efeito"] * 100
    multi = e["conta"].nunique() > 1
    cor = (alt.Color("conta:N", scale=alt.Scale(domain=list(cores), range=list(cores.values())), title=None)
           if multi else alt.Color("sinal:N", scale=alt.Scale(domain=["ajuda", "atrapalha"],
                                                              range=["#2E9E6A", "#D1495B"]), legend=None))
    enc = dict(y=alt.Y("característica:N", sort=alt.EncodingSortField("efeito", order="descending"), title=None),
               x=alt.X("efeito_pct:Q", title="efeito no engajamento (%) — vídeos COM vs SEM"),
               color=cor, opacity=alt.condition("datum['vídeos com'] >= 5", alt.value(1), alt.value(.45)),
               tooltip=["conta", "característica", alt.Tooltip("vídeos com:Q"),
                        alt.Tooltip("efeito_pct:Q", format="+.0f", title="efeito %"), "confiança"])
    if multi:
        enc["yOffset"] = "conta:N"
    return alt.Chart(e).mark_bar().encode(**enc).properties(height=max(260, 24 * e["característica"].nunique() * (2 if multi else 1)))


# ======================================================== blocos de tela
def bloco_kpis(r: dict) -> None:
    c = st.columns(6)
    c[0].metric("Seguidores", fmt(r["seguidores"]))
    c[1].metric("Vídeos válidos", f"{r['videos_validos']}/{r['videos_coletados']}")
    c[2].metric("Vídeo típico", f"{fmt(r['mediana_interacoes'])} interações",
                help="Mediana de curtidas + comentários por vídeo")
    c[3].metric("Engaj. por 1.000 seg.", fmt(r["eng_mil_seg"], 2),
                help="Interações do vídeo típico a cada 1.000 seguidores")
    c[4].metric("Posts por semana", fmt(r["posts_semana"], 1))
    c[5].metric("Tendência recente", pct(r["tendencia"]),
                help=f"Mediana dos {r.get('tendencia_k', 10)} vídeos mais recentes vs. os {r.get('tendencia_k', 10)} anteriores")


def avisos_qualidade(df: pd.DataFrame) -> None:
    inval = int((~df["valido"]).sum())
    susp = int(df["data_suspeita"].sum())
    sem_leg = int((df["valido"] & ~df["legenda_propria"]).sum())
    partes = []
    if inval:
        partes.append(f"**{inval}** vídeo(s) o Kwai não entregou mesmo após novas tentativas (ficam fora das análises)")
    if susp:
        partes.append(f"**{susp}** com data incoerente com a posição na grade (fora das análises de data)")
    if sem_leg:
        partes.append(f"**{sem_leg}** sem legenda própria (fora da análise de legendas)")
    if partes:
        st.caption("ℹ️ Qualidade dos dados: " + " · ".join(partes) + ".")


def tabela_fora_da_curva(df: pd.DataFrame, n: int = 10) -> None:
    v = df[df["valido"]].sort_values("interacoes", ascending=False).head(n)
    t = v[["conta", "data", "interacoes", "indice", "coment_por_100_curtidas", "legenda", "link"]].copy()
    t["legenda"] = t["legenda"].where(t["legenda"].ne(""), "(sem legenda própria)").str.slice(0, 110)
    st.dataframe(t, hide_index=True, width="stretch", column_config={
        "conta": "conta", "data": st.column_config.DateColumn("data", format="DD/MM/YYYY"),
        "interacoes": st.column_config.NumberColumn("interações", format="%d"),
        "indice": st.column_config.NumberColumn("× vídeo típico", format="%.1f×"),
        "coment_por_100_curtidas": st.column_config.NumberColumn("coment./100 curt.", format="%.1f"),
        "link": st.column_config.LinkColumn("vídeo", display_text="abrir ↗")})


def bloco_quando(df: pd.DataFrame, cores: dict) -> None:
    c1, c2, c3 = st.columns(3)
    for coluna, (col, ordem, titulo) in zip((c1, c2, c3), (
            ("dia_semana", A.DIAS, "Dia da semana"),
            ("faixa_horario", A.FAIXAS_HORA, "Horário"),
            ("periodo_mes", ["início (1–10)", "meio (11–20)", "fim (21–31)"], "Período do mês"))):
        g = A.por_grupo(df, col, ordem)
        with coluna:
            if g.empty:
                st.info(f"{titulo}: o Kwai não informou")
            else:
                g[col] = g[col].astype(str)
                st.altair_chart(grafico_grupo(g, col, ordem, cores, titulo), width="stretch")


def bloco_legendas(df: pd.DataFrame, cor: str, chave: str) -> None:
    L = df[df["valido"] & df["legenda_propria"]]
    if len(L) < 6:
        st.info("Poucas legendas próprias para analisar (precisa de pelo menos 6).")
        return
    ef = A.efeitos_legenda(df)
    st.markdown(f"Analisadas **{len(L)}** legendas. *Efeito* = quanto o vídeo típico **com** a característica engaja "
                "a mais (ou a menos) que o vídeo típico **sem** ela. Barras claras = poucos vídeos, leia com cautela.")
    if len(ef):
        ef["conta"] = df["conta"].iloc[0]
        st.altair_chart(grafico_efeitos(ef, {df['conta'].iloc[0]: cor}), width="stretch")

    c1, c2, c3 = st.columns(3)
    for coluna, (col, titulo) in zip((c1, c2, c3), (("categoria_principal", "Tipo de conteúdo"),
                                                    ("gancho", "Como a legenda começa"), ("tom", "Tom"))):
        with coluna:
            st.markdown(f"**{titulo}**")
            st.dataframe(A.tabela_categorica(df, col), hide_index=True, width="stretch",
                         column_config={"índice": st.column_config.NumberColumn(format="%.2f"),
                                        "conversa": st.column_config.NumberColumn("coment./100", format="%.1f")})

    pal = A.palavras(df)
    if len(pal):
        c1, c2, c3 = st.columns(3)
        cfg = {"índice": st.column_config.NumberColumn(format="%.2f"),
               "conversa": st.column_config.NumberColumn("coment./100", format="%.1f"),
               "vs geral": st.column_config.NumberColumn(format="percent")}
        c1.markdown("**🔥 Palavras que puxam engajamento**")
        c1.dataframe(pal.sort_values("índice", ascending=False).head(10), hide_index=True, width="stretch", column_config=cfg)
        c2.markdown("**🧊 Palavras que esfriam**")
        c2.dataframe(pal.sort_values("índice").head(10), hide_index=True, width="stretch", column_config=cfg)
        c3.markdown("**💬 Palavras que puxam comentário**")
        c3.dataframe(pal.sort_values("conversa", ascending=False).head(10), hide_index=True, width="stretch", column_config=cfg)

    tm = A.temas(df)
    if len(tm):
        st.markdown("**Temas descobertos automaticamente** (agrupamento das legendas por vocabulário)")
        st.dataframe(tm, hide_index=True, width="stretch",
                     column_config={"índice": st.column_config.NumberColumn(format="%.2f"),
                                    "conversa": st.column_config.NumberColumn("coment./100", format="%.1f")})

    st.markdown("#### 🧪 Simulador de legenda")
    texto = st.text_area("Escreva uma legenda nova e veja o que ela tem que costuma funcionar nesta conta",
                         "Você sabia? Últimos dias para garantir o seu! Link na bio 👇", key=f"sim_{chave}")
    if texto.strip():
        r = A.testar_legenda(texto, ef)
        st.write(f"Gancho: **{r['gancho']}**")
        for nome, e in r["tem"]:
            icone = "✅" if e > 0.1 else "⚠️" if e < -0.1 else "➖"
            st.write(f"{icone} {nome}: {pct(e)}")
        for nome, e in r["sugestoes"]:
            st.write(f"💡 Considere: {nome} ({pct(e)})")
        st.caption("Indicativo: são correlações nos vídeos analisados, não garantia de resultado.")


def bloco_dados(df: pd.DataFrame, nome_arquivo: str, chave: str) -> None:
    st.download_button("⬇️ Baixar CSV tratado e rotulado", A.para_csv(df), file_name=nome_arquivo,
                       mime="text/csv", type="primary", key=f"dl_{chave}", width="stretch")
    st.caption("CSV com `;` e vírgula decimal (abre direto no Excel em português). Uma linha por vídeo, "
               "com as métricas, os campos de data, os rótulos da legenda (sim/não) e as marcações de qualidade.")
    cols = [c for c in A.COLUNAS_CSV if c in df.columns]
    st.dataframe(df[cols], hide_index=True, width="stretch", height=360,
                 column_config={"link": st.column_config.LinkColumn("link", display_text="abrir ↗")})


def relatorio_perfil(df: pd.DataFrame, info: dict, chave: str) -> None:
    r = A.resumo(df)
    conta = r["conta"]
    cores = {conta: config.COR_A}
    st.subheader(f"@{conta}" + (f" · {info['nome']}" if info.get("nome") else ""))
    st.caption(f"{data_br(r['inicio'])} a {data_br(r['fim'])} · coletado em {info.get('coletado_em', '–')} "
               f"({info.get('segundos', '–')}s) · [abrir perfil ↗]({info.get('url')})")
    bloco_kpis(r)
    avisos_qualidade(df)

    abas = st.tabs(["📈 Desempenho", "🕐 Quando postar", "✍️ Legendas", "🗂️ Dados e CSV"])
    with abas[0]:
        if df["data_ok"].sum() >= 2:
            st.altair_chart(grafico_linha_tempo(df, cores), width="stretch")
        c1, c2 = st.columns(2)
        c1.markdown("**Ritmo**")
        c1.write(f"Intervalo típico entre posts: **{fmt(r['intervalo_mediano'], 1)} dia(s)** · "
                 f"maior pausa: **{fmt(r['maior_pausa'])} dias**")
        c1.write(f"Conversa: **{fmt(r['coment_100_curtidas'], 1)}** comentários a cada 100 curtidas")
        c2.markdown("**Vídeos fora da curva**")
        c2.write(f"**{pct(r['pct_fora_da_curva'], False)}** dos vídeos tiveram 2× ou mais o engajamento do vídeo típico.")
        st.markdown("**Top 10 vídeos**")
        tabela_fora_da_curva(df)
    with abas[1]:
        for f in A.recomendacoes_quando(df):
            st.markdown("• " + f)
        bloco_quando(df, cores)
        st.caption("Índice 1,0 = vídeo típico da conta. Usa a mediana para que um viral isolado não distorça o resultado.")
    with abas[2]:
        bloco_legendas(df, config.COR_A, chave)
    with abas[3]:
        bloco_dados(df, f"kwai_{conta}_{datetime.now(FUSO_BR):%Y-%m-%d}.csv", chave)


# ========================================================= competição
def placar(ra: dict, rb: dict) -> pd.DataFrame:
    itens = [("Seguidores", "seguidores", 0, True), ("Vídeo típico (interações)", "mediana_interacoes", 0, True),
             ("Engajamento por 1.000 seguidores", "eng_mil_seg", 2, True), ("Posts por semana", "posts_semana", 1, True),
             ("Comentários a cada 100 curtidas", "coment_100_curtidas", 1, True),
             ("% de vídeos fora da curva", "pct_fora_da_curva", None, True),
             ("Tendência recente", "tendencia", None, True), ("Maior pausa sem postar (dias)", "maior_pausa", 0, False)]
    linhas = []
    for rotulo, k, casas, maior_melhor in itens:
        a, b = ra.get(k), rb.get(k)
        f = (lambda x: pct(x, k == "tendencia")) if casas is None else (lambda x, c=casas: fmt(x, c))
        venc = "–"
        if a is not None and b is not None and not (pd.isna(a) or pd.isna(b)) and a != b:
            venc = "@" + (ra["conta"] if (a > b) == maior_melhor else rb["conta"])
        linhas.append({"indicador": rotulo, f"@{ra['conta']}": f(a), f"@{rb['conta']}": f(b), "vantagem": venc})
    return pd.DataFrame(linhas)


def aba_competicao(max_videos: int) -> None:
    st.markdown("Coloque **dois perfis** para comparar lado a lado. Os índices são relativos ao vídeo típico de cada conta, "
                "então dá para comparar contas de tamanhos diferentes.")
    c1, c2 = st.columns(2)
    pa = c1.text_input("Perfil A", placeholder="https://www.kwai.com/@marcaA", key="comp_a")
    pb = c2.text_input("Perfil B (concorrente)", placeholder="https://www.kwai.com/@marcaB", key="comp_b")
    if st.button("⚔️ Comparar", type="primary", disabled=not (pa and pb)):
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
        st.warning("Os dois links são do mesmo perfil.")
        return
    ra, rb = A.resumo(da), A.resumo(db)
    cores = {ra["conta"]: config.COR_A, rb["conta"]: config.COR_B}
    df = pd.concat([da, db], ignore_index=True)

    st.markdown("### Placar")
    col_p, col_r = st.columns([3, 2])
    with col_p:
        st.dataframe(placar(ra, rb), hide_index=True, width="stretch")
    with col_r:
        for r, info in ((ra, ia), (rb, ib)):
            st.markdown(f"<span style='color:{cores[r['conta']]};font-weight:700'>● @{r['conta']}</span> — "
                        f"{r['videos_validos']} vídeos válidos, {data_br(r['inicio'])} a {data_br(r['fim'])}",
                        unsafe_allow_html=True)
            for f in A.recomendacoes_quando(df[df["conta"] == r["conta"]])[:2]:
                st.caption(f)

    abas = st.tabs(["📈 Desempenho", "🕐 Quando postar", "✍️ Legendas", "🏆 Top vídeos", "🗂️ Dados e CSV"])
    with abas[0]:
        st.altair_chart(grafico_linha_tempo(df, cores), width="stretch")
        st.caption("Pontos = vídeos (clique para abrir) · linha = mediana móvel de 7 vídeos.")
    with abas[1]:
        bloco_quando(df, cores)
        st.caption("Índice 1,0 = vídeo típico de cada conta.")
    with abas[2]:
        efs = []
        for d in (da, db):
            e = A.efeitos_legenda(d)
            if len(e):
                e["conta"] = d["conta"].iloc[0]
                efs.append(e)
        if efs:
            st.markdown("O que nas legendas acompanha mais engajamento **em cada conta**:")
            st.altair_chart(grafico_efeitos(pd.concat(efs), cores), width="stretch")
        else:
            st.info("Poucas legendas próprias para comparar.")
        c1, c2 = st.columns(2)
        for col, d in ((c1, da), (c2, db)):
            with col:
                st.markdown(f"**@{d['conta'].iloc[0]} · tipo de conteúdo**")
                st.dataframe(A.tabela_categorica(d, "categoria_principal"), hide_index=True, width="stretch",
                             column_config={"índice": st.column_config.NumberColumn(format="%.2f"),
                                            "conversa": st.column_config.NumberColumn("coment./100", format="%.1f")})
                top = A.palavras_top(d)
                if top:
                    st.caption("Palavras dos 25% que mais engajam: " + ", ".join(f"{w} ({n})" for w, n in top))
    with abas[3]:
        c1, c2 = st.columns(2)
        for col, d in ((c1, da), (c2, db)):
            with col:
                st.markdown(f"**@{d['conta'].iloc[0]}**")
                tabela_fora_da_curva(d, 8)
    with abas[4]:
        bloco_dados(df, f"kwai_competicao_{ra['conta']}_x_{rb['conta']}_{datetime.now(FUSO_BR):%Y-%m-%d}.csv", "comp")


# ================================================================== tela
with st.sidebar:
    st.markdown("### ⚙️ Configurações")
    max_videos = st.slider("Vídeos mais recentes por perfil", 30, 300, config.MAX_VIDEOS_PADRAO, 10,
                           help="Mais vídeos = análise mais confiável, mas a coleta demora mais (≈1 min a cada 100).")
    if st.button("Limpar dados em memória"):
        st.session_state.pop("coletas", None)
        st.session_state.pop("comp_ok", None)
        st.rerun()
    st.divider()
    st.caption("Lê somente dados públicos exibidos nas páginas do Kwai. "
               "Os números podem diferir do app por arredondamento ou por limitações do site.")

aba1, aba2, aba3 = st.tabs(["🔍 Analisar perfil", "⚔️ Competição", "ℹ️ Como funciona"])

with aba1:
    c1, c2 = st.columns([4, 1])
    perfil = c1.text_input("Link do perfil do Kwai", placeholder="https://www.kwai.com/@Embelleze",
                           label_visibility="collapsed")
    if c2.button("Analisar", type="primary", width="stretch", disabled=not perfil):
        st.session_state["perfil_ok"] = perfil
    if "perfil_ok" in st.session_state:
        res = obter(st.session_state["perfil_ok"], max_videos)
        if res:
            relatorio_perfil(*res, chave="perfil")
    else:
        st.info("Cole o link de qualquer perfil público do Kwai (ou só o @) e clique em **Analisar**.")

with aba2:
    aba_competicao(max_videos)

with aba3:
    st.markdown("""
**Como os dados são coletados**
1. Um navegador invisível abre o perfil e rola a grade de vídeos para pegar os links.
2. A página pública de cada vídeo é lida (4 ao mesmo tempo): curtidas, comentários, legenda, data, hora e duração.
3. Quando o Kwai devolve uma página genérica, o app tenta de novo até 3 vezes. O que não vier fica marcado como inválido.

**Como os dados são tratados**
- **Interações** = curtidas + comentários.
- **Índice** = interações do vídeo ÷ mediana da conta. 1,0 = vídeo típico; 2,0 = o dobro. Permite comparar contas de tamanhos diferentes.
- **Data suspeita**: a grade vem do mais novo ao mais antigo. Se a data lida de um vídeo foge mais de 45 dias da dos vizinhos na grade, ela é descartada das análises de tempo (o vídeo continua nas demais).
- **Legenda própria**: quando o vídeo não tem legenda, o Kwai mostra só "N curtidas, N comentários". Esses vídeos ficam fora da análise de texto.
- **Rótulos da legenda**: pergunta, chamada para ação, urgência, preço, contato, "você", "nós", emoji, hashtag, exclamação, maiúsculas, 8 categorias de conteúdo, gancho (como começa) e tom.

**Como ler**
Tudo usa **mediana** (um viral isolado não distorce). Os efeitos são correlações: mostram o que acompanha o engajamento, não garantem causa.
""")

st.markdown(f"<div class='rodape'>{config.NOME_APP} · desenvolvido por <b>{config.AUTOR}</b> em {config.CRIADO_EM}"
            + (f" · {config.CONTATO_AUTOR}" if config.CONTATO_AUTOR else "")
            + f" · {' & '.join(l['nome'] for l in config.LOGOS)}</div>", unsafe_allow_html=True)
