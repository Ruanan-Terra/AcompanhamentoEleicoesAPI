# Acompanhamento da Apuração — Eleições 2026

Painel em Streamlit que lê os arquivos JSON públicos da Divulgação de Resultados do TSE
(`resultados.tse.jus.br`). Não exige autenticação.

## Instalação

```bash
cd "/Users/ruananterradelima/Documents/02 - Projetos/AcompanhamentoEleicoesAPI"
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Execução

```bash
.venv/bin/streamlit run app.py
```

Abra http://localhost:8501. Na barra lateral escolha turno, cargo, UF e o intervalo de atualização.

O app tem duas páginas (menu no topo da barra lateral):

- **Visão geral**: uma página com todos os cargos. Botões de região (Brasil, Norte, Nordeste, Centro-Oeste,
  Sudeste, Sul) e de estado; indicadores do recorte; três mapas lado a lado (Presidente, Governador, Senado)
  coloridos por quem lidera em cada UF, com as UFs fora do filtro esmaecidas; resumo de cada cargo e, ao
  escolher um estado, os deputados federais e estaduais mais votados. Presidente por região soma os votos
  das UFs da região.
- **Painel detalhado**: um cargo por vez, com cartões dos candidatos, gráfico, mapa ("Quem lidera",
  "Desempenho" e "Andamento"), tabela "Resultado por estado", indicadores e lista completa com busca.

Gráficos e mapas são interativos (Plotly): zoom, arrastar, detalhes ao passar o mouse, baixar como PNG e,
nos mapas por partido, clicar na legenda para esconder/mostrar um partido. Segue o tema claro/escuro do sistema.

## Testes

```bash
.venv/bin/python -m pytest
```

As fixtures em `tests/fixtures/` são arquivos reais baixados do TSE em 04/10/2026.

## Estrutura

| Arquivo | Papel |
|---|---|
| `config.py` | URL base, códigos de eleição/cargo, UFs, intervalos |
| `tse_client.py` | Monta a URL, faz o GET e guarda a última resposta válida em `cache/` |
| `parser.py` | Converte o JSON em `Resultado` / `Candidato`; `agregar()` soma UFs (Presidente por região) |
| `app.py` | Navegação e as duas páginas (Visão geral e Painel detalhado) |
| `ui.py` | Componentes e dados compartilhados: cartões, gráficos e mapas (Plotly), cache |
| `assets/br_uf.geojson` | Contorno das UFs (malha do IBGE, pré-processada: sigla da UF + anéis no sentido horário exigido pelo d3, usado pelo Plotly) |
| `.streamlit/config.toml` | Tema claro/escuro e toolbar |

## Endpoints utilizados

**Índice de eleições** (de onde vieram os códigos em `config.py`):

```
https://resultados.tse.jus.br/oficial/comum/config/ele-c.json
```

Lista os pleitos (`pl`) e, em cada um, as eleições (`e`): código (`cd`), código do 2º turno (`cdt2`) e cargos (`cp`).
Para 2026 (pleito 3220, ciclo `ele2026`):

| Eleição | 1º turno | 2º turno | Cargos |
|---|---|---|---|
| Federal | 6257 | 6258 | 1 Presidente |
| Estadual | 6259 | 6260 | 3 Governador, 5 Senador, 6 Dep. Federal, 7 Dep. Estadual, 8 Dep. Distrital |

**Resultado por cargo e abrangência** (arquivo "unificado"):

```
https://resultados.tse.jus.br/oficial/ele2026/{eleicao}/dados/{abr}/{abr}-c{cargo:04d}-e{eleicao:06d}-u.json
```

`abr` é `br` para Presidente (Brasil) ou a sigla da UF em minúsculas. Exemplos:
`6257/dados/br/br-c0001-e006257-u.json`, `6259/dados/sp/sp-c0003-e006259-u.json`.

Campos usados:

| Campo | Significado |
|---|---|
| `dg`, `hg` | data/hora de geração do arquivo (horário de Brasília; usada nos recortes por região) |
| `dt`, `ht` | data/hora da totalização (vazios antes da divulgação; o app usa `dg`/`hg` nesse caso; confirmado preenchido às 17:37 de 04/10) |
| `s.ts`, `s.st`, `s.pst` | seções: total, totalizadas, % totalizadas |
| `e.te`, `e.est` | eleitorado total e eleitorado das seções já totalizadas |
| `e.c`, `e.pc`, `e.a`, `e.pa` | comparecimento e abstenção; os % são sobre `est`, não sobre `te` |
| `v.vv`, `v.vb`, `v.tvn` | votos válidos, brancos, total de nulos (`tvn` = `vn` nulos + `vnt` nulos técnicos; válidos + brancos + `tvn` = comparecimento) |
| `v.pvvc`, `v.pvb`, `v.ptvn` | % de válidos, brancos e nulos sobre o total de votos (`pvv` é relativo aos próprios válidos: sempre 100%) |
| `carg[0].nmn`, `carg[0].nv` | nome do cargo, número de vagas |
| `carg[0].agr[].par[].sg` | sigla do partido |
| `...cand[].n`, `nmu`, `vap`, `pvap` | número, nome de urna, votos, % dos válidos |
| `...cand[].e`, `st` | eleito (`s`/`n`) e situação em texto, exibida como vem do TSE |

**Andamento por UF** (mapa "Andamento", 1 arquivo para todas as UFs):

```
https://resultados.tse.jus.br/oficial/ele2026/{eleicao}/dados/br/br-e{eleicao:06d}-ab.json
```

`abr[]` com `cdabr` (UF), `tpabr` e `s.pst` (% de seções totalizadas). O exterior (`zz`) também vem como `tpabr: "uf"` e é ignorado.

**Fotos dos candidatos** (carregadas pelo navegador):

```
https://resultados.tse.jus.br/oficial/ele2026/{eleicao}/fotos/{abr}/{sqcand}.jpeg
```

**Mapa "Quem lidera"/"Desempenho" e tabela "Resultado por estado"**: baixam o arquivo `-u` do cargo em cada
uma das 27 UFs (sequencialmente, uma vez para os três) e ficam 5 min em cache (`config.MAPA_TTL_S`).
Presidente também pode ser visto por UF ou Exterior (`zz-c0001-e006257-u.json`). As fotos de Presidente
existem só em `fotos/br/`.

**Contorno dos estados** (não é dado eleitoral; baixado uma única vez e salvo em `assets/`):

```
https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?formato=application/vnd.geo+json&qualidade=minima&intrarregiao=UF
```

Arquivos ainda não publicados (ex.: 2º turno antes de 25/10) retornam 404 e aparecem como "ainda não divulgado".
O formato "simplificado" de 2022 (`dados-simplificados/...-r.json`) retorna 404 em 2026 e não é usado.

## Respeito ao servidor

- Requisições sequenciais, uma por arquivo exibido.
- `st.cache_data(ttl=60)`: o mesmo arquivo nunca é baixado duas vezes em menos de 60 s, mesmo com várias abas abertas.
- Intervalo de atualização automática mínimo de 60 s (`config.INTERVALO_MIN_S`).
- Dados por UF (27 arquivos por cargo) atualizam no máximo a cada 5 min. A Visão geral usa Presidente,
  Governador e Senador (até 81 arquivos pequenos a cada 5 min, compartilhados com o Painel detalhado);
  deputados só são baixados ao escolher um estado.
- Em falha de rede, exibe a última cópia salva em `cache/`.
