-- Bootstrap do CI: cria o schema raw vazio para o dbt conseguir compilar.
-- Em produção esse schema é criado pela ingestão; no CI não baixamos dados.

CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.yellow_trips (
    vendorid                integer,
    tpep_pickup_datetime    timestamp,
    tpep_dropoff_datetime   timestamp,
    passenger_count         double precision,
    trip_distance           double precision,
    ratecodeid              double precision,
    store_and_fwd_flag      text,
    pulocationid            integer,
    dolocationid            integer,
    payment_type            integer,
    fare_amount             double precision,
    extra                   double precision,
    mta_tax                 double precision,
    tip_amount              double precision,
    tolls_amount            double precision,
    improvement_surcharge   double precision,
    total_amount            double precision,
    congestion_surcharge    double precision,
    airport_fee             double precision,
    _source_file            text,
    _loaded_at              timestamptz
);

CREATE TABLE IF NOT EXISTS raw.taxi_zones (
    locationid   integer primary key,
    borough      text,
    zone         text,
    service_zone text
);
