# Infraestrutura em Terraform (validada, não aplicada)

Módulo que descreve o mesmo pipeline do `docker-compose.yml`, só que na AWS: bucket raw em S3,
warehouse Postgres gerenciado (RDS) e catálogo Glue sobre os Parquet da camada raw.

**Este módulo não é aplicado.** Ele existe para provar IaC — declarar a infraestrutura com
revisão, `fmt` e `validate` no CI — sem criar recurso pago. O `docker compose` continua sendo a
forma de rodar o projeto (ver `D-06` e `D-07` em `docs/DECISIONS.md`).

## O que ele descreve

| Recurso | Equivalente local | Decisão |
|---|---|---|
| `aws_s3_bucket.raw` | `./data/raw` | versionamento ligado, AES256, bloqueio de acesso público, política que nega HTTP sem TLS, lifecycle para `STANDARD_IA` em 30 dias |
| `aws_db_instance.warehouse` | serviço `postgres` | Postgres 16, `gp3` cifrado, sem acesso público, `manage_master_user_password` (a senha nasce no Secrets Manager, não no código) |
| `aws_vpc` + 2 subnets privadas + SG | rede do compose | RDS sem IP público; 5432 liberado só para `allowed_cidr_blocks` |
| `aws_glue_catalog_database` + `aws_glue_crawler` | — | crawler sobre `s3://<bucket>/raw/`, role com `AWSGlueServiceRole` + acesso mínimo ao bucket |
| `aws_iam_role.glue` + policy inline | — | somente `ListBucket`/`GetBucketLocation` no bucket e `Get/Put/DeleteObject` nos objetos |

## Como validar

```bash
cd infra/terraform
terraform init -backend=false     # baixa o provider; não precisa de credencial AWS
terraform fmt -check -recursive
terraform validate
```

No `check_env.py` e no `make validate` isso não entra de propósito: o restante do projeto roda com
Python + Docker, e exigir Terraform instalado quebraria a validação de quem só quer rodar o
pipeline. O portão do Terraform é o job `terraform` do CI (`.github/workflows/ci.yml`).

## Custo, se algum dia for aplicado

`db.t4g.micro` + 20 GB `gp3` + backups de 7 dias ≈ **US$ 15–20/mês** na `us-east-1`, mais S3. Para
ver o que seria criado sem criar nada:

```bash
terraform plan -var-file=terraform.tfvars   # exige credencial AWS com permissão de leitura
```

Para destruir: `terraform destroy`. O RDS está com `deletion_protection = false` e
`skip_final_snapshot = true` **só porque o ambiente é `dev`** — em `prod`, os dois mudam.

## O que falta para virar infraestrutura de verdade

1. Backend remoto (S3 + DynamoDB para lock) — hoje o state é local e não versionado.
2. Módulos separados (`network`, `warehouse`, `lake`) em vez de um arquivo `main.tf`.
3. `environments/dev` e `environments/prod` com `tfvars` e state distintos.
4. Um caminho de deploy real para o Airflow (ECS/MWK) — hoje é só `docker compose`.
