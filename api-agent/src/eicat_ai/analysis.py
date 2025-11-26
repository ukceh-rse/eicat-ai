from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pathlib import Path
from typing import Dict, Optional
import uuid
import asyncio
from datetime import datetime
from pydantic_ai import Agent
from eicat_ai.models import UploadMetadata, Paper
from eicat_ai.settings import settings
from eicat_ai.converters import pdf_to_markdown
from eicat_ai.agents import paper_agent

analysis_router = APIRouter(prefix="/analysis", tags=["Analysis"])

task_status: Dict[str, Dict] = {}


def get_data_path() -> Path:
    return settings.data_path


async def background_convert_pdf(upload_id: str, task_id: str, data_path: Path):
    """Background task to convert PDF to markdown"""
    try:
        task_status[task_id] = {
            "status": "processing",
            "progress": "Starting conversion...",
            "timestamp": datetime.now().isoformat(),
        }

        metadata = UploadMetadata.load_by_id(upload_id, data_path)

        if metadata is None:
            task_status[task_id] = {
                "status": "failed",
                "error": "Upload not found",
                "timestamp": datetime.now().isoformat(),
            }
            return

        file_folder = data_path / upload_id
        file_path = file_folder / metadata.filename

        if not file_path.exists():
            task_status[task_id] = {
                "status": "failed",
                "error": "File not found",
                "timestamp": datetime.now().isoformat(),
            }
            return

        task_status[task_id] = {
            "status": "processing",
            "progress": "Converting PDF to markdown...",
            "timestamp": datetime.now().isoformat(),
        }

        model: str = "bedrock:anthropic.claude-3-7-sonnet-20250219-v1:0"

        agent: Agent[None, Paper] = paper_agent(model)
        paper: Paper = await pdf_to_markdown(agent, str(file_path))
        paper.metadata["timestamp"] = datetime.now().isoformat()
        paper.metadata["model"] = model

        paper.save(file_folder / "converted.json")

        # Update metadata to indicate markdown is available
        metadata.markdown_available = True
        metadata.save(data_path)

        task_status[task_id] = {
            "status": "completed",
            "progress": "Conversion completed successfully",
            "timestamp": datetime.now().isoformat(),
            "result_available": True,
        }

    except Exception as e:
        task_status[task_id] = {
            "status": "failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


@analysis_router.post("/to-markdown/{upload_id}")
async def start_pdf_to_markdown(
    upload_id: str,
    background_tasks: BackgroundTasks,
    data_path: Path = Depends(get_data_path),
):
    """Start PDF to markdown conversion in background"""
    # Verify upload exists
    metadata = UploadMetadata.load_by_id(upload_id, data_path)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Upload not found")

    file_folder = data_path / upload_id
    file_path = file_folder / metadata.filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    # Create task
    task_id = str(uuid.uuid4())
    task_status[task_id] = {
        "status": "started",
        "progress": "Task queued",
        "upload_id": upload_id,
        "timestamp": datetime.now().isoformat(),
    }

    # Add background task with data_path parameter
    background_tasks.add_task(background_convert_pdf, upload_id, task_id, data_path)

    return {
        "task_id": task_id,
        "upload_id": upload_id,
        "status": "started",
        "message": "PDF to markdown conversion task started",
    }


@analysis_router.get("/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    """Get the status of a conversion task"""
    if task_id not in task_status:
        raise HTTPException(status_code=404, detail="Task not found")

    return task_status[task_id]


@analysis_router.get("/tasks/{task_id}/result", response_model=Paper)
async def get_conversion_result(task_id: str, data_path: Path = Depends(get_data_path)):
    """Get the converted paper result"""
    if task_id not in task_status:
        raise HTTPException(status_code=404, detail="Task not found")

    task = task_status[task_id]

    if task["status"] == "failed":
        raise HTTPException(
            status_code=400, detail=f"Task failed: {task.get('error', 'Unknown error')}"
        )

    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="Task not completed yet")

    # Get upload_id from task
    upload_id = task.get("upload_id")
    if not upload_id:
        raise HTTPException(status_code=500, detail="Upload ID not found in task")

    # Load result from file
    file_folder = data_path / upload_id
    result_path = file_folder / "converted.json"

    if not result_path.exists():
        raise HTTPException(status_code=404, detail="Conversion result not found")

    try:
        with open(result_path, "r") as f:
            paper_data = f.read()
        return Paper.model_validate_json(paper_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading result: {str(e)}")


@analysis_router.get("/get-markdown/{upload_id}", response_model=Paper)
async def get_converted_paper_by_upload(
    upload_id: str, data_path: Path = Depends(get_data_path)
):
    """Get the converted paper result by upload ID"""
    # Verify upload exists
    metadata = UploadMetadata.load_by_id(upload_id, data_path)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Upload not found")

    # Check if conversion result exists
    file_folder = data_path / upload_id
    result_path = file_folder / "converted.json"

    if not result_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Paper has not been converted to markdown yet. Please start conversion first.",
        )

    try:
        with open(result_path, "r") as f:
            paper_data = f.read()
        return Paper.model_validate_json(paper_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading result: {str(e)}")


@analysis_router.get("/tasks")
async def list_all_tasks():
    """List all conversion tasks"""
    return {
        "tasks": [
            {"task_id": task_id, **task_info}
            for task_id, task_info in task_status.items()
        ],
        "total_tasks": len(task_status),
    }
