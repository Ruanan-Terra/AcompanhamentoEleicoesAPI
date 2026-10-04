"""Componentes e dados compartilhados pelas páginas."""
import json
import unicodedata
from datetime import datetime
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

import config
from parser import Candidato, Resultado, parse, parse_andamento
from tse_client import NaoDivulgado, buscar, url_andamento, url_foto, url_resultado

# Cores que dependem do tema: (claro, escuro). São escolhidas a cada execução, não na importação do módulo,
# porque o ui.py é importado uma vez por processo e cada visitante pode estar num tema diferente.
TINTA_SECUNDARIA = ("#52514e", "#c3c2b7")
TINTA = ("#0b0b0b", "#ffffff")
FUNDO = ("#ffffff", "#0e1117")
RAMPA = (["#cde2fb", "#104281"], ["#0d366b", "#9ec5f4"])  # escala sequencial (azul)


def tom(par: tuple):
    """Escolhe a versão clara ou escura de uma cor, conforme o tema de quem está vendo."""
    return par[1] if st.context.theme.type == "dark" else par[0]


def cor(partido: str) -> str:
    return tom(config.CORES_PARTIDOS.get(partido, config.COR_OUTROS))


def fmt(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def pct(p: float) -> str:
    return f"{p:.2f}%".replace(".", ",")


def sem_acento(t: str) -> str:
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().upper()


# ---------- dados ----------

@st.cache_resource
def malha() -> dict:
    """Contorno das UFs (malha oficial do IBGE, pré-processada em assets/)."""
    return json.loads((Path(__file__).parent / "assets" / "br_uf.geojson").read_text(encoding="utf-8"))


@st.cache_data(ttl=config.INTERVALO_MIN_S, show_spinner="Consultando o TSE…")
def carregar(url: str) -> dict:
    # Erros também ficam em cache, para não repetir requisição antes de 60 s.
    try:
        dados, do_cache = buscar(url)
        return {"dados": dados, "do_cache": do_cache, "hora": datetime.now().strftime("%H:%M:%S")}
    except NaoDivulgado:
        return {"erro": "Resultado ainda não divulgado pelo TSE."}
    except ConnectionError as e:
        return {"erro": str(e)}


@st.cache_resource(ttl=config.MAPA_TTL_S, show_spinner="Carregando as 27 UFs…")
def resultados_por_uf(turno: int, cargo: str) -> dict[str, Resultado]:
    # ponytail: 27 GETs sequenciais por atualização; por isso o TTL de 5 min.
    res = {}
    for uf in config.UFS:
        try:
            dados, _ = buscar(url_resultado(turno, cargo, uf))
        except (NaoDivulgado, ConnectionError):
            continue  # UF sem arquivo (ex.: sem 2º turno) fica como "Sem dados"
        res[uf] = parse(dados)
    return res


def lider(r: Resultado) -> Candidato | None:
    return r.candidatos[0] if r.candidatos and r.candidatos[0].votos else None


# ---------- componentes ----------

def cabecalho(r: Resultado, consulta: dict, auto: bool):
    local = {"BR": "Brasil", "ZZ": "Exterior"}.get(r.abrangencia, r.abrangencia)
    st.markdown(f"## {r.cargo} · {local}" + (f" <small>({r.vagas} vagas)</small>" if r.vagas > 1 else ""), unsafe_allow_html=True)
    hora_tse = r.atualizacao.split(" ")[-1][:5] or "—"
    selo = "green" if auto else "gray"
    st.markdown(
        f":{selo}-badge[:material/schedule: Dados de {hora_tse}] "
        f":gray-badge[Atualização TSE: {r.atualizacao or '—'}] "
        f":gray-badge[Consultado às {consulta['hora']}]"
    )
    st.progress(
        min(r.pct_secoes / 100, 1.0),
        text=f"**{pct(r.pct_secoes)}** das seções totalizadas · {fmt(r.secoes_totalizadas)} de {fmt(r.secoes_total)}",
    )
    if consulta["do_cache"]:
        st.warning("Sem conexão com o TSE: exibindo a última cópia salva.", icon=":material/cloud_off:")


def barra(p: float, cor_hex: str):
    st.markdown(
        f'<div style="background:rgba(128,128,128,.18);border-radius:4px;height:8px;margin:-.25rem 0 .5rem">'
        f'<div style="width:{min(p, 100):.2f}%;background:{cor_hex};height:8px;border-radius:4px"></div></div>',
        unsafe_allow_html=True,
    )


def selo_situacao(c: Candidato):
    if c.eleito:
        st.badge(c.situacao or "Eleito", icon=":material/check_circle:", color="green")
    elif "2º" in c.situacao:
        st.badge(c.situacao, icon=":material/autorenew:", color="orange")
    elif c.situacao:
        st.badge(c.situacao, color="gray")


def cartoes(r: Resultado, turno: int, cargo: str):
    top = r.candidatos[: min(4, max(r.vagas + 1, 2))]
    for col, c in zip(st.columns(len(top) or 1), top):
        with col.container(border=True):
            foto, info = st.columns([1, 3], vertical_alignment="center", gap="small")
            if c.sqcand:
                foto.image(url_foto(turno, cargo, r.abrangencia, c.sqcand), width=64)
            info.markdown(f"**{c.nome}**  \n<small>{c.partido} · {c.numero}</small>", unsafe_allow_html=True)
            st.metric("% dos válidos", pct(c.pct_validos), f"{fmt(c.votos)} votos", delta_color="off", delta_arrow="off")
            barra(c.pct_validos, cor(c.partido))
            selo_situacao(c)


PLOTLY_CONFIG = {
    "displaylogo": False,
    "locale": "pt-BR",
    "toImageButtonOptions": {"format": "png", "scale": 2, "filename": "apuracao-2026"},
}


def _plotar(fig: go.Figure, altura: int, margem_direita: int = 0):
    fig.update_layout(
        height=altura,
        margin=dict(l=0, r=margem_direita, t=10, b=0),
        separators=",.",  # 1.234,56
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(align="left"),
    )
    st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)


