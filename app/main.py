from datetime import datetime

from fastapi import FastAPI

from .db import init_schema
from .routes import controls, documents, evaluation

app = FastAPI(title="Azure Compliance Processing Pipeline")


@app.on_event("startup")
def startup_event():
    # Initialize database schema; later we will also load controls, models, etc.
    init_schema()


app.include_router(documents.router)
app.include_router(controls.router)
app.include_router(evaluation.router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "service": "azure-compliance-processing-pipeline",
    }


