from functools import partial

import streamlit as st

import config
import ui
from parser import Resultado, agregar, parse
from tse_client import url_resultado

st.set_page_config(page_title="Apuração 2026", page_icon="🗳️", layout="wide")


# ---------- página: visão geral (one page) ----------
# Um "recorte" é ("brasil", None), ("regiao", "Nordeste") ou ("uf", "ba").

REGIAO_DA_UF = {u: r for r, ufs in config.REGIOES.items() for u in ufs}
# Filtro de cada card: cada região seguida dos seus estados (o dropdown aceita busca digitando)
OPCOES_CARD = ["geral", "brasil"] + [o for r, ufs in config.REGIOES.items() for o in (f"r:{r}", *(f"uf:{u}" for u in ufs))]


def para_recorte(opcao: str) -> tuple[str, str | None]:
    if opcao.startswith("r:"):
        return ("regiao", opcao[2:])
    if opcao.startswith("uf:"):
        return ("uf", opcao[3:])
    return ("brasil", None)


def nome_recorte(rec: tuple[str, str | None]) -> str:
    tipo, valor = rec
    if tipo == "uf":
        return config.NOMES_UF[valor]
    return valor if tipo == "regiao" else "Brasil"


def ufs_recorte(rec: tuple[str, str | None]) -> list[str]:
    tipo, valor = rec
    return [valor] if tipo == "uf" else config.REGIOES[valor] if tipo == "regiao" else config.UFS


def rotulo_opcao(opcao: str) -> str:
    if opcao == "geral":  # texto fixo: o rótulo de uma opção não se atualiza num widget já criado
        return "↺ Seguir filtro geral"
    tipo, valor = para_recorte(opcao)
    if tipo == "uf":
        return f"\u2003\u2003{config.NOMES_UF[valor]} ({valor.upper()})"  # recuado: estado dentro da região
    return f"{valor.upper()} · região" if tipo == "regiao" else "Brasil"


def presidente_no_recorte(rec: tuple[str, str | None], pres: dict[str, Resultado]) -> Resultado | None:
    tipo, valor = rec
    if tipo == "uf":
        return pres.get(valor)
    if tipo == "regiao":
        rs = [pres[u] for u in config.REGIOES[valor] if u in pres]
        return agregar(rs, valor) if rs else None
    consulta = ui.carregar(url_resultado(turno, "Presidente", None))  # nacional: inclui o exterior
    return parse(consulta["dados"]) if "erro" not in consulta else None


def apurado(res: dict[str, Resultado], ufs: list[str]) -> float:
    total = sum(res[u].secoes_total for u in ufs if u in res)
    return 100 * sum(res[u].secoes_totalizadas for u in ufs if u in res) / total if total else 0.0


def definir(chave: str, valor):
    st.session_state[chave] = valor


def abrir_uf(chave_tabela: str, ufs_linhas: list[str], chave_card: str):
    """Clique numa linha da lista de estados (na caixinha ou em qualquer célula): o card abre aquele estado."""
    selecao = st.session_state[chave_tabela].selection
    linhas = selecao.rows or [linha for linha, _coluna in selecao.cells]
    if linhas:
        st.session_state[chave_card] = f"uf:{ufs_linhas[linhas[0]]}"


