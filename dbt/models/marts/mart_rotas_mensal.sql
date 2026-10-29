with totais as (
    select
        competencia, empresa_icao, origem_icao, destino_icao, envolve_gig_sdu,
        count(*) as total_etapas,
        sum(case when planejado then 1 else 0 end) as etapas_planejadas,
        sum(case when realizado then 1 else 0 end) as realizadas,
        sum(case when cancelado and planejado then 1 else 0 end) as canceladas_planejadas,
        sum(case when elegivel_partida then 1 else 0 end) as elegiveis_partida,
        sum(case when elegivel_chegada then 1 else 0 end) as elegiveis_chegada,
        sum(case when atraso_partida_15 then 1 else 0 end) as atrasos_partida_15,
        sum(case when atraso_chegada_15 then 1 else 0 end) as atrasos_chegada_15,
        sum(case when realizado and not elegivel_chegada then 1 else 0 end)
            as realizadas_sem_horario_chegada,
        sum(case when situacao = 'NAO INFORMADO' then 1 else 0 end) as nao_informadas,
        sum(case when elegivel_chegada then atraso_chegada_min else 0 end)
            as soma_desvio_chegada_min
    from {{ ref('fct_voos') }}
    group by competencia, empresa_icao, origem_icao, destino_icao, envolve_gig_sdu
)
select
    *,
    1.0 * canceladas_planejadas / nullif(etapas_planejadas, 0) as taxa_cancelamento,
    1.0 * atrasos_chegada_15 / nullif(elegiveis_chegada, 0) as taxa_atraso_chegada_15,
    1.0 * (elegiveis_chegada - atrasos_chegada_15) / nullif(elegiveis_chegada, 0)
        as pontualidade_chegada_15,
    soma_desvio_chegada_min / nullif(elegiveis_chegada, 0) as media_desvio_chegada_min
from totais
