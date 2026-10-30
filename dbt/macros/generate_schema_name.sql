-- Sem este macro, o dbt prefixa o schema do profile ao schema customizado
-- (profile `schema: staging` + `+schema: staging` -> `staging_staging`).
-- Aqui o schema customizado manda: cada camada fica em raw/staging/intermediate/marts,
-- exatamente como descrito no desenho do projeto.
{% macro generate_schema_name(custom_schema_name, node) -%}

    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}

{%- endmacro %}
