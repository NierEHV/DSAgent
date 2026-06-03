FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY workflows/ ./workflows/
COPY config.yaml ./

RUN mkdir -p data static

ENV PYTHONUNBUFFERED=1
ENV MOCK_MODE=true

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

WORKDIR /app/src
CMD ["python", "main.py", "--host", "0.0.0.0", "--port", "8000"]
