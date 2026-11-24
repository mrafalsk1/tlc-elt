# Atalhos do projeto. No Windows, use Git Bash ou WSL — ou copie os comandos crus no README.

.PHONY: validate check-env lint test test-dbt db-bootstrap-ci build-check quality tf-fmt tf-validate up down restart logs psql seed dbt clean

# Conexão do Postgres de validação (mesmos defaults do CI e do serviço postgres:16).
CI_PGHOST ?= localhost
CI_PGPORT ?= 5432
CI_PGUSER ?= postgres
CI_PGPASSWORD ?= postgres

validate: check-env lint test db-bootstrap-ci build-check
	@echo "VALIDAÇÃO COMPLETA OK"

check-env:
	python scripts/check_env.py

lint:
	ruff check scripts dags dagster_project

# Qualidade com Great Expectations: NÃO entra em validate (exige .venv-quality com GX).
# Roda sobre as fixtures: deve detectar as linhas sujas e sair com código 1.
QUALITY_PY ?= .venv-quality/bin/python
quality:
	$(QUALITY_PY) scripts/quality/run_quality.py --input tests/fixtures/trips_sample.csv --zones tests/fixtures/taxi_zones_sample.csv --out data/alerts/quality-fixtures.jsonl

# Paridade rules.py x GX sobre a fixture. Exige pytest no .venv-quality (requirements-dev).
quality-test:
	$(QUALITY_PY) -m pytest tests/unit/test_quality_parity.py -q

# Dagster (comparativo, lacuna 8): valida definições e lista assets, sem tocar o Postgres.
DAGSTER_PY ?= .venv-dagster/bin/dagster
dagster-check:
	$(DAGSTER_PY) definitions validate -m dagster_project.definitions
	$(DAGSTER_PY) asset list -m dagster_project.definitions

test:
	pytest tests/unit tests/integration -v

test-dbt:
	docker compose exec airflow bash -lc "cd /opt/airflow/dbt && dbt test --profiles-dir ."

# Cria o banco warehouse e o schema raw vazio, como o CI faz antes do dbt build.
db-bootstrap-ci:
	PGPASSWORD=$(CI_PGPASSWORD) psql -h $(CI_PGHOST) -p $(CI_PGPORT) -U $(CI_PGUSER) -c "CREATE DATABASE warehouse;"
	PGPASSWORD=$(CI_PGPASSWORD) psql -h $(CI_PGHOST) -p $(CI_PGPORT) -U $(CI_PGUSER) -d warehouse -f infra/ci_bootstrap.sql

build-check:
	cd dbt && dbt build --profiles-dir . --target ci

# Terraform (infra/terraform): so fmt + validate. Sem credencial da AWS e sem apply.
# `terraform fmt` recusa arquivos fora de *.tf/*.tfvars, entao terraform.tfvars.example e conferido na mao.

TF ?= terraform

tf-fmt:
	cd infra/terraform && $(TF) fmt -recursive

tf-validate:
	cd infra/terraform && $(TF) init -backend=false -input=false -lockfile=readonly && $(TF) fmt -check -recursive && $(TF) validate

# Infraestrutura (Docker)

up:
	# O container roda como uid 50000; sem isso o bind mount de ./data fica sem escrita.
	mkdir -p data/raw && chmod -R 777 data
	docker compose up -d
	@echo "Airflow: http://localhost:8080 (senha em: docker compose logs airflow | grep -i password)"

down:
	docker compose down

restart:
	docker compose restart airflow

logs:
	docker compose logs -f airflow

psql:
	docker compose exec postgres psql -U dw -d warehouse

# Baixa 3 meses + o lookup de zonas e carrega em raw (ajuste o período)
seed:
	docker compose exec airflow python /opt/airflow/scripts/ingest.py --months 2024-01 2024-02 2024-03
	docker compose exec airflow python /opt/airflow/scripts/load_zones.py

dbt:
	docker compose exec airflow bash -lc "cd /opt/airflow/dbt && dbt build --profiles-dir ."

clean:
	docker compose down -v
