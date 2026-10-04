"""Converte o JSON "-u" do TSE em objetos simples."""
from dataclasses import dataclass, replace
from datetime import datetime


def _int(v) -> int:
    return int(str(v or "0").replace(".", "") or 0)


def _pct(v) -> float:
    return float(str(v or "0").replace(",", ".") or 0)


@dataclass
class Candidato:
    numero: str
    sqcand: str  # identificador do candidato, usado no nome do arquivo da foto
    nome: str
    partido: str
    votos: int
    pct_validos: float
    eleito: bool
    situacao: str  # texto do TSE, ex.: "Eleito", "2º turno" (vazio até a totalização)


@dataclass
class Resultado:
    cargo: str
    abrangencia: str
    vagas: int
    atualizacao: str  # "dd/mm/aaaa hh:mm:ss" da totalização (dt/ht) ou da geração do arquivo (dg/hg)
    gerado: str  # geração do arquivo (dg/hg), sempre no horário de Brasília
    secoes_total: int
    secoes_totalizadas: int
    pct_secoes: float
    eleitorado: int
    eleitorado_apurado: int  # eleitorado das seções já totalizadas: base do % de comparecimento/abstenção
    comparecimento: int
    pct_comparecimento: float
    abstencao: int
    pct_abstencao: float
    validos: int
    pct_validos: float
    brancos: int
    pct_brancos: float
    nulos: int
    pct_nulos: float
    candidatos: list[Candidato]


def parse(d: dict) -> Resultado:
    cargo = d["carg"][0]
    s, e, v = d.get("s", {}), d.get("e", {}), d.get("v", {})
    candidatos = [
        Candidato(
            numero=c["n"],
            sqcand=c.get("sqcand", ""),
            nome=c.get("nmu") or c.get("nm", ""),
            partido=p.get("sg", ""),
            votos=_int(c.get("vap")),
            pct_validos=_pct(c.get("pvap")),
            eleito=c.get("e") == "s",
            situacao=c.get("st", ""),
        )
        for agr in cargo.get("agr", [])
        for p in agr.get("par", [])
        for c in p.get("cand", [])
    ]
    candidatos.sort(key=lambda c: (-c.votos, c.nome))
    data, hora = (d["dt"], d["ht"]) if d.get("dt") else (d.get("dg", ""), d.get("hg", ""))
    return Resultado(
        cargo=cargo.get("nmn", ""),
        abrangencia=d.get("cdabr", "").upper(),
        vagas=_int(cargo.get("nv")),
        atualizacao=f"{data} {hora}".strip(),
        gerado=f"{d.get('dg', '')} {d.get('hg', '')}".strip(),
        secoes_total=_int(s.get("ts")),
        secoes_totalizadas=_int(s.get("st")),
        pct_secoes=_pct(s.get("pst")),
        eleitorado=_int(e.get("te")),
        eleitorado_apurado=_int(e.get("est")),
        comparecimento=_int(e.get("c")),
        pct_comparecimento=_pct(e.get("pc")),
        abstencao=_int(e.get("a")),
        pct_abstencao=_pct(e.get("pa")),
        validos=_int(v.get("vv")),
        pct_validos=_pct(v.get("pvvc")),  # "pvv" é relativo aos próprios válidos (sempre 100%)
        brancos=_int(v.get("vb")),
        pct_brancos=_pct(v.get("pvb")),
        nulos=_int(v.get("tvn")),
        pct_nulos=_pct(v.get("ptvn")),
        candidatos=candidatos,
    )


def parse_andamento(d: dict) -> dict[str, float]:
    """Arquivo "-ab": UF (minúscula) -> % de seções totalizadas. Ignora "br" e "zz" (exterior, que o TSE marca como uf)."""
    return {
        a["cdabr"]: _pct(a.get("s", {}).get("pst"))
        for a in d.get("abr", [])
        if a.get("tpabr") == "uf" and a["cdabr"] != "zz"
    }


def _p(parte: int, todo: int) -> float:
    return round(100 * parte / todo, 2) if todo else 0.0


def agregar(resultados: list[Resultado], nome: str) -> Resultado:
    """Soma várias abrangências (ex.: as UFs de uma região) e recalcula os percentuais.
    Só faz sentido quando os candidatos são os mesmos em todas (Presidente)."""
    cands: dict[str, Candidato] = {}
    for r in resultados:
        for c in r.candidatos:
            if c.numero in cands:
                cands[c.numero].votos += c.votos
            else:  # cópia: não altera o objeto original
                cands[c.numero] = replace(c, eleito=False, situacao="")

    def soma(campo: str) -> int:
        return sum(getattr(r, campo) for r in resultados)

    validos, comparecimento, apurado = soma("validos"), soma("comparecimento"), soma("eleitorado_apurado")
    for c in cands.values():
        c.pct_validos = _p(c.votos, validos)
    # dg/hg em vez de dt/ht: alguns arquivos de UF trazem dt/ht fora do horário de Brasília (ex.: PE)
    datas = [r.gerado for r in resultados if r.gerado]
    gerado = max(datas, key=lambda d: datetime.strptime(d, "%d/%m/%Y %H:%M:%S"), default="")
    return Resultado(
        cargo=resultados[0].cargo if resultados else "",
        abrangencia=nome,
        vagas=resultados[0].vagas if resultados else 0,
        atualizacao=gerado,
        gerado=gerado,
        secoes_total=soma("secoes_total"),
        secoes_totalizadas=soma("secoes_totalizadas"),
        pct_secoes=_p(soma("secoes_totalizadas"), soma("secoes_total")),
        eleitorado=soma("eleitorado"),
        eleitorado_apurado=apurado,
        comparecimento=comparecimento,
        pct_comparecimento=_p(comparecimento, apurado),
        abstencao=soma("abstencao"),
        pct_abstencao=_p(soma("abstencao"), apurado),
        validos=validos,
        pct_validos=_p(validos, comparecimento),
        brancos=soma("brancos"),
        pct_brancos=_p(soma("brancos"), comparecimento),
        nulos=soma("nulos"),
        pct_nulos=_p(soma("nulos"), comparecimento),
        candidatos=sorted(cands.values(), key=lambda c: (-c.votos, c.nome)),
    )
