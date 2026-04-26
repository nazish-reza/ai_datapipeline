Overview
========

Welcome to Astronomer! This project was generated after you ran 'astro dev init' using the Astronomer CLI. This readme describes the contents of the project, as well as how to run Apache Airflow on your local machine.

Project Contents
================

Your Astro project contains the following files and folders:

- dags: This folder contains the Python files for your Airflow DAGs. By default, this directory includes one example DAG:
    - `example_astronauts`: This DAG shows a simple ETL pipeline example that queries the list of astronauts currently in space from the Open Notify API and prints a statement for each astronaut. The DAG uses the TaskFlow API to define tasks in Python, and dynamic task mapping to dynamically print a statement for each astronaut. For more on how this DAG works, see our [Getting started tutorial](https://www.astronomer.io/docs/learn/get-started-with-airflow).
- Dockerfile: This file contains a versioned Astro Runtime Docker image that provides a differentiated Airflow experience. If you want to execute other commands or overrides at runtime, specify them here.
- include: This folder contains any additional files that you want to include as part of your project. It is empty by default.
- packages.txt: Install OS-level packages needed for your project by adding them to this file. It is empty by default.
- requirements.txt: Install Python packages needed for your project by adding them to this file. It is empty by default.
- plugins: Add custom or community plugins for your project to this file. It is empty by default.
- airflow_settings.yaml: Use this local-only file to specify Airflow Connections, Variables, and Pools instead of entering them in the Airflow UI as you develop DAGs in this project.

Deploy Your Project Locally
===========================

Start Airflow on your local machine by running 'astro dev start'.

This command will spin up five Docker containers on your machine, each for a different Airflow component:

- Postgres: Airflow's Metadata Database
- Scheduler: The Airflow component responsible for monitoring and triggering tasks
- DAG Processor: The Airflow component responsible for parsing DAGs
- API Server: The Airflow component responsible for serving the Airflow UI and API
- Triggerer: The Airflow component responsible for triggering deferred tasks

When all five containers are ready the command will open the browser to the Airflow UI at http://localhost:8080/. You should also be able to access your Postgres Database at 'localhost:5432/postgres' with username 'postgres' and password 'postgres'.

Note: If you already have either of the above ports allocated, you can either [stop your existing Docker containers or change the port](https://www.astronomer.io/docs/astro/cli/troubleshoot-locally#ports-are-not-available-for-my-local-airflow-webserver).

Deploy Your Project to Astronomer
=================================

If you have an Astronomer account, pushing code to a Deployment on Astronomer is simple. For deploying instructions, refer to Astronomer documentation: https://www.astronomer.io/docs/astro/deploy-code/

Contact
=======

The Astronomer CLI is maintained with love by the Astronomer team. To report a bug or suggest a change, reach out to our support.

# Airflow + FastAPI (Astro CLI) Local Development Setup

This project runs:

-   Apache Airflow via Astro CLI
-   A separate FastAPI container
-   PostgreSQL (via Astro)

FastAPI is built separately and then started together with Airflow using
`astro dev start`.

------------------------------------------------------------------------

## 📦 Project Structure

. ├── dags/ ├── plugins/ ├── include/ ├── dbt/ ├── fastapi_app/ │ ├──
Dockerfile │ ├── requirements.txt │ └── app/ │ └── main.py ├──
docker-compose.override.yml ├── requirements.txt ├── Dockerfile └──
README.md

------------------------------------------------------------------------

## 🐳 Step 1 --- Build FastAPI Image Separately

From the project root directory, run:

``` bash
docker build -t airflow-dbt_b57794-fastapi:latest ./fastapi_app
docker build -t airflow-dbt_b57794-mcp:latest ./mcp_server
```

Verify the image exists:

``` bash
docker images | grep fastapi
```

------------------------------------------------------------------------

## ⚙️ Step 2 --- docker-compose.override.yml

Make sure your override file looks like this:

``` yaml
services:
  fastapi:
    image: airflow-dbt_b57794-fastapi:latest
    ports:
      - "8000:8000"
```

Important: - Do NOT use `build:` here - Do NOT use
`${COMPOSE_PROJECT_NAME}` - Use the exact image name you built

------------------------------------------------------------------------

## 🚀 Step 3 --- Start the Project

Start everything:

``` bash
astro dev start
```

------------------------------------------------------------------------

## 🔎 Step 4 --- Verify Containers

``` bash
astro dev ps
```

Or:

``` bash
docker ps
```

------------------------------------------------------------------------

## 🌐 Step 5 --- Access Services

Airflow UI: http://localhost:8080

FastAPI Swagger UI: http://localhost:8000/docs

------------------------------------------------------------------------

## 🛑 Stopping Services

Stop containers (keep them created):

``` bash
astro dev stop
```

Kill and remove containers:

``` bash
astro dev kill
```

Full cleanup including unused volumes:

``` bash
astro dev kill
docker volume prune -f
docker system prune -af 
```

------------------------------------------------------------------------

## 🔁 Rebuilding FastAPI

If you make changes inside `fastapi_app/`, rebuild the image:

``` bash
docker build -t airflow-dbt_b57794-fastapi:latest ./fastapi_app
```

Then restart Astro:

``` bash
astro dev restart
```

------------------------------------------------------------------------

## 📌 Common Issues

### ❌ "No such image airflow-dbt_b57794-fastapi"

You forgot to build the FastAPI image.

Run:

``` bash
docker build -t airflow-dbt_b57794-fastapi:latest ./fastapi_app
```

### ❌ Port 8000 already in use

Find the process:

``` bash
lsof -i :8000
```

Stop it, then restart Astro.

------------------------------------------------------------------------

## 🎯 Summary Workflow

1.  Build FastAPI image\
2.  Run `astro dev start`\
3.  Develop\
4.  Stop with `astro dev stop`

