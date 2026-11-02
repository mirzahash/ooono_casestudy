-- Once only: setup_dbt.py selects the configured database and warehouse.
CREATE SCHEMA IF NOT EXISTS STAGING;
CREATE SCHEMA IF NOT EXISTS ANALYTICS;
CREATE ROLE IF NOT EXISTS OOONO_DBT;
