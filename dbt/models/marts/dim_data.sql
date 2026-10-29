select distinct
    data_voo,
    cast(extract(year from data_voo) as integer) as ano,
    cast(extract(month from data_voo) as integer) as mes,
    cast(extract(day from data_voo) as integer) as dia
from {{ ref('stg_voos') }}
