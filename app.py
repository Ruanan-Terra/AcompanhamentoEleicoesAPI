from collections import Counter

import streamlit as st

import config
import ui
from parser import Resultado, agregar, parse
from tse_client import url_resultado

st.set_page_config(page_title="Apuração 2026", page_icon="🗳️", layout="wide")


# ---------- página: visão geral (one page) ----------

def placar(res: dict[str, Resultado], ufs: list[str]):
    """Quantas UFs do recorte cada partido lidera, com a cor do partido."""
    contagem = Counter(c.partido for u in ufs if u in res and (c := ui.lider(res[u])))
    if not contagem:
        st.caption("Aguardando os primeiros votos apurados.")
        return
    itens = " &nbsp; ".join(f'<span style="color:{ui.cor(p)}">●</span> {p} <b>{n}</b>' for p, n in contagem.most_common())
    st.markdown(f"<small>Lidera em: {itens}</small>", unsafe_allow_html=True)


def resumo_estadual(res: dict[str, Resultado], ufs: list[str], uf: str | None):
    """Governador/Senado: ranking da UF escolhida ou, num recorte maior, quem lidera em cada UF."""
    if uf:
        r = res.get(uf)
        if r is None:
            st.info("Sem dados para esta UF.")
            return
        ui.grafico_barras(r.candidatos[:5], rotulo_max=130)
        st.caption(f"{ui.pct(r.pct_secoes)} das seções" + (f" · {r.vagas} vagas" if r.vagas > 1 else ""))
        return
    placar(res, ufs)
    linhas = []
    for u in ufs:
        r = res.get(u)
        top = [c for c in (r.candidatos[:2] if r else []) if c.votos]
        rotulos = [f"{c.nome} ({c.partido}) {ui.pct(c.pct_validos)}" for c in top] + ["—", "—"]
        # Senado (2 vagas): 1º e 2º em colunas separadas; Governador: só quem lidera
        linhas.append({"UF": u.upper(), "1º": rotulos[0], "2º": rotulos[1]} if r and r.vagas > 1
                      else {"UF": u.upper(), "Lidera": rotulos[0]})
    st.dataframe(linhas, hide_index=True, width="stretch", height=min(35 * (len(linhas) + 1) + 3, 400))


def visao_geral():
    st.markdown("## Visão geral")
    regiao = st.segmented_control("Região", ["Brasil", *config.REGIOES], default="Brasil", key="vg_regiao") or "Brasil"
    ufs = config.UFS if regiao == "Brasil" else config.REGIOES[regiao]
    # key por região: ao trocar de região a seleção de estado recomeça
    uf = st.pills("Estado", ufs, format_func=str.upper, key=f"vg_uf_{regiao}")
    destaque = {uf} if uf else (set(ufs) if regiao != "Brasil" else set())
    nome = uf.upper() if uf else regiao

    @st.fragment(run_every=REFRESH)
    def conteudo():
        pres = ui.resultados_por_uf(turno, "Presidente")
        if uf:
            r = pres.get(uf)
        elif regiao == "Brasil":  # arquivo nacional: inclui o exterior e atualiza a cada 60 s
            consulta = ui.carregar(url_resultado(turno, "Presidente", None))
            r = parse(consulta["dados"]) if "erro" not in consulta else None
        else:
            r = agregar([pres[u] for u in ufs if u in pres], regiao) if pres else None
        if r is None:
            st.info("Resultado ainda não divulgado pelo TSE.", icon=":material/hourglass_empty:")
            return

        st.markdown(f"### {nome}")
        st.markdown(f":gray-badge[:material/schedule: Dados de {r.atualizacao.split(' ')[-1][:5] or '—'}] "
                    f":gray-badge[Presidente: {ui.pct(r.pct_secoes)} das seções totalizadas]")
        st.progress(min(r.pct_secoes / 100, 1.0))
        k = st.columns(4)
        k[0].metric("Eleitorado", ui.fmt(r.eleitorado), border=True)
        k[1].metric("Comparecimento", ui.fmt(r.comparecimento), ui.pct(r.pct_comparecimento), delta_color="off", delta_arrow="off", border=True)
        k[2].metric("Abstenção", ui.fmt(r.abstencao), ui.pct(r.pct_abstencao), delta_color="off", delta_arrow="off", border=True)
        k[3].metric("Brancos e nulos", ui.fmt(r.brancos + r.nulos), ui.pct(r.pct_brancos + r.pct_nulos), delta_color="off", delta_arrow="off", border=True)

        cargos = [("Presidente", pres), ("Governador", ui.resultados_por_uf(turno, "Governador"))]
        if turno == 1:
            cargos.append(("Senado", ui.resultados_por_uf(1, "Senador")))
        for col, (titulo, res) in zip(st.columns(len(cargos), gap="medium"), cargos):
            with col, st.container(border=True):
                st.markdown(f"#### {titulo}")
                ui.mapa_lideres(res, destaque, esmaecer=True, altura=320)
                if titulo == "Presidente":
                    st.markdown(f"**Mais votados · {nome}**")
                    ui.grafico_barras(r.candidatos[:5], rotulo_max=130)
                else:
                    resumo_estadual(res, ufs, uf)
        st.caption(f"Mapas: partido de quem lidera em cada UF · atualizam a cada {config.MAPA_TTL_S // 60} min · "
                   "UFs fora do filtro ficam esmaecidas")

        if turno == 1:
            st.divider()
            if not uf:
                st.caption("Escolha um estado para ver os deputados mais votados.")
                return
            st.markdown(f"#### Deputados mais votados · {uf.upper()}")
            estadual = "Deputado Distrital" if uf == "df" else "Deputado Estadual"
            for col, cargo in zip(st.columns(2, gap="large"), ("Deputado Federal", estadual)):
                with col:
                    st.markdown(f"**{cargo}**")
                    consulta = ui.carregar(url_resultado(1, cargo, uf))
                    if "erro" in consulta:
                        st.info(consulta["erro"])
                        continue
                    rd = parse(consulta["dados"])
                    ui.grafico_barras(rd.candidatos[:10], rotulo_max=220)
                    st.caption(f"{rd.vagas} vagas · detalhes e busca no Painel detalhado")

    conteudo()