def grafico_barras(cands: list[Candidato], rotulo_max: int = 240):
    """Barras horizontais por candidato. rotulo_max: largura aproximada (px) do nome no eixo."""
    limite = rotulo_max // 7
    nomes = [f"{c.nome} · {c.partido}" for c in cands]
    maior = max([c.pct_validos for c in cands] + [0.01])
    fig = go.Figure(go.Bar(
        x=[c.pct_validos for c in cands],
        y=[n if len(n) <= limite else n[: limite - 1] + "…" for n in nomes],
        orientation="h",
        marker=dict(color=[cor(c.partido) for c in cands], cornerradius=4),
        text=[pct(c.pct_validos) for c in cands],
        textposition="outside",
        textfont=dict(color=tom(TINTA_SECUNDARIA), size=11),
        cliponaxis=False,
        customdata=[[n, fmt(c.votos)] for n, c in zip(nomes, cands)],
        hovertemplate="<b>%{customdata[0]}</b><br>%{text} dos válidos<br>%{customdata[1]} votos<extra></extra>",
    ))
    # escala até o maior valor (+18% de folga para o rótulo); deputados têm ~0,2%, num eixo 0–100 sumiriam
    fig.update_xaxes(title="% dos votos válidos", range=[0, maior * 1.18], ticksuffix="%")
    fig.update_yaxes(autorange="reversed", ticks="", title=None)
    fig.update_layout(bargap=0.3, showlegend=False)
    _plotar(fig, 30 * len(cands) + 70, margem_direita=48)  # espaço para o rótulo da barra mais longa


def _estilo_ufs(ufs: list[str], destaque: set[str], esmaecer: bool) -> dict:
    """Opacidade e contorno por UF: realça o destaque (contorno se for uma UF só) e apaga o resto se esmaecer."""
    contorno = destaque if len(destaque) == 1 else set()
    tinta, fundo = tom(TINTA), tom(FUNDO)
    return dict(
        opacity=[0.22 if esmaecer and destaque and u not in destaque else 1.0 for u in ufs],
        line=dict(width=[2.5 if u in contorno else 0.8 for u in ufs],
                  color=[tinta if u in contorno else fundo for u in ufs]),
    )


def _plotar_mapa(fig: go.Figure, altura: int):
    fig.update_geos(fitbounds="locations", visible=False, projection_type="mercator", bgcolor="rgba(0,0,0,0)")
    fig.update_layout(legend=dict(orientation="h", x=0.5, xanchor="center", y=0, yanchor="top"), dragmode="pan")
    _plotar(fig, altura)


