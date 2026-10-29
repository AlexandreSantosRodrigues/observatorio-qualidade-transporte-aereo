select
    *,
    situacao = 'REALIZADO' as realizado,
    situacao = 'CANCELADO' as cancelado,
    partida_prevista is not null as planejado,
    situacao = 'REALIZADO' and partida_prevista is not null and partida_real is not null
        as elegivel_partida,
    situacao = 'REALIZADO' and chegada_prevista is not null and chegada_real is not null
        as elegivel_chegada,
    case
        when situacao = 'REALIZADO' and partida_prevista is not null and partida_real is not null
        then atraso_partida_min > 15
        else null
    end as atraso_partida_15,
    case
        when situacao = 'REALIZADO' and chegada_prevista is not null and chegada_real is not null
        then atraso_chegada_min > 15
        else null
    end as atraso_chegada_15,
    origem_icao in ('SBGL', 'SBRJ') or destino_icao in ('SBGL', 'SBRJ') as envolve_gig_sdu
from {{ ref('stg_voos') }}
