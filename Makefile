# Atalhos do projeto. No Windows, use Git Bash ou WSL — ou copie os comandos crus no README.

.PHONY: validate check-env lint test test-dbt build-check up down restart logs psql seed dbt clean

validate: check-env lint test build-check
	@echo "VALIDAÇÃO COMPLETA OK"

check-env:
	python scripts/check_env.py

lint:
	ruff check scripts dags

test:
	pytest tests/unit tests/integration -v

test-dbt:
	docker compose exec airflow bash -lc "cd /opt/airflow/dbt && dbt test --profiles-dir ."

build-check:
	dbt build --profiles-dir . --target ci

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
