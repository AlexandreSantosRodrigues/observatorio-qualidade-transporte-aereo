{% if target.type == 'bigquery' %}
{{ config(partition_by={'field': 'data_voo', 'data_type': 'date'},
          cluster_by=['empresa_icao', 'origem_icao', 'destino_icao']) }}
{% endif %}
select * from {{ ref('int_indicadores_voos') }}
