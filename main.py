from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI on App Runner!"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}
    