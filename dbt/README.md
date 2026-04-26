DBT project for this repo

Quick start

1. Update `profiles.yml` with real credentials (Databricks token, GCP keyfile, or Postgres host/credentials).
2. From the `dbt/` folder run a dbt debug to validate connections:

```bash
cd dbt
dbt debug --profiles-dir .
```

3. Run models by tag:

```bash
# Postgres models
dbt run --profiles-dir . --target dev_postgres --select tag:postgres

# Databricks models
dbt run --profiles-dir . --target databricks --select tag:databricks

# BigQuery models
dbt run --profiles-dir . --target bigquery --select tag:bigquery
```

Notes
- You can set `--profiles-dir` to the dbt folder when running from Airflow; the example DAGs in this repo reference a local `dbt` directory.
- For production, keep credentials out of source control and use Airflow Connections / Secrets backends.
