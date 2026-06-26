FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY agents/sales/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip \
    && pip install -r /tmp/requirements.txt

COPY agents/__init__.py /app/agents/__init__.py
COPY agents/shared/ /app/agents/shared/
COPY agents/sales/ /app/agents/sales/

EXPOSE 8101

CMD ["uvicorn", "agents.sales.app.main:app", "--host", "0.0.0.0", "--port", "8101"]
