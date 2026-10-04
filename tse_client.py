"""Cliente HTTP dos arquivos públicos do TSE. Guarda a última resposta válida em disco."""
import json
from pathlib import Path

import requests

import config


class NaoDivulgado(Exception):
    """Arquivo ainda não publicado pelo TSE (404) e sem cópia local."""


def _eleicao(turno: int, cargo: str) -> int:
    return config.ELEICOES[turno][config.CARGOS[cargo][1]]


def url_resultado(turno: int, cargo: str, uf: str | None) -> str:
    """uf=None usa a abrangência fixa do cargo (ex.: "br" para Presidente)."""
    cd_cargo, _, abr_fixa = config.CARGOS[cargo]
    ele = _eleicao(turno, cargo)
    abr = uf or abr_fixa
    return f"{config.BASE_URL}/{config.CICLO}/{ele}/dados/{abr}/{abr}-c{cd_cargo:04d}-e{ele:06d}-u.json"


def url_andamento(turno: int, cargo: str) -> str:
    """Andamento da apuração (% de seções) de todas as UFs, num só arquivo."""
    ele = _eleicao(turno, cargo)
    return f"{config.BASE_URL}/{config.CICLO}/{ele}/dados/br/br-e{ele:06d}-ab.json"


def url_foto(turno: int, cargo: str, abr: str, sqcand: str) -> str:
    # Presidente só tem fotos em fotos/br, mesmo vendo o resultado de uma UF.
    abr = config.CARGOS[cargo][2] or abr.lower()
    return f"{config.BASE_URL}/{config.CICLO}/{_eleicao(turno, cargo)}/fotos/{abr}/{sqcand}.jpeg"


def buscar(url: str) -> tuple[dict, bool]:
    """Retorna (json, veio_do_cache). Em falha de rede usa a última cópia salva."""
    cache = Path(config.CACHE_DIR) / url.rsplit("/", 1)[1]
    try:
        r = requests.get(url, timeout=config.TIMEOUT_S, headers={"User-Agent": "AcompanhamentoEleicoes/1.0"})
        if r.status_code in (403, 404):
            raise NaoDivulgado(url)
        r.raise_for_status()
        dados = r.json()
    except (requests.RequestException, ValueError, NaoDivulgado) as erro:
        if cache.exists():
            return json.loads(cache.read_text(encoding="utf-8")), True
        if isinstance(erro, NaoDivulgado):
            raise
        raise ConnectionError(f"Falha ao acessar o TSE: {erro}") from erro
    cache.parent.mkdir(exist_ok=True)
    cache.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    return dados, False