def filtro_geral(pres: dict[str, Resultado]) -> tuple[str, str | None]:
    """Blocos clicáveis por região (com quem lidera para Presidente) e, abaixo, os estados da região."""
    st.session_state.setdefault("vg_regiao", "Brasil")
    regiao = st.session_state["vg_regiao"]
    for col, reg in zip(st.columns(6, gap="small"), ["Brasil", *config.REGIOES]):
        rec = ("brasil", None) if reg == "Brasil" else ("regiao", reg)
        r = presidente_no_recorte(rec, pres)
        c = ui.lider(r) if r else None
        ativo = reg == regiao
        # três linhas fixas (cortadas com "…") para os botões ficarem alinhados entre os blocos
        linha = '<div style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:.85rem" title="{dica}">{}</div>'
        with col.container(border=True):
            apuracao = f"{r.pct_secoes if r else 0:.0f}% apurado"
            dica = f"Presidente em {reg}: {c.nome} ({c.partido}) lidera com {ui.pct(c.pct_validos)}" if c else ""
            st.markdown(
                linha.format(f"<b>{reg}</b> <small>· {len(ufs_recorte(rec))} UFs</small>", dica=dica)
                + linha.format(f'<span style="color:{ui.cor(c.partido)}">●</span> {c.nome}' if c else "Aguardando votos", dica=dica)
                + linha.format(f"<b>{ui.pct(c.pct_validos)}</b> · {apuracao}" if c else apuracao, dica=dica),
                unsafe_allow_html=True,
            )
            st.button("✓ Selecionada" if ativo else "Ver região", key=f"vg_reg_{reg}", width="stretch",
                      type="primary" if ativo else "secondary", on_click=definir, args=("vg_regiao", reg))
    ufs = config.UFS if regiao == "Brasil" else config.REGIOES[regiao]
    # key por região: ao trocar de região a seleção de estado recomeça
    uf = st.pills("Estado", ufs, key=f"vg_uf_{regiao}",
                  format_func=str.upper if regiao == "Brasil" else config.NOMES_UF.get)
    if uf:
        return ("uf", uf)
    return ("brasil", None) if regiao == "Brasil" else ("regiao", regiao)


def lista_estados(chave: str, res: dict[str, Resultado], ufs: list[str], rec: tuple[str, str | None]):
    """Tabela compacta de quem lidera em cada UF do recorte; clicar numa linha abre o estado no card."""
    linhas, ufs_linhas = [], []
    for u in ufs:
        r = res.get(u)
        if r is None:
            continue
        cs = r.candidatos if r.candidatos and r.candidatos[0].votos else []
        nome = [f"{c.nome} ({c.partido})" for c in cs] + ["—"] * 3
        p = [c.pct_validos for c in cs] + [None] * 3
        if r.vagas > 1:  # Senado: 2 vagas, a disputa que importa é a da 2ª vaga (2º × 3º)
            linhas.append({"UF": u.upper(), "1º": nome[0], "2º": nome[1],
                           "2º×3º": p[1] - p[2] if p[2] is not None else None})
        else:
            linhas.append({"UF": u.upper(), "Lidera": nome[0], "%": p[0],
                           "Vant.": p[0] - p[1] if p[1] is not None else None})
        ufs_linhas.append(u)
    chave_tabela = f"vg_tab_{chave}_{rec[1]}"
    st.dataframe(
        linhas, hide_index=True, width="stretch", key=chave_tabela,
        height=min(35 * (len(linhas) + 1) + 3, 318),
        on_select=partial(abrir_uf, chave_tabela, ufs_linhas, f"vg_card_{chave}"), selection_mode=["single-row", "single-cell"],  # só "single-row" exigiria acertar a caixinha
        column_config={  # larguras fixas para todas as colunas caberem no card (nomes longos ganham "…")
            "UF": st.column_config.TextColumn(width=36),
            "Lidera": st.column_config.TextColumn(width=126),
            "1º": st.column_config.TextColumn(width=92),
            "2º": st.column_config.TextColumn(width=92),
            "%": st.column_config.NumberColumn(format="%.1f%%", width=56),
            "Vant.": st.column_config.NumberColumn(format="%.1f", width=48, help="1º menos 2º, em pontos percentuais"),
            "2º×3º": st.column_config.NumberColumn(format="%.1f", width=52, help="Disputa pela 2ª vaga: 2º menos 3º, em p.p."),
        },
    )
    st.caption("Clique num estado para ver o ranking · ordene pelo cabeçalho")


def situacao_disputas(res: dict[str, Resultado], ufs: list[str]) -> str:
    rs = [res[u] for u in ufs if u in res]
    eleito = sum(any(c.eleito for c in r.candidatos) for r in rs)
    segundo = sum(not any(c.eleito for c in r.candidatos) and any("2º" in c.situacao for c in r.candidatos) for r in rs)
    partes = [f"{eleito} com eleito" if eleito else "", f"{segundo} vão ao 2º turno" if segundo else "",
              f"{len(rs) - eleito - segundo} em apuração"]
    return " · ".join(x for x in partes if x)