def mapa_categorias(cat: dict[str, str], cores: dict[str, str], hover: dict[str, str],
                    destaque: set[str] = frozenset(), esmaecer: bool = False, altura: int = 480):
    """Uma camada por categoria (partido), na ordem de `cores`: clicar na legenda esconde/mostra a camada."""
    fig = go.Figure()
    for nome, cor_hex in cores.items():
        ufs = [u for u in config.UFS if cat.get(u) == nome]
        if not ufs:
            continue
        # só os contornos desta camada: a malha inteira em cada camada multiplicaria o tamanho da página
        geo = {"type": "FeatureCollection", "features": [f for f in malha()["features"] if f["properties"]["uf"] in ufs]}
        fig.add_trace(go.Choropleth(
            geojson=geo, featureidkey="properties.uf", locations=ufs, z=[1] * len(ufs),
            colorscale=[[0, cor_hex], [1, cor_hex]], showscale=False, name=nome, showlegend=True,
            marker=_estilo_ufs(ufs, destaque, esmaecer),
            hovertext=[hover[u] for u in ufs], hovertemplate="%{hovertext}<extra></extra>",
        ))
    _plotar_mapa(fig, altura)


def mapa_valores(valores: dict[str, float], hover: dict[str, str], zmax: float, titulo: str,
                 destaque: set[str] = frozenset(), esmaecer: bool = False, altura: int = 480):
    """Escala sequencial (azul claro → escuro) de um valor por UF."""
    ufs = config.UFS
    rampa = tom(RAMPA)
    fig = go.Figure(go.Choropleth(
        geojson=malha(), featureidkey="properties.uf", locations=ufs, z=[valores.get(u, 0) for u in ufs],
        zmin=0, zmax=zmax, colorscale=[[0, rampa[0]], [1, rampa[1]]],
        colorbar=dict(title=dict(text=titulo, side="top"), orientation="h", x=0.5, y=-0.02, yanchor="top",
                      len=0.6, thickness=10, ticksuffix="%"),
        marker=_estilo_ufs(ufs, destaque, esmaecer),
        hovertext=[hover.get(u, f"<b>{u.upper()}</b><br>sem dados") for u in ufs],
        hovertemplate="%{hovertext}<extra></extra>",
    ))
    _plotar_mapa(fig, altura)


def mapa_lideres(res: dict[str, Resultado], destaque: set[str] = frozenset(), esmaecer: bool = False,
                 altura: int = 480):
    cat, hover = {}, {}
    for uf in config.UFS:
        r = res.get(uf)
        c = lider(r) if r else None
        if r is None:
            cat[uf], hover[uf] = "Sem dados", f"<b>{uf.upper()}</b><br>sem dados"
        elif c is None:
            cat[uf], hover[uf] = "Sem votos apurados", f"<b>{uf.upper()}</b><br>sem votos apurados"
        else:
            cat[uf] = c.partido if c.partido in config.CORES_PARTIDOS else "Outros"
            hover[uf] = (f"<b>{uf.upper()}</b> · {pct(r.pct_secoes)} apurado<br>"
                         f"Lidera: {c.nome} ({c.partido})<br>{pct(c.pct_validos)} dos válidos")
    cores = {**{p: cor(p) for p in config.CORES_PARTIDOS}, "Outros": tom(config.COR_OUTROS),
             "Sem votos apurados": tom(config.COR_SEM_DADOS), "Sem dados": tom(config.COR_SEM_DADOS)}
    mapa_categorias(cat, cores, hover, destaque, esmaecer, altura)


def mapa_desempenho(res: dict[str, Resultado], candidatos: list[Candidato], uf_sel: str | None):
    """% de um candidato em cada UF (só faz sentido para Presidente: mesmos candidatos em todo o país)."""
    nomes = {c.numero: f"{c.nome} ({c.partido})" for c in candidatos}
    numero = st.selectbox("Candidato", sorted(nomes, key=nomes.get), index=None, placeholder="Escolha o candidato",
                          format_func=nomes.get, key="cand_mapa", label_visibility="collapsed")
    numero = numero or candidatos[0].numero  # padrão: quem lidera no recorte atual
    valores, hover = {}, {}
    for uf, r in res.items():
        c = next((x for x in r.candidatos if x.numero == numero), None)
        if c:
            valores[uf] = c.pct_validos
            hover[uf] = f"<b>{uf.upper()}</b><br>{pct(c.pct_validos)} dos válidos<br>{fmt(c.votos)} votos"
    mapa_valores(valores, hover, max(list(valores.values()) + [0.01]), "% válidos", {uf_sel} if uf_sel else set())
    st.caption(f"Votação de {nomes[numero]} em cada UF · cor mais escura = maior percentual")


