# Regras dos indicadores

Todos os horários são os informados pela ANAC em horário de Brasília. São
tratados como horários civis sem fuso, sem conversão para UTC e sem subtrair fusos
dos aeroportos internacionais. O projeto analisa dados históricos, não filas ou
posição de aviões em tempo real.

| Indicador | Numerador | Denominador |
|---|---|---|
| Cancelamento | Etapas `CANCELADO` com partida prevista | Todas as etapas aceitas com partida prevista |
| Atraso na chegada >15 min | Etapas elegíveis cujo desvio de chegada é >15 | Etapas `REALIZADO` com chegada prevista e real |
| Pontualidade na chegada ≤15 min | Etapas elegíveis com desvio ≤15 | Mesmo denominador de chegada |
| Desvio médio na chegada | Soma de real − previsto, em minutos | Mesmo denominador de chegada |

As taxas são proporções entre 0 e 1. Exatamente 15 minutos é pontual; 15 minutos e
1 segundo é atraso. Antecipações têm desvio negativo e contam como pontuais.
`media_desvio_chegada_min` inclui antecipações; não deve ser chamada de média de
atrasos positivos. Denominador zero produz `NULL`, nunca zero inventado.

Cancelados, não informados e realizados sem o par de horários necessário não
entram na pontualidade. Permanecem no fato e são contabilizados separadamente.
Etapas sem partida prevista entram no total, mas não no denominador de cancelamento.

A régua >15 min é uma escolha analítica do projeto, não uma afirmação sobre o
limiar oficial de classificação da ANAC nem uma conclusão jurídica. Campos de
classificação do CSV original não são usados como se tivessem a mesma régua.

Ao juntar meses, empresas ou rotas, **some numeradores e denominadores e divida**.
Não tire a média aritmética de percentuais de grupos de tamanhos diferentes.
Comparações e rankings devem apresentar o número de voos elegíveis; o notebook
usa pelo menos 30 chegadas elegíveis para exibir o ranking exploratório.

`envolve_gig_sdu` identifica `SBGL` e `SBRJ` em origem ou destino. Não inclui todos
os aeródromos do estado do Rio de Janeiro. Também não significa que o voo é
doméstico: o escopo contém etapas nacionais e internacionais disponíveis no VRA.

Os dados não sustentam atribuir o atraso ao clima, à companhia, ao aeroporto ou à
regulação. O projeto descreve frequência e horários, não causalidade nem previsão.
