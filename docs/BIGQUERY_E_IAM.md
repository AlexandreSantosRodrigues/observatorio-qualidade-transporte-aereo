# BigQuery Sandbox e IAM — execução pendente na conta do proprietário

## Caminho gratuito sem cartão

1. Abra [BigQuery Studio](https://console.cloud.google.com/bigquery) no navegador.
2. Crie um projeto de uso exclusivo e permaneça no **Sandbox**, sem vincular uma
   conta de faturamento, ativar trial ou inserir cartão.
3. Habilite a BigQuery API e, se necessário, a Cloud Billing API para consultar
   `billingInfo`. Habilitar uma API não autoriza habilitar faturamento.
4. Execute primeiro a parte DuckDB do notebook com um mês.
5. Na célula opcional, informe o ID do projeto, marque `EXECUTAR_BIGQUERY=True` e
   autentique-se na interface segura do Colab.
6. A integração só continua se a Cloud Billing API retornar explicitamente
   `billingEnabled=false`. Erro, permissão insuficiente ou resposta desconhecida
   bloqueia a carga. Não há opção para ignorar esse controle.

Seus tokens não são gravados no código nem enviados ao GitHub. Não crie uma chave
JSON de conta de serviço para este exercício. Não compartilhe sua sessão do Colab.

## O que o código faz

- Cria `vra_bronze` e `vra_analytics` em `US`, com identificação `managed_by` e TTL
  de 60 dias para novas tabelas. Se já existirem sem a identificação do projeto,
  interrompe a carga para não substituir datasets de outro trabalho.
- Carrega um Parquet por competência com `WRITE_TRUNCATE`, sem streaming.
- Mantém uma view `vra_bronze.voos` com os meses selecionados.
- Executa os mesmos modelos/testes dbt com o adapter BigQuery, usando tabelas e
  views, sem seeds, snapshots, `INSERT`, `UPDATE`, `DELETE` ou `MERGE`.
- Salva os recibos em `data/<execução>/gcp-evidence/bigquery.json` somente após
  execução bem-sucedida. Arquivos GCP ficam ignorados pelo Git por padrão.

Há um teto de 1.000.000.000 bytes por consulta no perfil dbt e na criação da view,
1 thread e limite de 150 MiB de Parquets comprimidos por carga. São controles
adicionais, **não uma previsão do armazenamento descomprimido**. A conta sem
faturamento é o controle de custo principal. A execução pode falhar por quota.

O atalho de reprocessamento confere hashes da fonte/contrato e contagem da tabela.
Isso não é uma prova criptográfica do conteúdo remoto: uma alteração de valores
mantendo a mesma quantidade de linhas pode passar pelo atalho. Recarregue a tabela
se houver edição externa; os datasets são dedicados ao pipeline.

## Matriz de acesso a verificar

| Papel funcional | Permissão/role a avaliar | Escopo mínimo |
|---|---|---|
| Executar consultas | `roles/bigquery.jobUser` | Projeto de execução |
| Ler fonte carregada | `roles/bigquery.dataViewer` | Dataset `vra_bronze` |
| Escrever modelos | `roles/bigquery.dataEditor` | Dataset `vra_analytics` |
| Carregar e substituir fonte | `roles/bigquery.dataEditor` | Dataset `vra_bronze` |
| Criar datasets inicialmente | `bigquery.datasets.create` | Projeto, somente na preparação |
| Conferir billingInfo | `resourcemanager.projects.get` e acesso requerido pela API | Projeto |

O proprietário do projeto recém-criado pode já ter esses acessos; isso não prova
que uma identidade restrita os tenha. Não conceda `Owner`, `Editor` ou
`BigQuery Admin` a outras pessoas para fazer o exercício. Permissões reais e IAM
permanecem **pendentes de teste**; esta matriz documenta o desenho.

Uma validação completa deve registrar: identidade executora sem expor token,
permissões usadas, job IDs, testes dbt, comparação de totais com DuckDB e uma
tentativa de acesso negada por uma identidade autorizada para esse teste. Não
adicione outra pessoa nem crie credenciais sem necessidade.

## Limites atuais e expiração

Documentação consultada em 29/10/2026: o Sandbox informa 10 GiB de armazenamento
no ciclo de vida (sem devolução da quota por excluir dados), 1 TiB processado por
mês e expiração automática após 60 dias. Não suporta DML, streaming ou Data
Transfer Service. Reconstruções podem consumir quota; não execute repetidamente
o ano completo. O SQL foi desenhado para essas restrições, mas só a execução
autenticada confirma compatibilidade ponta a ponta.

GCS e Pub/Sub ficam fora desta versão: a oferta Free Tier do Google Cloud requer
conta de faturamento e pode cobrar uso excedente. Não tratamos um trial temporário
como gratuidade permanente.

Fontes primárias:

- https://docs.cloud.google.com/bigquery/docs/sandbox
- https://docs.cloud.google.com/free/docs/free-cloud-features
- https://docs.cloud.google.com/billing/docs/reference/rest/v1/projects/getBillingInfo
- https://docs.cloud.google.com/bigquery/docs/access-control
- https://docs.getdbt.com/docs/core/connect-data-platform/bigquery-setup
