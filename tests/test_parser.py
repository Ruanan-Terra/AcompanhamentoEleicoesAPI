import json
from pathlib import Path

from parser import parse, parse_andamento

FIX = Path(__file__).parent / "fixtures"


def carregar(nome):
    return json.loads((FIX / nome).read_text(encoding="utf-8"))


def test_presidente_br():
    r = parse(carregar("br-c0001-e006257-u.json"))
    assert r.cargo == "Presidente" and r.abrangencia == "BR" and r.vagas == 1
    assert r.secoes_total == 499248 and r.eleitorado == 158745502
    assert len(r.candidatos) == 12
    assert all(c.sqcand for c in r.candidatos)  # usado na URL da foto
    assert r.atualizacao == "03/10/2026 14:47:37"  # dt/ht vazios -> usa dg/hg


def test_senador_sp_duas_vagas():
    r = parse(carregar("sp-c0005-e006259-u.json"))
    assert r.cargo == "Senador" and r.abrangencia == "SP" and r.vagas == 2
    assert len(r.candidatos) == 13


def test_votos_ordem_e_situacao():
    d = carregar("br-c0001-e006257-u.json")
    d.update(dt="04/10/2026", ht="19:00:00")
    d["s"].update(st="1000", pst="45,67")
    cands = [c for a in d["carg"][0]["agr"] for p in a["par"] for c in p["cand"]]
    cands[3].update(vap="900", pvap="60,00", e="s", st="Eleito")
    cands[0].update(vap="600", pvap="40,00")
    r = parse(d)
    assert r.atualizacao == "04/10/2026 19:00:00"
    assert r.pct_secoes == 45.67 and r.secoes_totalizadas == 1000
    top = r.candidatos[0]
    assert (top.votos, top.pct_validos, top.eleito, top.situacao) == (900, 60.0, True, "Eleito")
    assert r.candidatos[1].votos == 600


def test_campos_ausentes_nao_quebram():
    r = parse({"carg": [{"nmn": "Governador"}]})
    assert r.candidatos == [] and r.pct_secoes == 0 and r.atualizacao == ""


def test_andamento_por_uf():
    a = parse_andamento(carregar("br-e006257-ab.json"))
    assert len(a) == 27 and "br" not in a and "zz" not in a
    assert a["sp"] == 0.0


def test_apuracao_parcial_real():
    # Arquivo real das 17:38 de 04/10/2026 (4,32% das seções)
    r = parse(carregar("br-c0001-e006257-u-parcial.json"))
    assert r.atualizacao == "04/10/2026 17:38:07"  # dt/ht preenchidos durante a apuração
    assert r.validos + r.brancos + r.nulos == r.comparecimento  # tvn = nulos + nulos técnicos
    assert r.pct_validos == 96.19
    votos = [c.votos for c in r.candidatos]
    assert votos == sorted(votos, reverse=True) and votos[0] > 0
