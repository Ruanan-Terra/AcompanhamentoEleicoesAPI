import json
import unicodedata
from datetime import datetime
from pathlib import Path

import altair as alt
import streamlit as st

import config
from parser import Candidato, Resultado, parse, parse_andamento
from tse_client import NaoDivulgado, buscar, url_andamento, url_foto, url_resultado

st.set_page_config(page_title="Apuração 2026", page_icon="🗳️", layout="wide")

ESCURO = st.context.theme.type == "dark"
TINTA_SECUNDARIA = "#c3c2b7" if ESCURO else "#52514e"
FUNDO = "#0e1117" if ESCURO else "#ffffff"


def tom(par: tuple[str, str]) -> str:
    """Escolhe a versão clara ou escura de uma cor."""
    return par[1] if ESCURO else par[0]


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


def grafico_barras(cands: list[Candidato]):
    linhas = [
        {"nome": f"{c.nome} · {c.partido}", "pct": c.pct_validos, "rotulo": pct(c.pct_validos),
         "votos": fmt(c.votos), "cor": cor(c.partido)}
        for c in cands
    ]
    base = alt.Chart(alt.Data(values=linhas)).encode(
        y=alt.Y("nome:N", sort=None, title=None, axis=alt.Axis(labelLimit=240, ticks=False, domain=False)),
        # escala até o maior valor (+15% de folga para o rótulo); deputados têm ~0,2%, num eixo 0–100 sumiriam
        x=alt.X("pct:Q", title="% dos votos válidos",
                scale=alt.Scale(domain=[0, max([c.pct_validos for c in cands] + [0.01]) * 1.15])),
    )
    barras = base.mark_bar(cornerRadiusEnd=4, height={"band": 0.7}).encode(
        color=alt.Color("cor:N", scale=None),
        tooltip=[alt.Tooltip("nome:N", title="Candidato"), alt.Tooltip("rotulo:N", title="% válidos"),
                 alt.Tooltip("votos:N", title="Votos")],
    )
    rotulos = base.mark_text(align="left", dx=6, color=TINTA_SECUNDARIA).encode(text="rotulo:N")
    st.altair_chart((barras + rotulos).properties(height=alt.Step(30)), width="stretch")


def desenhar_mapa(props: dict[str, dict], padrao: dict, cor_enc, tooltip, uf_sel: str | None):
    feats = [
        {**f, "properties": {"uf": f["properties"]["uf"].upper(), **props.get(f["properties"]["uf"], padrao)}}
        for f in malha()["features"]
    ]
    sel = f"datum.properties.uf == '{(uf_sel or '').upper()}'"
    tinta = "#ffffff" if ESCURO else "#0b0b0b"
    grafico = (
        alt.Chart(alt.Data(values=feats))
        .mark_geoshape()
        .encode(
            color=cor_enc,
            tooltip=tooltip,
            stroke=alt.condition(sel, alt.value(tinta), alt.value(FUNDO)),
            strokeWidth=alt.condition(sel, alt.value(2.5), alt.value(0.8)),
        )
        .project("mercator")
        .properties(height=480)
    )
    st.altair_chart(grafico, width="stretch")


def mapa_lideres(res: dict[str, Resultado], uf_sel: str | None):
    props = {}
    for uf, r in res.items():
        c = lider(r)
        if c is None:
            props[uf] = {"legenda": "Sem votos apurados", "lider": "—", "pct": "—"}
        else:
            props[uf] = {"legenda": c.partido if c.partido in config.CORES_PARTIDOS else "Outros",
                         "lider": f"{c.nome} ({c.partido})", "pct": pct(c.pct_validos)}
    presentes = {p["legenda"] for p in props.values()} | ({"Sem dados"} if len(props) < len(config.UFS) else set())
    dominio = [p for p in [*config.CORES_PARTIDOS, "Outros", "Sem votos apurados", "Sem dados"] if p in presentes]
    cores = {**{p: cor(p) for p in config.CORES_PARTIDOS}, "Outros": tom(config.COR_OUTROS),
             "Sem votos apurados": tom(config.COR_SEM_DADOS), "Sem dados": tom(config.COR_SEM_DADOS)}
    desenhar_mapa(
        props,
        {"legenda": "Sem dados", "lider": "—", "pct": "—"},
        alt.Color("properties.legenda:N", scale=alt.Scale(domain=dominio, range=[cores[p] for p in dominio]),
                  legend=alt.Legend(title=None, orient="bottom", columns=5)),
        [alt.Tooltip("properties.uf:N", title="UF"), alt.Tooltip("properties.lider:N", title="Lidera"),
         alt.Tooltip("properties.pct:N", title="% válidos")],
        uf_sel,
    )
    st.caption(f"Partido de quem lidera em cada UF · atualiza a cada {config.MAPA_TTL_S // 60} min · "
               "detalhes na tabela \"Resultado por estado\"")


