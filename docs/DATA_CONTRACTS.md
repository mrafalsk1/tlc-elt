# Contrato de dados — Projeto A (ELT NYC TLC)

Este documento descreve cada tabela/modelo do pipeline, colunas, tipos, nulabilidade, chave primária e significado de negócio.

## 1. raw.yellow_trips (staging source)

| Coluna | Tipo | Nulo | PK | Significado |
|--------|------|------|----|-------------|
| vendorid | integer | SIM | NÃO | Provedor do registro (1=Creative Mobile, 2=VeriFone) |
| tpep_pickup_datetime | timestamp | SIM | NÃO | Início da corrida |
| tpep_dropoff_datetime | timestamp | SIM | NÃO | Fim da corrida |
| passenger_count | double precision | SIM | NÃO | Número de passageiros |
| trip_distance | double precision | SIM | NÃO | Distância em milhas |
| ratecodeid | double precision | SIM | NÃO | Código da tarifa |
| store_and_fwd_flag | text | SIM | NÃO | Flag de armazenamento e encaminhamento |
| pulocationid | integer | SIM | NÃO | LocationID da zona de embarque |
| dolocationid | integer | SIM | NÃO | LocationID da zona de desembarque |
| payment_type | integer | SIM | NÃO | Tipo de pagamento (0-6) |
| fare_amount | double precision | SIM | NÃO | Tarifa do taxímetro |
| extra | double precision | SIM | NÃO | Taxas extras |
| mta_tax | double precision | SIM | NÃO | Imposto MTA |
| tip_amount | double precision | SIM | NÃO | Valor da gorjeta |
| tolls_amount | double precision | SIM | NÃO | Pedágios |
| improvement_surcharge | double precision | SIM | NÃO | Sobretaxa de melhoria |
| total_amount | double precision | SIM | NÃO | Total cobrado |
| congestion_surcharge | double precision | SIM | NÃO | Sobretaxa de congestionamento |
| airport_fee | double precision | SIM | NÃO | Taxa de aeroporto |
| _source_file | text | SIM | NÃO | Nome do arquivo Parquet de origem |
| _loaded_at | timestamptz | SIM | NÃO | Timestamp de carregamento |

Chave natural (não é PK física): vendorid + tpep_pickup_datetime + tpep_dropoff_datetime + total_amount

## 2. raw.taxi_zones (staging source)

| Coluna | Tipo | Nulo | PK | Significado |
|--------|------|------|----|-------------|
| locationid | integer | NÃO | SIM | LocationID da TLC (chave primária) |
| borough | text | SIM | NÃO | Distrito (Manhattan, Queens, etc.) |
| zone | text | SIM | NÃO | Nome da zona |
| service_zone | text | SIM | NÃO | Zona de serviço (Boro Zone / Yellow Zone) |

## 3. staging.stg_yellow_trips (view)

| Coluna | Tipo | Nulo | Testes | Significado |
|--------|------|------|--------|-------------|
| vendor_id | integer | SIM | - | Renomeado de vendorid |
| pickup_at | timestamp | NÃO | not_null | Início da corrida |
| dropoff_at | timestamp | NÃO | not_null | Fim da corrida |
| pickup_zone_id | integer | NÃO | not_null | Zona de embarque |
| dropoff_zone_id | integer | NÃO | not_null | Zona de desembarque |
| payment_type | integer | SIM | accepted_values [0-6] | Tipo de pagamento |
| fare_amount | double precision | NÃO | not_null (> 0 após filtro) | Tarifa do taxímetro |
| total_amount | double precision | NÃO | not_null | Total cobrado |
| trip_duration_min | numeric | NÃO | not_null | Duração em minutos |
| speed_mph | numeric | SIM | - | Velocidade média (mph) |
| tip_pct | numeric | SIM | - | Gorjeta como fração da tarifa |

Filtros aplicados: fare_amount > 0, trip_distance >= 0, dropoff_at > pickup_at. Deduplicação por chave natural (mantém _loaded_at mais recente).

## 4. staging.stg_taxi_zones (view)

| Coluna | Tipo | Nulo | Testes | Significado |
|--------|------|------|--------|-------------|
| zone_id | integer | NÃO | unique, not_null | LocationID da TLC (PK) |
| borough | text | NÃO | not_null, accepted_values | Distrito |
| zone | text | NÃO | not_null | Nome da zona |
| service_zone | text | NÃO | - | Zona de serviço |