# ---------- página: painel detalhado ----------

def painel_detalhado():
    with filtros:
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
        busca = ui.sem_acento(st.text_input("Buscar candidato", placeholder="Nome ou número").strip()) if proporcional else ""

    @st.fragment(run_every=REFRESH)
    def conteudo():
        consulta = ui.carregar(url_resultado(turno, cargo, uf))
        if "erro" in consulta:
            st.info(consulta["erro"], icon=":material/hourglass_empty:")
            return
        r = parse(consulta["dados"])
        ui.cabecalho(r, consulta, auto)
        if busca:
            r.candidatos = [c for c in r.candidatos if busca in ui.sem_acento(c.nome) or c.numero.startswith(busca)]

        tem_votos = bool(r.candidatos) and r.candidatos[0].votos > 0
        if not proporcional and tem_votos:  # sem votos a ordem é alfabética: cartões dariam a falsa ideia de ranking
            ui.cartoes(r, turno, cargo)

        esq, dir_ = st.columns([1.1, 1], gap="large")
        with esq:
            st.markdown("#### Mais votados" if proporcional else "#### Votos por candidato")
            if not tem_votos:
                st.caption("Aguardando os primeiros votos apurados (ordem alfabética).")
            ui.grafico_barras(r.candidatos[:15])
        with dir_:
            st.markdown("#### Mapa")
            if proporcional:
                ui.mapa_andamento(turno, cargo, uf)
            else:
                modos = ["Quem lidera", "Desempenho", "Andamento"] if cargo == "Presidente" else ["Quem lidera", "Andamento"]
                modo = st.segmented_control("Modo do mapa", modos, default="Quem lidera",
                                            key="modo_mapa", label_visibility="collapsed")
                if modo == "Andamento":
                    ui.mapa_andamento(turno, cargo, uf)
                elif modo == "Desempenho" and r.candidatos:
                    ui.mapa_desempenho(ui.resultados_por_uf(turno, cargo), r.candidatos, uf)
                else:
                    ui.mapa_lideres(ui.resultados_por_uf(turno, cargo), {uf} if uf else set())
                    st.caption(f"Partido de quem lidera em cada UF · atualiza a cada {config.MAPA_TTL_S // 60} min · "
                               "detalhes na tabela \"Resultado por estado\"")

        if not proporcional:
            st.divider()
            st.markdown("#### Resultado por estado")
            st.caption(f"Clique no cabeçalho de uma coluna para ordenar · atualiza a cada {config.MAPA_TTL_S // 60} min")
            # Presidente: colunas com o % dos 4 primeiros do recorte atual em cada UF
            ui.tabela_estados(ui.resultados_por_uf(turno, cargo), r.candidatos[:4] if cargo == "Presidente" and tem_votos else [])

        st.divider()
        ui.totais(r)
        with st.expander(f"Todos os candidatos ({len(r.candidatos)})", expanded=proporcional):
            ui.tabela(r.candidatos)

    conteudo()


# ---------- navegação e barra lateral comum ----------

pagina = st.navigation([
    st.Page(visao_geral, title="Visão geral", icon=":material/dashboard:"),
    st.Page(painel_detalhado, title="Painel detalhado", icon=":material/insights:"),
])
with st.sidebar:
    st.markdown("### 🗳️ Apuração 2026")
    st.caption("Eleições gerais · dados oficiais do TSE")
    turno = st.radio("Turno", [1, 2], format_func=lambda t: f"{t}º turno", horizontal=True)
    filtros = st.container()  # cada página coloca aqui os seus filtros
    st.divider()
    auto = st.toggle("Atualização automática", value=True)
    intervalo = st.slider("Intervalo (s)", config.INTERVALO_MIN_S, 600, config.INTERVALO_PADRAO_S, step=30, disabled=not auto)
REFRESH = intervalo if auto else None

pagina.run()
st.caption("Fonte: Divulgação de Resultados do TSE (resultados.tse.jus.br) · contorno dos estados: IBGE")
