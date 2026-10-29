select * from {{ ref('mart_rotas_mensal') }}
where taxa_cancelamento < 0 or taxa_cancelamento > 1
    or pontualidade_chegada_15 < 0 or pontualidade_chegada_15 > 1
    or taxa_atraso_chegada_15 < 0 or taxa_atraso_chegada_15 > 1
    or canceladas_planejadas > etapas_planejadas
    or atrasos_chegada_15 > elegiveis_chegada
