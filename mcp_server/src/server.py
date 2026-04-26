import os
import requests
from datetime import datetime, timezone
from typing import Optional
from fastmcp import FastMCP

mcp = FastMCP("airflow-dbt-mcp")

AIRFLOW_URL = os.getenv("AIRFLOW_URL", "http://api-server:8080")
AIRFLOW_USERNAME = os.getenv("AIRFLOW_USERNAME", "admin")
AIRFLOW_PASSWORD = os.getenv("AIRFLOW_PASSWORD", "admin")

DBT_PROJECT_PATH = "/shared/dbt"
DAGS_PATH = "/shared/dags"


def get_airflow_token():
    r = requests.post(
        f"{AIRFLOW_URL}/auth/token",
        json={
            "username": AIRFLOW_USERNAME,
            "password": AIRFLOW_PASSWORD
        },
    )
    r.raise_for_status()
    return r.json()["access_token"]


def airflow_headers():
    token = get_airflow_token()
    return {"Authorization": f"Bearer {token}"}


@mcp.tool()
def list_dags():
    """List Airflow DAGs"""
    r = requests.get(
        f"{AIRFLOW_URL}/api/v2/dags",
        headers=airflow_headers()
    )
    r.raise_for_status()
    return r.json()


@mcp.tool()
def unpause_dag(dag_id: str):
    """Unpause a DAG in Airflow"""
    r = requests.patch(
        f"{AIRFLOW_URL}/api/v2/dags/{dag_id}",
        headers=airflow_headers(),
        json={"is_paused": False}
    )
    r.raise_for_status()
    return r.json()


@mcp.tool()
def trigger_dag(dag_id: str, conf: Optional[dict] = None) -> dict:
    """Trigger a DAG run in Airflow"""
    payload = {
        "logical_date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "conf": conf or {}
    }
    r = requests.post(
        f"{AIRFLOW_URL}/api/v2/dags/{dag_id}/dagRuns",
        headers=airflow_headers(),
        json=payload
    )
    r.raise_for_status()
    return r.json()


@mcp.tool()
def list_dag_runs(dag_id: str):
    """List DAG runs"""
    r = requests.get(
        f"{AIRFLOW_URL}/api/v2/dags/{dag_id}/dagRuns",
        headers=airflow_headers()
    )
    r.raise_for_status()
    return r.json()


@mcp.tool()
def list_dag_tasks(dag_id: str):
    """List tasks in a DAG"""
    r = requests.get(
        f"{AIRFLOW_URL}/api/v2/dags/{dag_id}/tasks",
        headers=airflow_headers()
    )
    r.raise_for_status()
    return r.json()

@mcp.tool()
def get_task_instances(dag_id: str, dag_run_id: str) -> dict:
    """List all task instances for a specific DAG run, including their state"""
    r = requests.get(
        f"{AIRFLOW_URL}/api/v2/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances",
        headers=airflow_headers(),
    )
    r.raise_for_status()
    return r.json()


@mcp.tool()
def get_latest_task_logs(dag_id: str, task_id: str) -> dict:
    """
    Get logs of the latest run of a specific task in a DAG.
    Args:
        dag_id:   The DAG ID
        task_id:  The task ID within the DAG
    """
    # Step 1: get the latest dag run
    r = requests.get(
        f"{AIRFLOW_URL}/api/v2/dags/{dag_id}/dagRuns",
        headers=airflow_headers(),
        params={"order_by": "-start_date", "limit": 1},
    )
    r.raise_for_status()
    runs = r.json().get("dag_runs", [])

    if not runs:
        return {"error": f"No runs found for DAG '{dag_id}'"}

    dag_run_id = runs[0]["dag_run_id"]
    dag_state = runs[0]["state"]

    # Step 2: get task instance to find try_number
    r = requests.get(
        f"{AIRFLOW_URL}/api/v2/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances/{task_id}",
        headers=airflow_headers(),
    )
    r.raise_for_status()
    task_instance = r.json()
    try_number = task_instance.get("try_number", 1)
    task_state = task_instance.get("state")

    # Step 3: fetch logs — Airflow 3 uses try_number as query param
    r = requests.get(
        f"{AIRFLOW_URL}/api/v2/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances/{task_id}/logs",
        headers=airflow_headers(),
        params={"try_number": try_number, "full_content": True},
    )
    r.raise_for_status()

    return {
        "dag_run_id": dag_run_id,
        "dag_state": dag_state,
        "task_id": task_id,
        "task_state": task_state,
        "try_number": try_number,
        "logs": r.json(),
    }


@mcp.tool()
def run_dbt_model(model: str):
    """Run a dbt model"""
    import subprocess

    result = subprocess.run(
        ["dbt", "run", "--select", model],
        cwd=DBT_PROJECT_PATH,
        capture_output=True,
        text=True
    )

    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode
    }


@mcp.tool()
def list_dbt_models():
    """List dbt models"""
    import subprocess

    result = subprocess.run(
        ["dbt", "ls", "--resource-type", "model"],
        cwd=DBT_PROJECT_PATH,
        capture_output=True,
        text=True
    )

    return result.stdout.splitlines()



if __name__ == "__main__":
    mcp.run(transport="sse")