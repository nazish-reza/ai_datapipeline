FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src

ENV FASTMCP_HOST=0.0.0.0
ENV FASTMCP_PORT=9000

CMD ["python", "src/server.py"]