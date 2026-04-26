from airflow.sdk import dag, task
from datetime import datetime, timedelta

@dag(
    dag_id="check_dag",
    start_date=datetime(2025, 1, 1),
    schedule='@daily',
    catchup=False,
    description="A simple DAG to check if Airflow is running",
    tags=["example"])

def check_dag():

    @task.bash
    def create_file():
        return 'echo "Hi there!" >/tmp/dummy'
    
    @task.bash
    def check_file_exists():
        return 'test -f /tmp/dummy'
    
    @task
    def read_file():
        print(open('/tmp/dummy', 'rb').read())

    create_file() >> check_file_exists() >> read_file()

check_dag()