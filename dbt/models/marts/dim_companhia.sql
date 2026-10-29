select
    empresa_icao,
    min(nullif(empresa_nome, '')) as empresa_nome,
    count(distinct nullif(empresa_nome, '')) as nomes_distintos_na_fonte
from {{ ref('stg_voos') }}
group by empresa_icao
