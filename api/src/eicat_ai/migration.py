from datetime import datetime, timezone
from typing import Dict, List, Optional

from beanie import PydanticObjectId
from loguru import logger

from eicat_ai.anchoring import anchor
from eicat_ai.models import (
    ActorKind,
    Analysis,
    AnalysisRun,
    AuditEvent,
    ImpactOrigin,
    PaperDoc,
    ReviewedImpact,
    RunStatus,
)
from eicat_ai.review import Event


async def migrate_legacy_analyses() -> None:
    """Give analyses from before the review layer their impacts (design D9): one synthetic `legacy` run, and each
    result as an active, unverified AI impact with anchored evidence. Analyses with any run are skipped, so running
    this again changes nothing, and `results` is left as it is."""
    markdown: Dict[str, Optional[str]] = {}
    analyses = impacts = spans = anchored = 0
    for analysis in await Analysis.find_all().to_list():
        if analysis.runs or not analysis.results:
            continue
        at = analysis.completed_at or analysis.created_at or datetime.now(timezone.utc)
        run = AnalysisRun(
            started_at=at, completed_at=at, model="legacy", usage=analysis.usage, status=RunStatus.COMPLETED,
        )
        events: List[Event] = []
        for paper_id, results in analysis.results.items():
            if paper_id not in markdown:
                doc = await PaperDoc.get(PydanticObjectId(paper_id))
                markdown[paper_id] = doc.markdown if doc else None
            for ai in results:
                evidence = anchor(markdown[paper_id] or "", ai.evidence)
                impact = ReviewedImpact(
                    paper_id=paper_id, origin=ImpactOrigin.AI, run_id=run.id,
                    ai=ai, current=ai.model_copy(deep=True), evidence=evidence,
                )
                analysis.impacts.append(impact)
                events.append(Event(
                    at=at, actor=ActorKind.AI, action="created", impact_id=impact.id, run_id=run.id,
                    note="migrated from results",
                ))
                spans += len(evidence)
                anchored += sum(1 for s in evidence if s.start is not None)
        analysis.runs.append(run)
        await analysis.save()
        if events:
            await AuditEvent.insert_many([e.to_document(analysis.id) for e in events])
        analyses += 1
        impacts += len(events)
    if analyses:
        rate = f"{anchored / spans:.1%}" if spans else "n/a"
        logger.info(f"Migrated {analyses} analyses: {impacts} impacts, {anchored}/{spans} evidence spans anchored ({rate})")
