"""Converte o JSON "-u" do TSE em objetos simples."""
from dataclasses import dataclass


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
    secoes_total: int
    secoes_totalizadas: int
    pct_secoes: float
    eleitorado: int
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
        secoes_total=_int(s.get("ts")),
        secoes_totalizadas=_int(s.get("st")),
        pct_secoes=_pct(s.get("pst")),
        eleitorado=_int(e.get("te")),
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
