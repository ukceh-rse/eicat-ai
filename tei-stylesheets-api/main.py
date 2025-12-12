from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse
import uvicorn
import subprocess
import tempfile
import os

app: FastAPI = FastAPI()


@app.post("/tei2html", response_class=HTMLResponse)
async def tei_to_html(file: UploadFile = File(...)):
    content = await file.read()

    with tempfile.NamedTemporaryFile(
        mode="wb", suffix=".xml", delete=False
    ) as temp_input:
        temp_input.write(content)
        temp_input_path = temp_input.name

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", delete=False
    ) as temp_output:
        temp_output_path = temp_output.name

    try:
        subprocess.run(["teitohtml", temp_input_path, temp_output_path], check=True)

        with open(temp_output_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        return HTMLResponse(content=html_content)
    finally:
        for temp_file in [temp_input_path, temp_output_path]:
            if os.path.exists(temp_file):
                os.unlink(temp_file)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
