"""Configuração central. Códigos confirmados em
https://resultados.tse.jus.br/oficial/comum/config/ele-c.json (pleito 3220, ciclo ele2026)."""

BASE_URL = "https://resultados.tse.jus.br/oficial"
CICLO = "ele2026"

# turno -> {"federal": código, "estadual": código}
ELEICOES = {
    1: {"federal": 6257, "estadual": 6259},
    2: {"federal": 6258, "estadual": 6260},
}

# nome -> (código do cargo, eleição "federal"/"estadual", abrangência fixa ou None = escolher UF)
CARGOS = {
    "Presidente": (1, "federal", "br"),
    "Governador": (3, "estadual", None),
    "Senador": (5, "estadual", None),
    "Deputado Federal": (6, "estadual", None),
    "Deputado Estadual": (7, "estadual", None),
    "Deputado Distrital": (8, "estadual", None),  # só DF; o app troca Estadual -> Distrital quando UF = DF
}
CARGOS_2T = ("Presidente", "Governador")

UFS = ("ac al am ap ba ce df es go ma mg ms mt pa pb pe pi pr rj rn ro rr rs sc se sp to").split()

INTERVALO_MIN_S = 60  # nunca consultar o mesmo arquivo em menos de 60 s
INTERVALO_PADRAO_S = 120
MAPA_TTL_S = 300  # o mapa "quem lidera" baixa 27 arquivos (um por UF), então atualiza no máximo a cada 5 min
TIMEOUT_S = 20
CACHE_DIR = "cache"

# Cores por partido (claro, escuro). A cor segue o partido em todas as telas.
# Paleta categórica validada para daltonismo; partidos fora da lista aparecem como "Outros".
CORES_PARTIDOS = {
    "PL": ("#2a78d6", "#3987e5"),
    "PSB": ("#eb6834", "#d95926"),
    "PSD": ("#1baf7a", "#199e70"),
    "UNIÃO": ("#eda100", "#c98500"),
    "PP": ("#e87ba4", "#d55181"),
    "MDB": ("#008300", "#008300"),
    "REPUBLICANOS": ("#4a3aa7", "#9085e9"),
    "PT": ("#e34948", "#e66767"),
}
COR_OUTROS = ("#898781", "#898781")
COR_SEM_DADOS = ("#e1e0d9", "#2c2c2a")
