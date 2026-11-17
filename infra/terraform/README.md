# Infraestrutura em Terraform (validada, não aplicada)

Módulo que descreve o mesmo pipeline do `docker-compose.yml`, só que na AWS: bucket raw em S3,
warehouse Postgres gerenciado (RDS) e catálogo Glue sobre os Parquet da camada raw.

**Este módulo não é aplicado.** Ele existe para provar IaC — declarar a infraestrutura com
revisão, `fmt` e `validate` no CI — sem criar recurso pago. O `docker compose` continua sendo a
forma de rodar o projeto (ver `D-06` e `D-09` em `docs/DECISIONS.md`).

## O que ele descreve

| Recurso | Equivalente local | Decisão |
|---|---|---|
| `aws_s3_bucket.raw` | `./data/raw` | versionamento ligado, AES256, bloqueio de acesso público, política que nega HTTP sem TLS, lifecycle para `STANDARD_IA` em 30 dias (só o prefixo dos Parquet grandes) |
| `aws_db_instance.warehouse` | serviço `postgres` | Postgres 16, `gp3` cifrado, sem acesso público, `manage_master_user_password` (a senha nasce no Secrets Manager, não no código), `deletion_protection` e snapshot final só quando `environment = "prod"` |
| `aws_vpc` + 2 subnets privadas + SG | rede do compose | RDS sem IP público; 5432 liberado só para `allowed_cidr_blocks` |
| `aws_glue_catalog_database` + `aws_glue_crawler` | — | crawler sobre `s3://<bucket>/raw/`, catálogo e prefixo de tabela `raw_` |
| `aws_iam_role.glue` + policy própria | — | **sem `AWSGlueServiceRole`**: só catálogo do projeto, logs `/aws-glue/*`, `ListBucket` com `s3:prefix=raw/*` e `GetObject` em `raw/*` (um crawler lê, não escreve) |

## Como validar

```bash
cd infra/terraform
terraform init -backend=false -lockfile=readonly   # baixa o provider; não precisa de credencial AWS
terraform fmt -check -recursive
terraform fmt -check terraform.tfvars.example
terraform validate
```

No `make validate` isso não entra de propósito: o resto do projeto roda com Python + Docker, e
exigir Terraform instalado quebraria a validação de quem só quer rodar o pipeline. O portão do
Terraform é o job `terraform` do CI (`.github/workflows/ci.yml`) — ou `make tf-validate` local.

## Custo, se algum dia for aplicado

`db.t4g.micro` + 20 GB `gp3` + backups de 7 dias ≈ **US$ 15–20/mês** na `us-east-1`, mais S3. Para
ver o que seria criado sem criar nada:

```bash
terraform plan -var-file=terraform.tfvars   # exige credencial AWS com permissão de leitura
```

Para destruir: `terraform destroy`. O bucket tem `force_destroy = false` **e versionamento**, então
`destroy` falha se houver objeto ou versão dentro dele — esvazie o bucket antes (ou use
`force_destroy = true` apenas em `dev`).

## O que fica fora do módulo (de propósito)

- **Schema `raw` e os schemas do dbt.** No compose eles nascem de `infra/init.sql` e
  `infra/ci_bootstrap.sql`; com RDS só o banco `warehouse` existe. Um bootstrap real seria
  migration (Flyway) ou `dbt` com `create_schema`.
- **Quem executa o pipeline dentro da VPC.** Hoje não há ECS/EC2 nem NAT: o RDS é uma caixa
  fechada, alcançável só de dentro da VPC. O passo correto é colocar o Airflow em ECS Fargate e
  trocar `allowed_cidr_blocks` por SG-to-SG.
- **Backend remoto.** O state é local e não versionado; em time de verdade seria S3 + DynamoDB
  para lock.

## O que falta para virar infraestrutura de verdade

1. Backend remoto (S3 + DynamoDB) e `-lockfile=readonly` já no `init`.
2. Módulos separados (`network`, `warehouse`, `lake`) em vez de um arquivo `main.tf`.
3. `environments/dev` e `environments/prod` com `tfvars` e state distintos.
4. KMS CMK própria por ambiente (hoje a cifra usa chaves gerenciadas pela AWS) e logging de acesso
   no bucket.
5. Um caminho de deploy real para o Airflow (ECS/MWK) — hoje é só `docker compose`.
