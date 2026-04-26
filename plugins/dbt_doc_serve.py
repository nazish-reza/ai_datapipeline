from airflow.plugins_manager import AirflowPlugin
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
import os

DBT_TARGET_PATH = "/usr/local/airflow/dbt/target"

dbt_docs_app = FastAPI()

@dbt_docs_app.get("/")
async def serve_index():
    index_path = os.path.join(DBT_TARGET_PATH, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h2>dbt docs not found. Run dbt_docs_generate first.</h2>", status_code=404)

@dbt_docs_app.get("/{filename:path}")
async def serve_file(filename: str):
    file_path = os.path.join(DBT_TARGET_PATH, filename)
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    index_path = os.path.join(DBT_TARGET_PATH, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h2>dbt docs not found. Run dbt_docs_generate first.</h2>", status_code=404)


class DbtDocsPlugin(AirflowPlugin):
    name = "dbt_docs_plugin"

    fastapi_apps = [
        {
            "app": dbt_docs_app,
            "url_prefix": "/dbt-docs",
            "name": "DBT Docs",
        }
    ]

    appbuilder_menu_items = [
        {
            "name": "dbt Docs",
            "category": "dbt",
            "category_icon": "fa-cube",
            "href": "/dbt-docs/",
        }
    ]