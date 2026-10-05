# Acompanhamento da Apuração — Eleições 2026

Painel em Python/Streamlit para acompanhar em tempo real a apuração das Eleições Gerais de 2026
(1º turno em 04/10/2026; 2º turno em 25/10/2026), usando **apenas os dados oficiais públicos do TSE**
(Divulgação de Resultados, `resultados.tse.jus.br`). Não exige login nem chave de API.

> Projeto independente, sem vínculo com o TSE. Os números exibidos são os publicados pelo TSE no momento
> da consulta.

---

## Sumário

- [Funcionalidades](#funcionalidades)
- [Instalação e execução](#instalação-e-execução)
- [Como usar](#como-usar)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Configuração](#configuração)
- [Fonte dos dados (endpoints do TSE)](#fonte-dos-dados-endpoints-do-tse)
- [Cache e respeito ao servidor](#cache-e-respeito-ao-servidor)
- [Particularidades dos dados e decisões técnicas](#particularidades-dos-dados-e-decisões-técnicas)
- [Testes](#testes)
- [Limitações conhecidas](#limitações-conhecidas)

---

## Funcionalidades

O app tem duas páginas, escolhidas no menu do topo da barra lateral. A barra lateral também tem o **turno**
(1º/2º) e a **atualização automática** (liga/desliga e intervalo de 60 a 600 s).

### Visão geral (página inicial)

Uma página com todos os cargos majoritários lado a lado.

- **Filtro geral** (topo da tela)
  - Um bloco por recorte: **Brasil, Norte, Nordeste, Centro-Oeste, Sudeste e Sul**. Cada bloco mostra quem
    lidera para Presidente ali, com quanto, e o % apurado; clicar seleciona o recorte.
  - Abaixo, os **estados** da região escolhida (com nome completo; em "Brasil", só as siglas).
  - Indicadores do recorte: eleitorado, comparecimento, abstenção, brancos e nulos e o progresso da apuração.
- **Cards Presidente, Governador e Senado**, cada um com o **seu próprio filtro**
  - Dropdown hierárquico: *Seguir filtro geral*, *Brasil* e cada região seguida dos seus estados
    (aceita busca digitando, ex.: "bah" → Bahia). Assim dá para ver Presidente no Brasil, Governador no
    Nordeste e Senado em SP ao mesmo tempo.
  - **Mapa** colorido pelo partido de quem lidera em cada UF; o recorte do card fica em destaque e o resto
    do país esmaecido (um estado escolhido ganha contorno).
  - **Recorte de região/Brasil**: placar de quantas UFs cada partido lidera (passe o mouse para ver quais),
    contagem de disputas ("3 com eleito · 24 em apuração") e lista de estados — **clique numa linha** para
    abrir o estado no card. No Senado (2 vagas), a coluna **2º×3º** mostra quão disputada está a 2ª vaga.
  - **Um estado**: ranking dos candidatos, situação de cada um (eleito / 2º turno) e botão para voltar à região.
- **Deputados**: ao escolher um estado no filtro geral, aparecem os 10 deputados federais e os 10
  estaduais (ou distritais, no DF) mais votados.

No 2º turno aparecem apenas Presidente e Governador.

### Painel detalhado

Um cargo por vez, com todos os detalhes.

- **Cargo**: Presidente, Governador, Senador, Deputado Federal e Deputado Estadual (Deputado Distrital
  quando a UF é DF).
- **Abrangência**: Presidente pode ser visto no Brasil, em qualquer UF ou no Exterior; os demais cargos, por UF.
- **Cabeçalho**: % de seções totalizadas, horário da totalização do TSE, horário da consulta e o selo
  "Dados de HH:MM".
- **Cartões** dos primeiros colocados com foto oficial, partido, número, % dos válidos, votos e situação
  (aparecem a partir do primeiro voto apurado; antes disso a ordem seria só alfabética).
- **Gráfico de barras** por candidato, colorido por partido.
- **Mapa** com três modos: *Quem lidera* (partido do 1º colocado em cada UF), *Desempenho* (% de um
  candidato a Presidente em cada UF) e *Andamento* (% de seções totalizadas por UF).
- **Resultado por estado**: tabela com as 27 UFs — % apurado, quem lidera, vantagem sobre o 2º e, para
  Presidente, o % dos 4 primeiros em cada UF. Ordenável pelo cabeçalho.
- **Comparecimento e votos**: comparecimento, abstenção, válidos, brancos e nulos, com percentuais.
- **Lista completa** de candidatos; para deputados, com **busca por nome ou número** (ignora acentos).

### Em todo o app

- Gráficos e mapas **interativos (Plotly)**: zoom, arrastar, detalhes ao passar o mouse, baixar como PNG e,
  nos mapas por partido, clicar na legenda para esconder/mostrar um partido.
- **Tema claro e escuro**, seguindo o sistema de quem está vendo.
- Erros de rede, arquivos ainda não publicados e respostas vazias **não quebram a tela**: aparece um aviso
  ("Resultado ainda não divulgado pelo TSE") ou a última cópia salva.

---

## Instalação e execução

Requer **Python 3.11+** (testado com 3.14).

```bash
git clone https://github.com/Ruanan-Terra/AcompanhamentoEleicoesAPI.git
cd AcompanhamentoEleicoesAPI
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Execução:

```bash
.venv/bin/streamlit run app.py
```

Abra http://localhost:8501.

Dependências (`requirements.txt`): `streamlit`, `requests`, `plotly` e `pytest` (só para os testes).

---

## Como usar

1. Na **Visão geral**, clique numa região (ou em Brasil) no topo e, se quiser, num estado.
2. Use o dropdown de cada card para olhar outro recorte só naquele cargo. "↺ Seguir filtro geral" volta a
   acompanhar o topo.
3. Nas listas de estados dos cards, clique em qualquer célula de uma linha para abrir o estado; "← Ver
   região" volta.
4. Para um cargo específico com todos os detalhes (incluindo deputados com busca), use o **Painel detalhado**.
5. Deixe a **atualização automática** ligada durante a apuração; o selo "Dados de HH:MM" mostra o horário
   dos dados do TSE.

---

## Estrutura do projeto

```
AcompanhamentoEleicoesAPI/
├── app.py                  # Navegação e as duas páginas (Visão geral e Painel detalhado)
├── ui.py                   # Componentes compartilhados: cartões, gráficos, mapas (Plotly) e cache de dados
├── parser.py               # JSON do TSE → Resultado / Candidato; agregar() soma UFs (Presidente por região)
├── tse_client.py           # Monta as URLs, faz o GET e guarda a última resposta válida em cache/
├── config.py               # Códigos de eleição/cargo, UFs, regiões, intervalos e cores dos partidos
├── assets/br_uf.geojson    # Contorno das UFs (malha do IBGE, pré-processada)
├── .streamlit/config.toml  # Tema claro/escuro, barra de ferramentas e telemetria desligada
├── tests/
│   ├── test_parser.py      # Testes do parsing e da agregação
│   └── fixtures/           # Arquivos reais do TSE de 04/10/2026
├── cache/                  # Última cópia de cada arquivo baixado (criado ao rodar; fora do git)
└── requirements.txt
```

Camadas: `tse_client.py` (rede) → `parser.py` (dados) → `ui.py` + `app.py` (interface). O parser não
depende de rede nem do Streamlit, por isso é testável isoladamente.

---

## Configuração

Tudo fica em `config.py`:

| Configuração | Para que serve |
|---|---|
| `ELEICOES` | Códigos das eleições por turno (federal e estadual) |
| `CARGOS` | Código de cada cargo, eleição a que pertence e abrangência fixa (`"br"` para Presidente) |
| `CARGOS_2T` | Cargos que têm 2º turno |
| `UFS`, `NOMES_UF`, `REGIOES` | Siglas, nomes e regiões do IBGE |
| `INTERVALO_MIN_S` | Intervalo mínimo entre consultas do mesmo arquivo (60 s) |
| `INTERVALO_PADRAO_S` | Intervalo padrão da atualização automática (120 s) |
| `MAPA_TTL_S` | Validade dos dados por UF usados nos mapas e listas (300 s) |
| `TIMEOUT_S` | Tempo máximo de espera por resposta do TSE |
| `CORES_PARTIDOS` | Cor de cada partido (versão clara e escura); os demais aparecem como "Outros" |

---

## Fonte dos dados (endpoints do TSE)

### Índice de eleições

```
https://resultados.tse.jus.br/oficial/comum/config/ele-c.json
```

Lista os pleitos (`pl`) e, em cada um, as eleições (`e`): código (`cd`), código do 2º turno (`cdt2`) e
cargos (`cp`). Os códigos de 2026 (pleito 3220, ciclo `ele2026`) vieram daqui:

| Eleição | 1º turno | 2º turno | Cargos (código) |
|---|---|---|---|
| Federal | 6257 | 6258 | Presidente (1) |
| Estadual | 6259 | 6260 | Governador (3), Senador (5), Dep. Federal (6), Dep. Estadual (7), Dep. Distrital (8) |

### Resultado por cargo e abrangência (arquivo "unificado")

```
https://resultados.tse.jus.br/oficial/ele2026/{eleicao}/dados/{abr}/{abr}-c{cargo:04d}-e{eleicao:06d}-u.json
```

`abr` é `br` (Brasil, só Presidente), a sigla da UF em minúsculas ou `zz` (Exterior, Presidente).
Exemplos: `6257/dados/br/br-c0001-e006257-u.json`, `6259/dados/sp/sp-c0003-e006259-u.json`.

Campos usados:

| Campo | Significado |
|---|---|
| `dt`, `ht` | data/hora da totalização (vazios antes da divulgação) |
| `dg`, `hg` | data/hora de geração do arquivo (horário de Brasília) |
| `s.ts`, `s.st`, `s.pst` | seções: total, totalizadas e % totalizadas |
| `e.te`, `e.est` | eleitorado total e eleitorado das seções já totalizadas |
| `e.c`, `e.pc`, `e.a`, `e.pa` | comparecimento e abstenção (os % são sobre `est`) |
| `v.vv`, `v.vb`, `v.tvn` | votos válidos, brancos e total de nulos (`tvn` = `vn` + `vnt`, nulos técnicos) |
| `v.pvvc`, `v.pvb`, `v.ptvn` | % de válidos, brancos e nulos sobre o total de votos |
| `carg[0].nmn`, `carg[0].nv` | nome do cargo e número de vagas |
| `carg[0].agr[].par[].sg` | sigla do partido |
| `...cand[].n`, `nmu`, `sqcand` | número, nome de urna e identificador do candidato |
| `...cand[].vap`, `pvap` | votos e % dos válidos |
| `...cand[].e`, `st` | eleito (`s`/`n`) e situação em texto, exibida como vem do TSE |

### Andamento por UF (1 arquivo para todas as UFs)

```
https://resultados.tse.jus.br/oficial/ele2026/{eleicao}/dados/br/br-e{eleicao:06d}-ab.json
```

`abr[]` com `cdabr` (UF), `tpabr` e `s.pst` (% de seções totalizadas). Usado no mapa "Andamento".

### Fotos dos candidatos

```
https://resultados.tse.jus.br/oficial/ele2026/{eleicao}/fotos/{abr}/{sqcand}.jpeg
```

Carregadas direto pelo navegador. As de Presidente existem só em `fotos/br/`.

### Contorno dos estados (IBGE)

```
https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?formato=application/vnd.geo+json&qualidade=minima&intrarregiao=UF
```

O TSE não publica geometria, então o contorno vem da malha oficial do IBGE. Não é dado eleitoral: foi
baixado **uma única vez**, pré-processado e salvo em `assets/br_uf.geojson`; o app não acessa o IBGE.

### Arquivos não usados

- O formato "simplificado" de 2022 (`dados-simplificados/...-r.json`) e os arquivos separados `-f`/`-v`
  retornam 404 em 2026.
- Arquivos ainda não publicados (ex.: 2º turno antes de 25/10) retornam 404 e aparecem como "ainda não
  divulgado".

---

## Cache e respeito ao servidor

- Todas as requisições são **sequenciais**, nunca em paralelo, com `timeout`.
- **Um arquivo exibido** (`st.cache_data`, 60 s): o mesmo arquivo nunca é baixado duas vezes em menos de
  60 s, mesmo com várias abas ou pessoas usando o app ao mesmo tempo.
- **Dados por UF** (27 arquivos por cargo, usados em mapas, placares e listas) ficam **5 min** em cache.
  A Visão geral usa Presidente, Governador e Senador (até 81 arquivos pequenos a cada 5 min,
  compartilhados com o Painel detalhado). Os arquivos de deputados, maiores, só são baixados ao escolher
  um estado.
- A atualização automática tem intervalo mínimo de **60 s**.
- **Falha de rede**: o app exibe a última cópia salva em `cache/` (no Painel detalhado, com um aviso de que
  está sem conexão; na Visão geral, sem aviso).

---

## Particularidades dos dados e decisões técnicas

Coisas descobertas com os dados reais da apuração de 04/10/2026 e que o código trata:

- **% de válidos**: `v.pvv` vem sempre como 100% (é relativo aos próprios válidos); o correto é `v.pvvc`,
  sobre o total de votos — mesma base de `pvb` (brancos) e `ptvn` (nulos).
- **Comparecimento e abstenção**: o TSE calcula sobre o eleitorado das seções já totalizadas (`e.est`), não
  sobre o eleitorado total (`e.te`). A soma por região (`agregar()`) usa a mesma base.
- **Horário de PE**: o arquivo de Pernambuco informou a totalização uma hora à frente do horário de geração
  (possivelmente o fuso de Fernando de Noronha; não confirmado). Nos recortes por região o app usa o
  horário de geração (`dg`/`hg`), que é sempre de Brasília.
- **Exterior no arquivo de andamento**: `zz` vem marcado como `tpabr: "uf"` e é ignorado nos mapas.
- **Presidente por região**: o TSE não publica totais por região; o app soma os votos das UFs da região e
  recalcula os percentuais.
- **Malha do IBGE**: os polígonos vêm no sentido anti-horário (padrão GeoJSON), mas o d3 (usado pelo
  Plotly) espera o sentido horário; o arquivo em `assets/` já está corrigido.
- **Mapas em camadas**: o Plotly ignora opacidade e contorno por estado dentro de uma mesma camada do
  choropleth. Por isso cada mapa é desenhado em camadas (estados apagados, normais e o contornado, nesta
  ordem, para a borda do estado escolhido não ficar sob as vizinhas), e cada camada leva só os contornos
  dos seus estados.
- **Cores dos partidos**: só os 8 partidos maiores têm cor própria (paleta validada para daltonismo); mais
  cores no mapa ficariam indistinguíveis. A cor segue o partido em todas as telas.
- **Tema**: as cores que dependem do tema claro/escuro são escolhidas a cada execução, não na importação
  do módulo, pois o `ui.py` é importado uma vez por processo e cada visitante pode usar um tema diferente.

---

## Testes

```bash
.venv/bin/python -m pytest
```

`tests/test_parser.py` cobre o parsing e a agregação usando arquivos reais do TSE salvos em
`tests/fixtures/` (inclusive um da apuração parcial de 04/10/2026, às 17:38): campos e tipos, ordenação
por votos, uso de `dt`/`ht` vs `dg`/`hg`, válidos + brancos + nulos = comparecimento, % de válidos,
andamento por UF sem o exterior, soma por região e campos ausentes sem quebrar.

---

## Limitações conhecidas

- **Dados por UF com até 5 min de atraso** em relação ao arquivo nacional (por causa do cache de 5 min).
- **Primeira abertura da Visão geral** leva alguns segundos (baixa os arquivos das 27 UFs).
- **Telas estreitas**: com a barra lateral aberta, a última coluna das listas de estados ("Vant." /
  "2º×3º") pode ficar parcialmente cortada; dá para ver rolando a tabela para o lado.
- **Situação dos candidatos** ("Eleito", "2º turno") só aparece quando o TSE a informa, geralmente perto do
  fim da totalização de cada estado.
