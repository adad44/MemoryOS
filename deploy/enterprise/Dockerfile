FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MEMORYOS_ENTERPRISE_HOST=0.0.0.0 \
    MEMORYOS_ENTERPRISE_PORT=8775

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
COPY ml/requirements-runtime.txt /app/ml/requirements-runtime.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r /app/backend/requirements.txt

COPY enterprise /app/enterprise
COPY ml /app/ml

EXPOSE 8775
CMD ["python", "-m", "enterprise.backend.app"]
