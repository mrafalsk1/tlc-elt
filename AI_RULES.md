# Regras para o assistente de IA neste projeto

## Tipo de projeto
Pipeline de dados (ELT) com dbt + Airflow + Postgres. Não há deploy; apenas CI do GitHub Actions valida.

## Antes de escrever código
1. Leia docs/FEATURES.md, docs/DECISIONS.md e docs/DATA_CONTRACTS.md.
2. Liste os arquivos que serão alterados e por quê.
3. Não remova nem altere comportamento existente sem pedir confirmação.

## Ao escrever código
4. Toda feature nova DEVE ter testes (unit + integration no mínimo para Python; dbt tests para modelos).
5. Não adicione dependências sem listá-las e justificar.
6. Nunca hardcode segredos, URLs, portas ou connection strings; use variáveis declaradas em .env.example e validadas por scripts/check_env.py.
7. Versões de dependências sempre fixas (==, lockfile commitado).
8. Código deve ser idempotente quando mexer em dados, arquivos ou APIs externas.
9. dbt: nunca use SELECT * em modelos de produção nem INSERT sem chave de deduplicação.

## Regras de dados (obrigatórias neste projeto)
10. Toda tabela nova ou alterada DEVE ter entrada em docs/DATA_CONTRACTS.md (colunas, tipos, nulabilidade, chave primária, significado de negócio).
11. Mudança de schema exige: atualizar o contrato, classificar como aditiva ou breaking, atualizar testes de contrato.
12. Pipelines devem ter teste de idempotência (rodar 2x = mesmo resultado).
13. Dados de teste: apenas fixtures pequenas e anonimizadas; nunca dados reais.
14. Nunca faça DROP/TRUNCATE em produção fora de migração explícita.

## Antes de dar a tarefa por concluída (OBRIGATÓRIO)
15. Rode `make validate` e mostre a saída completa.
16. Se algo falhar, corrija e rode novamente. Não diga "deve funcionar".
17. Atualize docs/FEATURES.md marcando a feature como "validada" com o teste que a cobre.

## Proibido
- Dizer "concluído" sem evidência de execução.
- Ignorar testes quebrados, marcá-los como skip ou alterá-los sem justificativa explícita.
- Declarar que o CI vai passar sem ter rodado o `make validate` localmente.
