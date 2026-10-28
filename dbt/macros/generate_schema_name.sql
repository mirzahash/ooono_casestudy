{% macro generate_schema_name(custom_schema_name, node) -%}
  {# dbt supplies a default audit schema for tests even when failure storage is off. #}
  {% set schema = (target.schema if node.resource_type == 'test' else (custom_schema_name or target.schema)) | trim | upper %}
  {% if schema not in ['STAGING', 'ANALYTICS'] %}
    {{ exceptions.raise_compiler_error('Only STAGING and ANALYTICS are dbt output schemas in this single-user case.') }}
  {% endif %}
  {{ schema }}
{%- endmacro %}
