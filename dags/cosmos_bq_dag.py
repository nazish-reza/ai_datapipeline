from airflow import DAG
from airflow.operators.empty import EmptyOperator
from cosmos import DbtTaskGroup, ProjectConfig, ProfileConfig
from cosmos.profiles import GoogleCloudServiceAccountFileProfileMapping  # For keyfile path
from datetime import datetime, timedelta
import os

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 0,
    'retry_delay': timedelta(minutes=5)
}

DBT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'dbt'))

with DAG(
    dag_id='dbt_bigquery_folder_cosmos',
    default_args=default_args,
    description='DBT BigQuery folder only with service-account',
    schedule='@daily',
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['dbt', 'bigquery']
):
    
    start = EmptyOperator(task_id='start')
    
    dbt_bq_folder = DbtTaskGroup(
        group_id='dbt_bigquery_folder',
        project_config=ProjectConfig(DBT_PATH),
        profile_config=ProfileConfig(
            profile_name="default",
            target_name="bigquery",
            profile_mapping=GoogleCloudServiceAccountFileProfileMapping(
                conn_id="google_cloud_bigquery",  # Your connection
                profile_args={
                    "dataset": "dbt_dataset",
                    "keyfile": "key/bq_key.json"  # Path in container
                }
            )
        ),
        operator_args={
            "install_deps": True,
            # BIGQUERY FOLDER ONLY
            "select": "bigquery/",  # All models in bigquery/ folder
            # Or: "select": "+bigquery.my_model" for specific
        }
    )
    
    end = EmptyOperator(task_id='end')
    
    start >> dbt_bq_folder >> end
