"""Read-only connection and object checks; never create or modify cloud objects."""

import argparse
import json
import sys

from snowflake_io import connect, quoted_identifier, read_config


def inspect(cursor, sql):
    cursor.execute(sql)
    columns = [item[0].lower() for item in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-config", action="store_true", help="Validate local settings without logging in")
    args = parser.parse_args()
    try:
        config = read_config()
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 2
    if args.check_config:
        print("Local configuration is present; no connection attempted and no credentials displayed.")
        return 0
    try:
        # Authenticate before selecting cloud objects that may not exist yet.
        login_config = {key: value for key, value in config.items() if key not in {"warehouse", "database", "schema"}}
        with connect(login_config) as connection:
            with connection.cursor() as cursor:
                identity = inspect(cursor, """
                    SELECT CURRENT_ORGANIZATION_NAME() || '-' || CURRENT_ACCOUNT_NAME() AS ACCOUNT_IDENTIFIER,
                           CURRENT_USER() AS USER_NAME, CURRENT_ROLE() AS ROLE_NAME,
                           CURRENT_WAREHOUSE() AS WAREHOUSE_NAME, CURRENT_DATABASE() AS DATABASE_NAME,
                           CURRENT_SCHEMA() AS SCHEMA_NAME
                """)
                print(json.dumps({"connection": identity}, default=str, indent=2))
                # USE statements activate existing objects and verify basic usage access.
                for object_type, field in [("WAREHOUSE", "warehouse"), ("DATABASE", "database")]:
                    cursor.execute(f"USE {object_type} {quoted_identifier(config[field])}")
                cursor.execute(f"USE SCHEMA {quoted_identifier(config['database'])}.{quoted_identifier(config['schema'])}")
                cursor.execute("SELECT 1 AS CONNECTIVITY_CHECK")
                assert cursor.fetchone()[0] == 1
                tables = inspect(cursor, f"SHOW TABLES IN SCHEMA {quoted_identifier(config['database'])}.{quoted_identifier(config['schema'])}")
                print(json.dumps({"raw_tables_visible": [row["name"] for row in tables]}, indent=2))
                grants = inspect(cursor, f"SHOW GRANTS TO ROLE {quoted_identifier(config['role'])}")
                relevant = [
                    {key: row.get(key) for key in ["privilege", "granted_on", "name"]}
                    for row in grants
                    if row.get("privilege") in {"USAGE", "CREATE TABLE", "CREATE STAGE", "OWNERSHIP"}
                    and row.get("granted_on") in {"DATABASE", "SCHEMA", "WAREHOUSE"}
                    and (str(row.get("name", "")).startswith(config["database"].upper())
                         or row.get("name") == config["warehouse"].upper())
                ]
                print(json.dumps({"direct_role_grants": relevant}, default=str, indent=2))
                print("Connection and object usage succeeded. No tables were created or modified.")
                print("Direct grants are diagnostic; inherited/future privileges and write access need validation during setup.")
    except Exception as error:
        # Connector exception text may contain connection details; emit only stable error codes.
        print(json.dumps({"error_type": type(error).__name__, "errno": getattr(error, "errno", None), "sqlstate": getattr(error, "sqlstate", None), "message": "Connection or access check failed; no secrets displayed."}), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
