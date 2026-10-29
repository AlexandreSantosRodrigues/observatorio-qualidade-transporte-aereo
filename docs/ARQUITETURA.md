# Arquitetura e contrato de dados

## Problema e escopo

Comparar atrasos e cancelamentos por mês, companhia, origem e destino, sem misturar
voos cancelados ou sem horários no denominador de pontualidade. Escopo inicial:
12 arquivos mensais do VRA/ANAC de 2025. Os arquivos podem ser revisados pela ANAC;
um resultado só é reproduzível com os mesmos hashes e a mesma versão do código.

## Fluxo

1. CSV oficial → arquivo original em `data/raw/<competência>/<sha256>.csv`.
2. Python valida cabeçalho, datas, chaves, situação e competência. Mantém os
   identificadores alfanuméricos de voo (por exemplo, `Z8117`).
3. Linhas aceitas → Parquet Zstandard; rejeitadas → JSON com linha, dados e motivos.
4. O release é identificado pelo hash da fonte e pelo hash do código de ingestão.
   `CURRENT.json` publica a versão ativa de cada competência em uma operação.
5. DuckDB reconstrói a bronze com os Parquets ativos. dbt constrói staging,
   indicadores, dimensões, fato e agregado mensal.
6. Após os testes, CSVs, resumo e evidências são gravados em uma nova pasta.
   Somente então um segundo `CURRENT.json` publica o conjunto completo de exports.

Não há consumidores de arquivos parcialmente exportados se usarem o ponteiro
`data/<execução>/exports/CURRENT.json`. Versões antigas permanecem preservadas.
Use apenas um escritor por diretório de dados; concorrência entre cargas no mesmo
diretório não é suportada nesta versão.

## Chave, duplicidades e correções

A chave é o SHA-256 da sequência empresa ICAO, número do voo, DI, tipo de linha,
origem, destino e partida prevista. Na ausência da partida prevista usa-se a
partida real. O hash do conteúdo completo da linha é separado da chave.

- Linhas exatamente iguais, com a mesma chave: conserva uma e contabiliza as cópias.
- Mesma chave e conteúdo diferente no mesmo arquivo: todas as linhas desse grupo
  vão para quarentena. Não há escolha arbitrária de uma versão.
- Nova versão mensal: novo release; substitui o ponteiro daquele mês, sem append.
- Correção de um horário real não muda a chave de um voo que tem partida prevista.
- Em etapas sem partida prevista, corrigir a partida real pode mudar a chave. Por
  isso o reprocessamento substitui a competência inteira.

## Critérios de aceitação

Obrigatórios: empresa ICAO (3 caracteres alfanuméricos), origem/destino ICAO
(4), identificador de voo alfanumérico (até 8), DI (1 alfanumérico), tipo de linha
(1 letra), situação reconhecida e uma partida prevista ou real utilizável.
Tipo de linha ausente é quarentena, não um valor inventado. Data não vazia que
não pode ser interpretada, duração negativa e chave conflitante são rejeitadas.

`fora_competencia` indica que a partida de referência não pertence ao mês do
arquivo: é uma exclusão de escopo deste projeto, não uma declaração de erro da ANAC.
Quarentena não é descartada. Um registro pode ter mais de um motivo; a soma das
contagens por motivo pode exceder o número de registros rejeitados.

Todas as execuções conferem:

`linhas da fonte = aceitas + quarentena + cópias exatas removidas`.

Cada fato conserva `source_sha256`, `competencia` e `source_line`. O leitor usa CSV
com separador `;`, UTF-8/BOM e fallback CP1252. Cabeçalhos novos são conservados no
manifesto e no original, mas não são automaticamente adicionados ao modelo.

## Modelo dimensional

| Modelo | Grão / chave |
|---|---|
| `stg_voos` | Etapa aceita, com tipos explícitos |
| `int_indicadores_voos` | Etapa, flags e elegibilidade |
| `dim_companhia` | ICAO da empresa |
| `dim_aeroporto` | ICAO do aeroporto; usada em dois papéis |
| `dim_data` | Datas observadas; não é calendário contínuo |
| `fct_voos` | Uma etapa aceita, chave `voo_id` |
| `mart_rotas_mensal` | Competência × empresa × origem × destino |

As dimensões usam chaves naturais, não SCD Tipo 2. Se houver nomes distintos para
um ICAO, o nome apresentado é o primeiro em ordem lexical, com contagem explícita
das variantes; não se apresenta esse nome como cadastro histórico oficial.

No BigQuery, o fato é particionado por `data_voo` e agrupado por empresa/origem/
destino. Esse desenho foi escrito, mas sua execução no sandbox permanece pendente.

## Disponibilidade e limites

Os resultados apresentados neste estudo foram produzidos no DuckDB. O adapter
`dbt-bigquery` e a carga são uma integração separada, ainda sem resultados de execução. O fluxo gratuito inicial não
usa GCS, Pub/Sub, Airflow, VMs, trials, Docker, GPU ou conta dbt Cloud.

O Colab não é um serviço de execução contínua: pode interromper sessões. Os dados
ficam na sessão até serem salvos pelo usuário. O workflow manual do GitHub valida
um mês e conserva somente evidências/agregados pequenos, com retenção de 3 dias.
O workflow de Pages publica documentação demonstrativa baseada na fixture sintética;
não representa atualização automática da base oficial.
