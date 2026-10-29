# Power BI — guia preparado; relatório ainda não criado

O projeto entrega dados e medidas para Power BI; não inclui um `.pbix` nem afirma
que um dashboard foi publicado. A criação gratuita no navegador depende de uma
conta corporativa/acadêmica elegível e das configurações da organização. Gmail e
Hotmail não dão acesso direto ao cadastro do serviço. Não abra trial pago para
executar este projeto sem avaliar as condições.

## Entrada

Use os CSVs da pasta apontada por `exports/CURRENT.json`. No notebook, essa pasta
é a variável `EXPORTS`. Para um relatório web simples, comece com
`mart_rotas_mensal.csv` e as opções de importação disponíveis na sua conta.
Se não houver caminho de criação gratuito, mantenha este requisito pendente e
explore as tabelas no Colab. Outra ferramenta de BI não conta como Power BI.

## Medidas sobre o agregado mensal

```dax
Etapas = SUM(mart_rotas_mensal[total_etapas])

Etapas Planejadas = SUM(mart_rotas_mensal[etapas_planejadas])

Canceladas Planejadas = SUM(mart_rotas_mensal[canceladas_planejadas])

Taxa de Cancelamento = DIVIDE([Canceladas Planejadas], [Etapas Planejadas])

Chegadas Elegíveis = SUM(mart_rotas_mensal[elegiveis_chegada])

Chegadas Atrasadas = SUM(mart_rotas_mensal[atrasos_chegada_15])

Pontualidade Chegada =
    DIVIDE([Chegadas Elegíveis] - [Chegadas Atrasadas], [Chegadas Elegíveis])

Desvio Médio Chegada =
    DIVIDE(SUM(mart_rotas_mensal[soma_desvio_chegada_min]), [Chegadas Elegíveis])
```

Importe contagens como inteiros, desvios como números decimais e taxas como
números decimais formatados em percentual. Verifique a localidade de leitura:
CSV usa vírgula como separador e ponto decimal. Não some nem tire a média das
colunas de taxas já calculadas no CSV.

## Modelo completo, se o ambiente permitir

- `dim_companhia[empresa_icao]` 1 → N `fct_voos[empresa_icao]`.
- `dim_data[data_voo]` 1 → N `fct_voos[data_voo]`.
- Duplique a dimensão aeroporto como Origem e Destino para ter dois papéis ativos:
  ICAO 1 → N em `origem_icao` e `destino_icao`, respectivamente.
- Filtragem simples da dimensão para o fato; evitar relacionamentos bidirecionais.
- Dimensão de datas contém somente dias observados; construa calendário completo
  antes de usar funções de inteligência de tempo que o exijam.

## Páginas propostas para implementação

1. Visão geral: etapas, cancelamento, pontualidade, elegibilidade e série mensal.
2. Companhias/rotas: comparações com denominador visível e filtro mínimo de volume.
3. GIG/SDU: etapas envolvendo Galeão ou Santos Dumont, sem afirmar cobrir todo o RJ.
4. Qualidade: aceitas, quarentena, duplicatas e conciliação da carga.

Referências:

- https://learn.microsoft.com/en-us/power-bi/fundamentals/service-self-service-signup-purchase-for-power-bi
- https://learn.microsoft.com/en-us/power-bi/fundamentals/service-get-started
