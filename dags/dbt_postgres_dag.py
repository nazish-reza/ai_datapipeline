from airflow import DAG
from airflow.operators.bash import BashOperator  # This is the correct import for Airflow 2.x
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
    'dbt_postgres_models',
    default_args=default_args,
    description='Execute DBT models for Postgres',
    schedule='@daily',  # or you can use schedule=timedelta(days=1)
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['dbt', 'postgres']
)

# Define the dbt path relative to the DAGs folder
DBT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'dbt'))

# Task 1: DBT Dependencies
dbt_deps = BashOperator(
    task_id='dbt_deps',
    bash_command=f'cd {DBT_PATH} && dbt deps --profiles-dir .',
    dag=dag
)

# Task 2: DBT Run (only Postgres models)
dbt_run = BashOperator(
    task_id='dbt_run_postgres',
    bash_command=f'cd {DBT_PATH} && dbt run --profiles-dir . --target dev_postgres --select postgres.*',
    dag=dag
)

# Task 3: DBT Test (only Postgres models)
dbt_test = BashOperator(
    task_id='dbt_test_postgres',
    bash_command=f'cd {DBT_PATH} && dbt test --profiles-dir . --target dev_postgres --select postgres.*',
    dag=dag)

# Set task dependencies
dbt_deps >> dbt_run >> dbt_test