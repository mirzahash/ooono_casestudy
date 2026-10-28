{% macro snapshot_literal() -%}
  {% set snapshot = var('snapshot_id') %}
  {% if snapshot | length != 64 or not modules.re.match('^[0-9a-f]{64}$', snapshot) %}
    {{ exceptions.raise_compiler_error('snapshot_id must be a 64-character lowercase SHA-256 identifier') }}
  {% endif %}
  '{{ snapshot }}'
{%- endmacro %}

{% macro cutoff_literal() -%}
  '{{ var("receipt_cutoff") | replace("'", "''") }}'::timestamp_tz
{%- endmacro %}

{% macro monday(expression) -%}
  dateadd(day, 1-dayofweekiso({{ expression }}), {{ expression }}::date)::date
{%- endmacro %}

{% macro reference_baseline() -%}
  {{ return(var('snapshot_id') == 'e943b3aefc3411575c251ada7404c7013b54bf9510e8d37e9e69bd2f80bf863a' and var('receipt_cutoff') == '2026-10-27T15:21:56.773109+00:00') }}
{%- endmacro %}