def card(titulo: str, chave: str, res: dict[str, Resultado], rec_geral: tuple[str, str | None]):
    with st.container(border=True):
        st.markdown(f"#### {titulo}")
        opcao = st.selectbox("Recorte do card", OPCOES_CARD, key=f"vg_card_{chave}", label_visibility="collapsed",
                             format_func=rotulo_opcao)
        rec = rec_geral if opcao == "geral" else para_recorte(opcao)
        ufs = ufs_recorte(rec)
        r_pres = presidente_no_recorte(rec, res) if chave == "presidente" else None
        pct_apurado = r_pres.pct_secoes if r_pres else apurado(res, ufs)
        st.markdown(f"**{nome_recorte(rec)}** <small>· {ui.pct(pct_apurado)} apurado</small>", unsafe_allow_html=True)
        ui.mapa_lideres(res, set() if rec[0] == "brasil" else set(ufs), esmaecer=True, altura=290)

        if rec[0] == "uf":  # um estado: ranking + situação + voltar para a região
            r = r_pres or res.get(rec[1])
            if r is None:
                st.info("Sem dados para esta UF.")
            else:
                ui.grafico_barras(r.candidatos[:5], rotulo_max=130)
                for c in r.candidatos[: r.vagas + 1]:
                    ui.selo_situacao(c)
            regiao = REGIAO_DA_UF[rec[1]]
            st.button(f"← Ver {regiao}", key=f"vg_voltar_{chave}", type="tertiary",
                      on_click=definir, args=(f"vg_card_{chave}", f"r:{regiao}"))
            return

        lideres = {u: c for u in ufs if u in res and (c := ui.lider(res[u]))}
        if lideres:
            st.markdown("<small>**Quem lidera nos estados**</small>", unsafe_allow_html=True)
            ui.grafico_placar(lideres)
        else:
            st.caption("Aguardando os primeiros votos apurados.")
        if r_pres is not None:
            st.markdown(f"<small>**Mais votados · {nome_recorte(rec)}**</small>", unsafe_allow_html=True)
            ui.grafico_barras(r_pres.candidatos[:5], rotulo_max=130)
        elif chave != "presidente":
            st.caption(situacao_disputas(res, ufs))
            lista_estados(chave, res, ufs, rec)


def visao_geral():
    @st.fragment(run_every=REFRESH)
    def conteudo():
        st.markdown("## Visão geral")
        pres = ui.resultados_por_uf(turno, "Presidente")
        rec = filtro_geral(pres)
        r = presidente_no_recorte(rec, pres)
        if r is None:
            st.info("Resultado ainda não divulgado pelo TSE.", icon=":material/hourglass_empty:")
            return

        st.markdown(f"### {nome_recorte(rec)}")
        st.markdown(f":gray-badge[:material/schedule: Dados de {r.atualizacao.split(' ')[-1][:5] or '—'}] "
                    f":gray-badge[Presidente: {ui.pct(r.pct_secoes)} das seções totalizadas]")
        st.progress(min(r.pct_secoes / 100, 1.0))
        k = st.columns(4)
        k[0].metric("Eleitorado", ui.fmt(r.eleitorado), border=True)
        k[1].metric("Comparecimento", ui.fmt(r.comparecimento), ui.pct(r.pct_comparecimento), delta_color="off", delta_arrow="off", border=True)
        k[2].metric("Abstenção", ui.fmt(r.abstencao), ui.pct(r.pct_abstencao), delta_color="off", delta_arrow="off", border=True)
        k[3].metric("Brancos e nulos", ui.fmt(r.brancos + r.nulos), ui.pct(r.pct_brancos + r.pct_nulos), delta_color="off", delta_arrow="off", border=True)

        cards = [("Presidente", "presidente", pres), ("Governador", "governador", ui.resultados_por_uf(turno, "Governador"))]
        if turno == 1:
            cards.append(("Senado", "senado", ui.resultados_por_uf(1, "Senador")))
        for col, (titulo, chave, res) in zip(st.columns(len(cards), gap="medium"), cards):
            with col:
                card(titulo, chave, res, rec)
        st.caption(f"Cada card tem o seu filtro (Brasil, região ou estado) ou segue o filtro geral · mapas: partido de "
                   f"quem lidera em cada UF, atualizam a cada {config.MAPA_TTL_S // 60} min")

        if turno == 1:
            st.divider()
            if rec[0] != "uf":
                st.caption("Escolha um estado no filtro geral para ver os deputados mais votados.")
                return
            uf = rec[1]
            st.markdown(f"#### Deputados mais votados · {config.NOMES_UF[uf]}")
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