def mapa_desempenho(res: dict[str, Resultado], candidatos: list[Candidato], uf_sel: str | None):
    """% de um candidato em cada UF (só faz sentido para Presidente: mesmos candidatos em todo o país)."""
    nomes = {c.numero: f"{c.nome} ({c.partido})" for c in candidatos}
    numero = st.selectbox("Candidato", sorted(nomes, key=nomes.get), index=None, placeholder="Escolha o candidato",
                          format_func=nomes.get, key="cand_mapa", label_visibility="collapsed")
    numero = numero or candidatos[0].numero  # padrão: quem lidera no recorte atual
    props = {}
    for uf, r in res.items():
        c = next((x for x in r.candidatos if x.numero == numero), None)
        if c:
            props[uf] = {"pct": c.pct_validos, "rotulo": pct(c.pct_validos), "votos": fmt(c.votos)}
    maximo = max([p["pct"] for p in props.values()] + [0.01])
    rampa = ["#0d366b", "#9ec5f4"] if ESCURO else ["#cde2fb", "#104281"]
    desenhar_mapa(
        props,
        {"pct": 0, "rotulo": "—", "votos": "—"},
        alt.Color("properties.pct:Q", scale=alt.Scale(domain=[0, maximo], range=rampa),
                  legend=alt.Legend(title="% válidos", orient="bottom", gradientLength=260)),
        [alt.Tooltip("properties.uf:N", title="UF"), alt.Tooltip("properties.rotulo:N", title="% válidos"),
         alt.Tooltip("properties.votos:N", title="Votos")],
        uf_sel,
    )
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
    rampa = ["#0d366b", "#9ec5f4"] if ESCURO else ["#cde2fb", "#104281"]
    desenhar_mapa(
        {uf: {"pst": p, "rotulo": pct(p)} for uf, p in parse_andamento(consulta["dados"]).items()},
        {"pst": 0, "rotulo": "—"},
        alt.Color("properties.pst:Q", scale=alt.Scale(domain=[0, 100], range=rampa),
                  legend=alt.Legend(title="% seções", orient="bottom", gradientLength=260)),
        [alt.Tooltip("properties.uf:N", title="UF"), alt.Tooltip("properties.rotulo:N", title="Seções totalizadas")],
        uf_sel,
    )
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


# ---------- página ----------

with st.sidebar:
    st.markdown("### 🗳️ Apuração 2026")
    st.caption("Eleições gerais · dados oficiais do TSE")
    turno = st.radio("Turno", [1, 2], format_func=lambda t: f"{t}º turno", horizontal=True)
    opcoes = [c for c in config.CARGOS if c != "Deputado Distrital" and (turno == 1 or c in config.CARGOS_2T)]
    cargo = st.selectbox("Cargo", opcoes)
    uf = None
    if cargo == "Presidente":
        uf = st.selectbox("Abrangência", [None, *config.UFS, "zz"], key="abr_presidente",
                          format_func=lambda u: {None: "Brasil", "zz": "Exterior"}.get(u, u and u.upper()))
    elif config.CARGOS[cargo][2] is None:
        uf = st.selectbox("UF", config.UFS, index=config.UFS.index("rs"), format_func=str.upper)
    if cargo == "Deputado Estadual" and uf == "df":
        cargo = "Deputado Distrital"
    proporcional = cargo.startswith("Deputado")
    busca = sem_acento(st.text_input("Buscar candidato", placeholder="Nome ou número").strip()) if proporcional else ""
    st.divider()
    auto = st.toggle("Atualização automática", value=True)
    intervalo = st.slider("Intervalo (s)", config.INTERVALO_MIN_S, 600, config.INTERVALO_PADRAO_S, step=30, disabled=not auto)


@st.fragment(run_every=intervalo if auto else None)
def painel():
    consulta = carregar(url_resultado(turno, cargo, uf))
    if "erro" in consulta:
        st.info(consulta["erro"], icon=":material/hourglass_empty:")
        return
    r = parse(consulta["dados"])
    cabecalho(r, consulta, auto)
    if busca:
        r.candidatos = [c for c in r.candidatos if busca in sem_acento(c.nome) or c.numero.startswith(busca)]

    tem_votos = bool(r.candidatos) and r.candidatos[0].votos > 0
    if not proporcional and tem_votos:  # sem votos a ordem é alfabética: cartões dariam a falsa ideia de ranking
        cartoes(r, turno, cargo)

    esq, dir_ = st.columns([1.1, 1], gap="large")
    with esq:
        st.markdown("#### Mais votados" if proporcional else "#### Votos por candidato")
        if not tem_votos:
            st.caption("Aguardando os primeiros votos apurados (ordem alfabética).")
        grafico_barras(r.candidatos[:15])
    with dir_:
        st.markdown("#### Mapa")
        if proporcional:
            mapa_andamento(turno, cargo, uf)
        else:
            modos = ["Quem lidera", "Desempenho", "Andamento"] if cargo == "Presidente" else ["Quem lidera", "Andamento"]
            modo = st.segmented_control("Modo do mapa", modos, default="Quem lidera",
                                        key="modo_mapa", label_visibility="collapsed")
            if modo == "Andamento":
                mapa_andamento(turno, cargo, uf)
            elif modo == "Desempenho" and r.candidatos:
                mapa_desempenho(resultados_por_uf(turno, cargo), r.candidatos, uf)
            else:
                mapa_lideres(resultados_por_uf(turno, cargo), uf)

    if not proporcional:
        st.divider()
        st.markdown("#### Resultado por estado")
        st.caption(f"Clique no cabeçalho de uma coluna para ordenar · atualiza a cada {config.MAPA_TTL_S // 60} min")
        # Presidente: colunas com o % dos 4 primeiros do recorte atual em cada UF
        tabela_estados(resultados_por_uf(turno, cargo), r.candidatos[:4] if cargo == "Presidente" and tem_votos else [])

    st.divider()
    totais(r)
    with st.expander(f"Todos os candidatos ({len(r.candidatos)})", expanded=proporcional):
        tabela(r.candidatos)


painel()
st.caption("Fonte: Divulgação de Resultados do TSE (resultados.tse.jus.br) · contorno dos estados: IBGE")