def tabela_estados(res: dict[str, Resultado], destaque: list[Candidato]):
    """Uma linha por UF: andamento, 1º e 2º colocados, vantagem e (Presidente) % dos principais candidatos."""
    linhas = []
    for uf in config.UFS:
        r = res.get(uf)
        linha = {"UF": uf.upper()}
        if r:
            c1, c2 = (r.candidatos + [None, None])[:2]
            com_votos = bool(c1 and c1.votos)
            linha |= {"Apurado": r.pct_secoes, "Lidera": f"{c1.nome} ({c1.partido})" if com_votos else "—"}
            if not destaque:  # com destaque (Presidente), as colunas por candidato já mostram 1º e 2º
                linha |= {
                    "% 1º": c1.pct_validos if com_votos else None,
                    "2º lugar": f"{c2.nome} ({c2.partido})" if com_votos and c2 else "—",
                    "% 2º": c2.pct_validos if com_votos and c2 else None,
                }
            linha["Vantagem (p.p.)"] = c1.pct_validos - c2.pct_validos if com_votos and c2 else None
            por_numero = {c.numero: c.pct_validos for c in r.candidatos}
            linha |= {f"% {c.nome}": por_numero.get(c.numero) for c in destaque}
        linhas.append(linha)
    pct_col = st.column_config.NumberColumn(format="%.2f%%")
    st.dataframe(
        linhas,
        hide_index=True,
        width="stretch",
        height=35 * (len(linhas) + 1) + 3,  # todas as UFs sem rolagem interna
        column_config={
            "Apurado": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100),
            "% 1º": pct_col, "% 2º": pct_col,
            "Vantagem (p.p.)": st.column_config.NumberColumn(format="%.2f", help="Diferença entre 1º e 2º, em pontos percentuais"),
            **{f"% {c.nome}": pct_col for c in destaque},
        },
    )


def mapa_andamento(turno: int, cargo: str, uf_sel: str | None):
    consulta = carregar(url_andamento(turno, cargo))
    if "erro" in consulta:
        st.info(consulta["erro"])
        return
    valores = parse_andamento(consulta["dados"])
    hover = {uf: f"<b>{uf.upper()}</b><br>{pct(p)} das seções totalizadas" for uf, p in valores.items()}
    mapa_valores(valores, hover, 100, "% seções", {uf_sel} if uf_sel else set())
    st.caption("Percentual de seções totalizadas em cada UF")


def totais(r: Resultado):
    st.markdown("#### Comparecimento e votos")
    t = st.columns(5)
    t[0].metric("Comparecimento", fmt(r.comparecimento), pct(r.pct_comparecimento), delta_color="off", delta_arrow="off", border=True)
    t[1].metric("Abstenção", fmt(r.abstencao), pct(r.pct_abstencao), delta_color="off", delta_arrow="off", border=True)
    t[2].metric("Válidos", fmt(r.validos), pct(r.pct_validos), delta_color="off", delta_arrow="off", border=True)
    t[3].metric("Brancos", fmt(r.brancos), pct(r.pct_brancos), delta_color="off", delta_arrow="off", border=True)
    t[4].metric("Nulos", fmt(r.nulos), pct(r.pct_nulos), delta_color="off", delta_arrow="off", border=True)
    st.caption(f"Eleitorado apto: {fmt(r.eleitorado)}")


def tabela(cands: list[Candidato]):
    st.dataframe(
        [
            {"Nº": c.numero, "Candidato": ("✅ " if c.eleito else "") + c.nome, "Partido": c.partido,
             "Votos": c.votos, "% válidos": c.pct_validos, "Situação": c.situacao}
            for c in cands
        ],
        hide_index=True,
        width="stretch",
        column_config={
            "Votos": st.column_config.NumberColumn(format="localized"),
            "% válidos": st.column_config.ProgressColumn(format="%.2f%%", min_value=0, max_value=100),
        },
    )
