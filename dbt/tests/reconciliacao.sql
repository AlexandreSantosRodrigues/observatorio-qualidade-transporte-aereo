select 1 as falha
where (select count(*) from {{ ref('fct_voos') }})
    <> (select count(*) from {{ source('vra', 'voos') }})
or (select count(*) from {{ ref('fct_voos') }})
    <> (select coalesce(sum(total_etapas), 0) from {{ ref('mart_rotas_mensal') }})
