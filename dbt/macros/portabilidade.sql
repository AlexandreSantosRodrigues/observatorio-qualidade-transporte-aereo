{% macro obs_datetime(expression) -%}
    {% if target.type == 'bigquery' %}
        cast({{ expression }} as datetime)
    {% else %}
        cast({{ expression }} as timestamp)
    {% endif %}
{%- endmacro %}
