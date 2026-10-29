with aeroportos as (
    select origem_icao as aeroporto_icao, origem_descricao as descricao
    from {{ ref('stg_voos') }}
    union all
    select destino_icao as aeroporto_icao, destino_descricao as descricao
    from {{ ref('stg_voos') }}
)
select
    aeroporto_icao,
    min(nullif(descricao, '')) as descricao,
    count(distinct nullif(descricao, '')) as descricoes_distintas_na_fonte,
    aeroporto_icao in ('SBGL', 'SBRJ') as gig_ou_sdu
from aeroportos
group by aeroporto_icao
