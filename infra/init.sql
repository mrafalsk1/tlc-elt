-- Roda uma única vez, na primeira subida do container (volume vazio).
-- Cria o warehouse separado do banco de metadados do Airflow.

CREATE DATABASE warehouse;

\connect warehouse

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS intermediate;
CREATE SCHEMA IF NOT EXISTS marts;
