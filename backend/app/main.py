from fastapi import FastAPI

app = FastAPI(title="GeoBiz API", version="0.1.0")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

