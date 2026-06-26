FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY coordinator/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip \
    && pip install -r /tmp/requirements.txt

COPY shared/ /app/agents/shared/
COPY coordinator/ /app/agents/coordinator/

EXPOSE 8100

CMD ["uvicorn", "agents.coordinator.app.main:app", "--host", "0.0.0.0", "--port", "8100"]
