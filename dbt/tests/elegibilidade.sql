select * from {{ ref('fct_voos') }}
where (not elegivel_chegada and atraso_chegada_15 is not null)
    or (not elegivel_partida and atraso_partida_15 is not null)
    or (cancelado and (elegivel_partida or elegivel_chegada))
    or (elegivel_chegada and atraso_chegada_15 <> (atraso_chegada_min > 15))
    or (elegivel_partida and atraso_partida_15 <> (atraso_partida_min > 15))
