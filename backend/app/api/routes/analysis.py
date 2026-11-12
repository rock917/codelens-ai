from app.auth import AuthUser, get_current_user, owned_repository
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database.base import get_db
from app.models.repository import Repository, AnalysisIssue, File, RepositoryJob
from app.services.analyzer.analysis_engine import run_analysis_job, calculate_health_score
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

router = APIRouter(prefix="/analysis", tags=["analysis"])

@router.post("/{repo_id}")
async def trigger_analysis(
    repo_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    await owned_repository(db, repo_id, user.id)
    result = await db.execute(
        select(Repository).where(Repository.id == repo_id).with_for_update()
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(404, "Repository not found")
    if repo.status != "READY":
        raise HTTPException(400, f"Repository not ready. Status: {repo.status}")

    active = await db.scalar(select(RepositoryJob.id).where(
        RepositoryJob.repository_id == repo_id, RepositoryJob.job_type == 'ANALYSIS',
        RepositoryJob.status.in_(['PENDING', 'RUNNING']),
    ).limit(1))
    if active:
        return {"message": "Analysis already running", "repository_id": repo_id, "job_id": active}
    job = RepositoryJob(id=str(uuid.uuid4()), repository_id=repo_id,
                        job_type='ANALYSIS', status='RUNNING',
                        created_at=datetime.now(timezone.utc).replace(tzinfo=None))
    db.add(job)
    await db.commit()
    background_tasks.add_task(run_analysis_job, repo_id, job.id)
    return {"message": "Analysis started", "repository_id": repo_id, "job_id": job.id}

@router.get("/{repo_id}/issues")
async def get_issues(
    repo_id: str,
    severity: Optional[str] = None,
    issue_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    await owned_repository(db, repo_id, user.id)
    query = (
        select(AnalysisIssue, File.path)
        .join(File, AnalysisIssue.file_id == File.id)
        .where(AnalysisIssue.repository_id == repo_id)
    )

    if severity:
        query = query.where(AnalysisIssue.severity == severity.upper())
    if issue_type:
        query = query.where(AnalysisIssue.issue_type == issue_type.upper())

    query = query.order_by(
        AnalysisIssue.severity.desc(),
        File.path
    )

    result = await db.execute(query)
    rows = result.all()

    issues = []
    for issue, file_path in rows:
        issues.append({
            "id": issue.id,
            "file_path": file_path,
            "issue_type": issue.issue_type,
            "severity": issue.severity,
            "message": issue.message,
            "line": issue.line,
            "suggestion": issue.suggestion
        })

    return issues

@router.get("/{repo_id}/summary")
async def get_analysis_summary(
    repo_id: str,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    await owned_repository(db, repo_id, user.id)
    result = await db.execute(
        select(Repository).where(Repository.id == repo_id)
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(404, "Repository not found")

    # Count by severity
    severities = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    counts = {}
    for severity in severities:
        count_result = await db.execute(
            select(func.count(AnalysisIssue.id))
            .where(
                AnalysisIssue.repository_id == repo_id,
                AnalysisIssue.severity == severity
            )
        )
        counts[severity] = count_result.scalar() or 0

    # Count by type
    type_result = await db.execute(
        select(
            AnalysisIssue.issue_type,
            func.count(AnalysisIssue.id)
        )
        .where(AnalysisIssue.repository_id == repo_id)
        .group_by(AnalysisIssue.issue_type)
        .order_by(func.count(AnalysisIssue.id).desc())
    )
    by_type = {row[0]: row[1] for row in type_result.all()}

    total = sum(counts.values())
    jobs = (await db.scalars(select(RepositoryJob).where(
        RepositoryJob.repository_id == repo_id, RepositoryJob.job_type == 'ANALYSIS',
    ).order_by(RepositoryJob.created_at.desc(), RepositoryJob.id.desc()))).all()
    # Current job and last successful result are separate: a failed rescan must
    # not turn old findings into a claim that the latest scan succeeded.
    active = next((job for job in jobs if job.status in ('PENDING', 'RUNNING')), None)
    latest = active or (jobs[0] if jobs else None)
    completed = next((job for job in jobs if job.status == 'COMPLETED'), None)
    coverage = json.loads(completed.message) if completed and completed.message else None
    status = latest.status if latest else ('LEGACY' if total else 'NOT_RUN')
    score = None
    if coverage and coverage['scanned_files'] > 0:
        score = calculate_health_score(counts, coverage['scanned_loc'])

    return {
        "repository_id": repo_id,
        "total_issues": total,
        "by_severity": counts,
        "by_type": by_type,
        "health_score": score,
        "analysis_status": status,
        "coverage": coverage,
        "completed_at": completed.updated_at if completed else None,
        "error_message": latest.error_message if latest else None,
        "score_version": "density-v1",
    }
