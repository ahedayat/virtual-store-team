from celery import shared_task


@shared_task(name="core.debug_celery_connection")
def debug_celery_connection():
    """Smoke task to verify Celery worker import and Redis connectivity."""
    return {"status": "ok", "message": "Celery worker is connected."}
