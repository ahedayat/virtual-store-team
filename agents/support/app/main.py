from fastapi import FastAPI

SERVICE_NAME = "support-agent"

app = FastAPI(title=SERVICE_NAME)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


@app.get("/")
def root() -> dict[str, str]:
    return {"service": SERVICE_NAME, "message": "placeholder"}
