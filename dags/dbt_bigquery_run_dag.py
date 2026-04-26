from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.standard.operators.trigger_dagrun import TriggerDagRunOperator
from datetime import datetime, timedelta
import os

# Define default arguments
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 0,
    'retry_delay': timedelta(minutes=5)
}

# Create DAG
dag = DAG(
    'dbt_bq_models',
    default_args=default_args,
    description='Execute DBT models for BigQuery',
    schedule='@daily',  # or you can use schedule=timedelta(days=1)
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['dbt', 'bigquery']
)

# Define the dbt path relative to the DAGs folder
DBT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'dbt'))
TARGET_PATH = "/usr/local/airflow/dbt/target"
STOP_SIGNAL = "/usr/local/airflow/dbt/.docs_serve_stop"
DONE_SIGNAL = "/usr/local/airflow/dbt/.docs_serve_done"
 

# Task 1: DBT Clean
dbt_clean = BashOperator(
    task_id='dbt_clean_bigquery',
    bash_command=f'cd {DBT_PATH} && dbt deps && dbt clean --profiles-dir . --target bigquery',
    dag=dag
)

# Task 2: DBT Run (only BigQuery models)
dbt_run = BashOperator(
    task_id='dbt_run_bigquery',
    bash_command=f'cd {DBT_PATH} && dbt run --select tag:bigquery --profiles-dir . --target bigquery',
    dag=dag
)

# Task 3: DBT Test (only BigQuery models)
dbt_test = BashOperator(
    task_id='dbt_test_bigquery',
    bash_command=f'cd {DBT_PATH} && dbt test --select tag:bigquery --profiles-dir . --target bigquery',
    dag=dag)

# 4. Generate Docs (NEW)
dbt_docs_generate = BashOperator(
    task_id='dbt_docs_generate',
    bash_command=f'''
    cd {DBT_PATH} && 
    dbt docs generate --select tag:bigquery  --profiles-dir . --target bigquery &&
    dbt docs generate --select tag:bigquery  --no-compile --profiles-dir . --target bigquery
    ''',
    dag=dag
)

 
# Dependencies
dbt_clean >> dbt_run >> dbt_test >> dbt_docs_generate