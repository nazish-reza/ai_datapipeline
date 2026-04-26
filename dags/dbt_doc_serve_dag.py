from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator
from datetime import datetime

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 0,
}

dag = DAG(
    'dbt_docs_serve',
    default_args=default_args,
    description='Serves dbt docs continuously on port 8081 — triggered by dbt_bq_models DAG',
    schedule=None,
    start_date=datetime(2025, 1, 1),
    catchup=False,
    is_paused_upon_creation=False,
    tags=['dbt', 'bigquery']
)

DBT_PATH = "/usr/local/airflow/dbt"
TARGET_PATH = "/usr/local/airflow/dbt/target"
STOP_SIGNAL = "/usr/local/airflow/dbt/.docs_serve_stop"
DONE_SIGNAL = "/usr/local/airflow/dbt/.docs_serve_done"

dbt_serve = BashOperator(
    task_id='dbt_docs_serve',
    bash_command=f'''
        # Clean up signals from previous runs
        rm -f {STOP_SIGNAL} {DONE_SIGNAL}

        # Wait for port 8081 to be free before starting
        echo "Waiting for port 8081 to be free..."
        while bash -c "echo > /dev/tcp/localhost/8081" 2>/dev/null; do
            echo "Port 8081 still in use, waiting..."
            # Actively kill whatever is on the port while waiting
            fuser -k 8081/tcp 2>/dev/null || true
            sleep 2
        done
        echo "Port 8081 is free — starting dbt docs serve"

        # Start dbt docs serve in background
        cd {DBT_PATH} && dbt docs serve \
            --profiles-dir . \
            --target bigquery \
            --target-path {TARGET_PATH} \
            --port 8081 \
            --host 0.0.0.0 &

        DBT_PID=$!
        echo "dbt docs serve started with PID $DBT_PID"

        # Poll every 3 seconds for stop signal
        while kill -0 $DBT_PID 2>/dev/null; do
            if [ -f {STOP_SIGNAL} ]; then
                echo "Stop signal received — killing all processes on port 8081"
                # fuser kills ALL processes holding the port — parent + children
                fuser -k 8081/tcp 2>/dev/null || true
                kill -9 $DBT_PID 2>/dev/null || true
                sleep 1
                rm -f {STOP_SIGNAL}
                touch {DONE_SIGNAL}
                exit 0
            fi
            sleep 3
        done

        exit 0
    ''',
    execution_timeout=None,
    dag=dag
)