from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from eicat_ai.uploads import uploads_router
from eicat_ai.analysis import analysis_router

app = FastAPI()
app.include_router(uploads_router)
app.include_router(analysis_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
    ],  # Common React dev server ports
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
