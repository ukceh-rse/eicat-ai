from contextlib import asynccontextmanager

import uvicorn
from beanie import init_beanie
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

from eicat_ai.models import Analysis, PaperDoc
from eicat_ai.routers.analyses import router as analyses_router
from eicat_ai.routers.gbif import router as gbif_router
from eicat_ai.routers.papers import router as papers_router
from eicat_ai.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = AsyncIOMotorClient(settings.mongodb_url)
    await init_beanie(
        database=client[settings.mongodb_db], document_models=[PaperDoc, Analysis]
    )
    yield
    client.close()


app = FastAPI(lifespan=lifespan)

app.include_router(papers_router)
app.include_router(analyses_router)
app.include_router(gbif_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    uvicorn.run(
        "eicat_ai.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
    )
