from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import FileResponse
import uuid
from pathlib import Path
from datetime import datetime
from typing import List
from eicat_ai.models import UploadMetadata
from eicat_ai.settings import settings

uploads_router = APIRouter(prefix="/uploads", tags=["Uploads"])


def get_data_path() -> Path:
    return settings.data_path


@uploads_router.post("/", response_model=UploadMetadata)
async def create_upload(
    file: UploadFile = File(...), data_path: Path = Depends(get_data_path)
) -> UploadMetadata:
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    if file.filename is None:
        raise HTTPException(status_code=400, detail="Filename is required")

    content = await file.read()

    upload_metadata = UploadMetadata(
        id=str(uuid.uuid4()),
        filename=file.filename,
        content_type=file.content_type,
        size=len(content),
        timestamp=datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        markdown_available=False,
    )

    upload_metadata.save(data_path)

    file_folder: Path = data_path / upload_metadata.id
    file_folder.mkdir(parents=True, exist_ok=True)

    file_path: Path = file_folder / upload_metadata.filename
    with open(file_path, "wb") as f:
        f.write(content)

    return upload_metadata


@uploads_router.get("/", response_model=List[UploadMetadata])
def list_uploads(data_path: Path = Depends(get_data_path)) -> List[UploadMetadata]:
    """Get details of all uploaded files"""

    return UploadMetadata.load_all(data_path)


@uploads_router.get("/{upload_id}", response_model=UploadMetadata)
def get_upload_by_id(
    upload_id: str, data_path: Path = Depends(get_data_path)
) -> UploadMetadata:
    """Get details of a specific upload by ID"""
    metadata = UploadMetadata.load_by_id(upload_id, data_path)

    if metadata is None:
        raise HTTPException(status_code=404, detail="Upload not found")

    return metadata


@uploads_router.get("/{upload_id}/download")
def download_upload_file(upload_id: str, data_path: Path = Depends(get_data_path)):
    """Download the PDF file for a specific upload"""
    metadata = UploadMetadata.load_by_id(upload_id, data_path)

    if metadata is None:
        raise HTTPException(status_code=404, detail="Upload not found")

    file_folder = data_path / upload_id
    file_path = file_folder / metadata.filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=str(file_path),
        filename=metadata.filename,
        media_type=metadata.content_type,
    )


@uploads_router.delete("/{upload_id}")
def delete_upload_by_id(upload_id: str, data_path: Path = Depends(get_data_path)):
    """Delete an upload by its ID"""
    if UploadMetadata.delete(upload_id, data_path):
        return {"message": f"Upload {upload_id} deleted successfully"}
    else:
        raise HTTPException(status_code=404, detail="Upload not found")
