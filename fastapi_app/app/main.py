from fastapi import FastAPI
import subprocess
import os

app = FastAPI()

process = None

@app.get("/health")
def health():
    return {"status": "running"}

@app.post("/start-job")
def start_job():
    global process
    if process is None:
        process = subprocess.Popen(["python", "worker.py"])
        return {"message": "Job started"}
    return {"message": "Already running"}

@app.post("/stop-job")
def stop_job():
    global process
    if process:
        process.terminate()
        process = None
        return {"message": "Job stopped"}
    return {"message": "No job running"}