from contextlib import asynccontextmanager

import uvicorn
from beanie import init_beanie
from beanie.exceptions import RevisionIdWasChanged
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient

from eicat_ai.migration import migrate_legacy_analyses
from eicat_ai.models import Analysis, AuditEvent, PaperDoc
from eicat_ai.routers.analyses import router as analyses_router
from eicat_ai.routers.gbif import router as gbif_router
from eicat_ai.routers.papers import router as papers_router
from eicat_ai.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = AsyncIOMotorClient(settings.mongodb_url)
    await init_beanie(
        database=client[settings.mongodb_db], document_models=[PaperDoc, Analysis, AuditEvent]
    )
    await migrate_legacy_analyses()
    yield
    client.close()


app = FastAPI(lifespan=lifespan)


@app.exception_handler(RevisionIdWasChanged)
async def stale_revision(request: Request, exc: RevisionIdWasChanged) -> JSONResponse:
    # Analysis uses revision checks, so a save over a concurrent change fails instead of overwriting it
    return JSONResponse(status_code=409, content={"detail": "The analysis was changed by another request; reload and retry"})


app.include_router(papers_router)
app.include_router(analyses_router)
app.include_router(gbif_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    uvicorn.run(
        "eicat_ai.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
    )
