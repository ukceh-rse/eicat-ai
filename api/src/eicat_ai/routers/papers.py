import asyncio
from typing import List

from beanie import PydanticObjectId
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import Response

from eicat_ai.converters import pdf_to_tei_xml, tei_xml_to_markdown
from eicat_ai.models import PaperDoc, PaperResponse, PaperStatus

router = APIRouter(prefix="/papers", tags=["Papers"])


async def _convert_paper(paper_id: PydanticObjectId) -> None:
    doc = await PaperDoc.get(paper_id)
    if doc is None:
        return
    try:
        tei_xml = await asyncio.to_thread(pdf_to_tei_xml, doc.pdf_data)
        doc.tei_xml = tei_xml
        await doc.save()
        doc.markdown = await asyncio.to_thread(tei_xml_to_markdown, tei_xml)
        doc.status = PaperStatus.READY
    except Exception as e:
        doc.status = PaperStatus.FAILED
        doc.error = str(e)
    await doc.save()


@router.post("/", response_model=PaperResponse, status_code=201)
async def upload_paper(
    background_tasks: BackgroundTasks, file: UploadFile = File(...)
) -> PaperResponse:
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    pdf_data = await file.read()
    doc = PaperDoc(
        filename=file.filename or "unknown.pdf",
        content_type=file.content_type,
        size=len(pdf_data),
        pdf_data=pdf_data,
    )
    await doc.insert()
    background_tasks.add_task(_convert_paper, doc.id)
    return PaperResponse.from_doc(doc)


@router.get("/", response_model=List[PaperResponse])
async def list_papers() -> List[PaperResponse]:
    docs = await PaperDoc.find_all().to_list()
    return [PaperResponse.from_doc(d) for d in docs]


@router.get("/{paper_id}", response_model=PaperResponse)
async def get_paper(paper_id: PydanticObjectId) -> PaperResponse:
    doc = await PaperDoc.get(paper_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    return PaperResponse.from_doc(doc)


@router.get("/{paper_id}/tei")
async def get_paper_tei(paper_id: PydanticObjectId):
    doc = await PaperDoc.get(paper_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    if doc.tei_xml is None:
        raise HTTPException(status_code=404, detail="TEI XML not yet available")
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(doc.tei_xml, media_type="application/xml")


@router.get("/{paper_id}/content")
async def get_paper_content(paper_id: PydanticObjectId):
    doc = await PaperDoc.get(paper_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    if doc.markdown is None:
        raise HTTPException(status_code=404, detail="Markdown not yet available")
    return {"content": doc.markdown}


@router.get("/{paper_id}/download")
async def download_paper(paper_id: PydanticObjectId):
    doc = await PaperDoc.get(paper_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    return Response(
        content=doc.pdf_data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{doc.filename}"'},
    )


@router.delete("/{paper_id}", status_code=204)
async def delete_paper(paper_id: PydanticObjectId) -> None:
    doc = await PaperDoc.get(paper_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    await doc.delete()
