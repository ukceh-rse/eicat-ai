from datetime import datetime, timezone
from typing import Dict, List

from beanie import PydanticObjectId
from fastapi import APIRouter, BackgroundTasks, HTTPException

from eicat_ai.agents import data_extraction_agent
from eicat_ai.converters import extract_impacts
from eicat_ai.models import (
    Analysis,
    AnalysisResponse,
    AnalysisStatus,
    Impact,
    Paper,
    PaperDoc,
    PaperStatus,
    SpeciesNames,
)
from eicat_ai.settings import settings

router = APIRouter(prefix="/analyses", tags=["Analyses"])


async def _run_analysis(analysis_id: PydanticObjectId) -> None:
    analysis = await Analysis.get(analysis_id)
    if analysis is None:
        return
    try:
        agent = data_extraction_agent(settings.model)
        results: Dict[str, List[Impact]] = {}
        for paper_id in analysis.paper_ids:
            doc = await PaperDoc.get(paper_id)
            if doc is None or doc.markdown is None:
                continue
            results[str(paper_id)] = await extract_impacts(
                agent, Paper(content=doc.markdown), analysis.species
            )
        analysis.results = results
        analysis.status = AnalysisStatus.COMPLETED
        analysis.completed_at = datetime.now(timezone.utc)
    except Exception as e:
        analysis.status = AnalysisStatus.FAILED
        analysis.error = str(e)
    await analysis.save()


@router.post("/", response_model=AnalysisResponse, status_code=201)
async def create_analysis(species: SpeciesNames) -> AnalysisResponse:
    analysis = Analysis(species=species)
    await analysis.insert()
    return AnalysisResponse.from_doc(analysis)


@router.get("/", response_model=List[AnalysisResponse])
async def list_analyses() -> List[AnalysisResponse]:
    docs = await Analysis.find_all().to_list()
    return [AnalysisResponse.from_doc(d) for d in docs]


@router.get("/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(analysis_id: PydanticObjectId) -> AnalysisResponse:
    analysis = await Analysis.get(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return AnalysisResponse.from_doc(analysis)


@router.post("/{analysis_id}/papers/{paper_id}", response_model=AnalysisResponse)
async def add_paper(analysis_id: PydanticObjectId, paper_id: PydanticObjectId) -> AnalysisResponse:
    analysis = await Analysis.get(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    doc = await PaperDoc.get(paper_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    if doc.status != PaperStatus.READY:
        raise HTTPException(status_code=400, detail="Paper conversion not complete")
    if paper_id not in analysis.paper_ids:
        analysis.paper_ids.append(paper_id)
        await analysis.save()
    return AnalysisResponse.from_doc(analysis)


@router.delete("/{analysis_id}/papers/{paper_id}", response_model=AnalysisResponse)
async def remove_paper(analysis_id: PydanticObjectId, paper_id: PydanticObjectId) -> AnalysisResponse:
    analysis = await Analysis.get(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    analysis.paper_ids = [pid for pid in analysis.paper_ids if pid != paper_id]
    await analysis.save()
    return AnalysisResponse.from_doc(analysis)


@router.post("/{analysis_id}/run", response_model=AnalysisResponse)
async def run_analysis(
    analysis_id: PydanticObjectId, background_tasks: BackgroundTasks
) -> AnalysisResponse:
    analysis = await Analysis.get(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if analysis.status == AnalysisStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Analysis is already running")
    if not analysis.paper_ids:
        raise HTTPException(status_code=400, detail="No papers added to this analysis")
    analysis.status = AnalysisStatus.RUNNING
    await analysis.save()
    background_tasks.add_task(_run_analysis, analysis_id)
    return AnalysisResponse.from_doc(analysis)


@router.delete("/{analysis_id}", status_code=204)
async def delete_analysis(analysis_id: PydanticObjectId) -> None:
    analysis = await Analysis.get(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    await analysis.delete()
