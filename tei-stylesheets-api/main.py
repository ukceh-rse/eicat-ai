import asyncio
import subprocess
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse

app: FastAPI = FastAPI()


def _convert(xml_bytes: bytes) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        input_path = tmp_path / "input.xml"
        output_path = tmp_path / "output.html"
        input_path.write_bytes(xml_bytes)
        subprocess.run(["teitohtml", str(input_path), str(output_path)], check=True)
        return output_path.read_text(encoding="utf-8")


@app.post("/tei2html", response_class=HTMLResponse)
async def tei_to_html(file: UploadFile = File(...)) -> HTMLResponse:
    content = await file.read()
    html = await asyncio.to_thread(_convert, content)
    return HTMLResponse(content=html)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