## 5. intermediate.int_trips_enriched (view)

| Coluna | Tipo | Nulo | Testes | Significado |
|--------|------|------|--------|-------------|
| (todas as colunas de stg_yellow_trips) | - | - | - | - |
| pickup_borough | text | NÃO | not_null | Distrito de embarque |
| pickup_zone | text | NÃO | not_null | Zona de embarque |
| dropoff_borough | text | NÃO | not_null | Distrito de desembarque |
| dropoff_zone | text | NÃO | not_null | Zona de desembarque |
| is_airport_trip | boolean | NÃO | - | Embarque em JFK/LGA/EWR |
| is_night_trip | boolean | NÃO | - | Embarque entre 22h-6h |
| has_zero_distance | boolean | NÃO | - | trip_distance = 0 |
| is_long_trip | boolean | NÃO | - | trip_duration_min > 360 |
| is_fast_trip | boolean | NÃO | - | speed_mph > 60 |
| is_out_of_period | boolean | NÃO | - | Corrida fora do mês do arquivo |
| is_valid_trip | boolean | NÃO | not_null | Nenhuma das condições acima |

Nenhuma linha é descartada. Filtros de negócio são flags para o consumidor decidir.

## 6. marts.fct_trips (tabela, incremental)

| Coluna | Tipo | Nulo | Testes | Significado |
|--------|------|------|--------|-------------|
| trip_id | text | NÃO | unique, not_null | md5 da chave natural (PK) |
| pickup_zone_id | integer | NÃO | not_null, relationships → dim_zones(zone_id) | Zona de embarque |
| dropoff_zone_id | integer | NÃO | not_null, relationships → dim_zones(zone_id) | Zona de desembarque |
| payment_type | integer | SIM | accepted_values [0-6] | Tipo de pagamento |
| is_valid_trip | boolean | NÃO | not_null | Flag de qualidade herdada |
| (demais colunas de int_trips_enriched) | - | - | - | - |

Incremental por mês com delete+insert. Rodar 2x = mesmo resultado (idempotente).

## 7. marts.dim_zones (tabela)

| Coluna | Tipo | Nulo | Testes | Significado |
|--------|------|------|--------|-------------|
| zone_id | integer | NÃO | unique, not_null | LocationID da TLC (PK) |
| borough | text | SIM | - | Distrito |
| zone | text | SIM | - | Nome da zona |
| service_zone | text | SIM | - | Zona de serviço |
| is_airport | boolean | NÃO | not_null | True para JFK, LaGuardia, Newark |

## 8. marts.agg_daily_demand (tabela)

| Coluna | Tipo | Nulo | Testes | Significado |
|--------|------|------|--------|-------------|
| trip_date | date | NÃO | not_null | Data da corrida |
| zone_id | integer | NÃO | not_null | Zona de embarque |
| trips | integer | NÃO | not_null | Contagem de corridas válidas |
| revenue | numeric | SIM | - | Receita total (total_amount) |
| avg_ticket | numeric | SIM | - | Ticket médio |
| avg_distance_miles | numeric | SIM | - | Distância média |
| avg_duration_min | numeric | SIM | - | Duração média |
| avg_speed_mph | numeric | SIM | - | Velocidade média |

Grão: dia × zona. Apenas is_valid_trip.

## 9. marts.agg_payment_behavior (tabela)

| Coluna | Tipo | Nulo | Testes | Significado |
|--------|------|------|--------|-------------|
| payment_method | text | NÃO | not_null, accepted_values | Forma de pagamento (credit_card, cash, etc.) |
| tip_bucket | text | NÃO | not_null | Faixa de gorjeta (0%, (0,10%], etc.) |
| trips | integer | SIM | - | Contagem de corridas |
| avg_tip_pct | numeric | SIM | - | Gorjeta média (% da tarifa) |
| total_tips | numeric | SIM | - | Total de gorjetas |
| avg_ticket | numeric | SIM | - | Ticket médio |
| total_fare | numeric | SIM | - | Total de tarifas |

Grão: método × faixa de gorjeta. Apenas is_valid_trip.

## Regras de mudança de schema

- Adição de coluna: classificar como aditiva; atualizar este contrato e testes de contrato.
- Remoção ou alteração de tipo: classificar como breaking; exigir atualização de todos os modelos downstream e testes.
- Nunca remover coluna usada por relação de chave estrangeira (ex: pickup_zone_id → dim_zones).
