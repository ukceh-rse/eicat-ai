from datetime import datetime, timezone
from typing import Dict, List, Optional

from beanie import PydanticObjectId
from loguru import logger

from eicat_ai.anchoring import Locator
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
from eicat_ai.review import Event, as_found


async def _locator(locators: Dict[str, Locator], paper_id: str) -> Locator:
    if paper_id not in locators:
        doc = await PaperDoc.get(PydanticObjectId(paper_id))
        locators[paper_id] = Locator(doc.markdown if doc and doc.markdown else "")
    return locators[paper_id]


async def migrate_legacy_analyses() -> None:
    """Give analyses from before the review layer their impacts (design D9): one synthetic `legacy` run, and each
    result as an active, unverified AI impact with anchored evidence. Analyses with any run are skipped, so running
    this again changes nothing, and `results` is left as it is."""
    locators: Dict[str, Locator] = {}
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
            locator = await _locator(locators, paper_id)
            for ai in results:
                evidence = locator.anchor(ai.evidence)
                impact = ReviewedImpact(
                    paper_id=paper_id, origin=ImpactOrigin.AI, run_id=run.id,
                    ai=ai, current=as_found(ai, evidence), evidence=evidence,
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


REANCHOR = "reanchor_evidence_v1"  # a new id makes the next start anchor stored evidence again


async def reanchor_evidence() -> None:
    """Bring AI evidence stored before anchoring could always place it in line with new runs (design D3). Impacts
    whose spans a reviewer changed, as the audit trail records, are flagged `evidence_edited`; impacts and sightings
    holding an unanchored span are anchored again from the AI's evidence; and an AI impact whose evidence no reviewer
    changed takes its spans' texts (see `as_found`). Reviewers' spans are always anchored, so they are never
    re-anchored. It runs once: a record in `migrations` stops later starts from anchoring spans that never anchor
    (e.g. a paper without markdown) again."""
    migrations = Analysis.get_pymongo_collection().database["migrations"]
    if await migrations.find_one({"_id": REANCHOR}):
        return
    edited = {
        e.impact_id
        for e in await AuditEvent.find({"action": "updated", "changes.field": "evidence"}).to_list()
    }
    locators: Dict[str, Locator] = {}
    analyses = repaired = 0
    for analysis in await Analysis.find_all().to_list():
        changed = False
        for impact in analysis.impacts:
            if impact.id in edited and not impact.evidence_edited:
                impact.evidence_edited = True
                changed = True
            for holder in [impact, *impact.sightings]:
                if holder.ai is None or all(s.start is not None for s in holder.evidence):
                    continue
                locator = await _locator(locators, impact.paper_id)
                evidence = locator.anchor(holder.ai.evidence)
                if evidence != holder.evidence:
                    holder.evidence = evidence
                    changed = True
                    repaired += 1
            if impact.ai is not None and not impact.evidence_edited:
                found = as_found(impact.ai, impact.evidence).evidence
                if found != impact.current.evidence:
                    impact.current.evidence = found
                    changed = True
                    repaired += 1
        if changed:
            await analysis.save()
            analyses += 1
    if repaired:
        logger.info(f"Brought evidence of {repaired} impacts and sightings in {analyses} analyses in line with the paper")
    await migrations.insert_one({"_id": REANCHOR, "at": datetime.now(timezone.utc)})
