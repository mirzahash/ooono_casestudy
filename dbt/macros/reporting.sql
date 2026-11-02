{# Small helpers for run metadata, week boundaries and reference-only tests. #}
{% macro run_id_literal() -%}
  '{{ var("run_id", invocation_id) | replace("'", "''") }}'
{%- endmacro %}

{% macro cutoff_literal() -%}
  '{{ var("receipt_cutoff", run_started_at.isoformat()) | replace("'", "''") }}'::timestamp_tz
{%- endmacro %}

{% macro monday(expression) -%}
  dateadd(day, 1-dayofweekiso({{ expression }}), {{ expression }}::date)::date
{%- endmacro %}

{% macro reference_baseline() -%}
  {{ return(var('validate_baseline', false)) }}
{%- endmacro %}
