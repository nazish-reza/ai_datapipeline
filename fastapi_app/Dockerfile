FROM python:3.11-slim

WORKDIR /app

# Install system deps for datacontract-cli
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# contracts/ lives in the repo root — mount it at runtime via docker-compose
# e.g. volumes: - ./contracts:/app/contracts
ENV CONTRACTS_DIR=/app/contracts

EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]