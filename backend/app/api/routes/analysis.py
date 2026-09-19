from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database.base import get_db
from app.models.repository import Repository, AnalysisIssue, File
from app.services.analyzer.analysis_engine import run_analysis
from typing import Optional

router = APIRouter(prefix="/analysis", tags=["analysis"])

@router.post("/{repo_id}")
async def trigger_analysis(
    repo_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Repository).where(Repository.id == repo_id)
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(404, "Repository not found")
    if repo.status != "READY":
        raise HTTPException(400, f"Repository not ready. Status: {repo.status}")

    background_tasks.add_task(run_analysis, db, repo_id)

    return {"message": "Analysis started", "repository_id": repo_id}

@router.get("/{repo_id}/issues")
async def get_issues(
    repo_id: str,
    severity: Optional[str] = None,
    issue_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
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
    db: AsyncSession = Depends(get_db)
):
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

    return {
        "repository_id": repo_id,
        "total_issues": total,
        "by_severity": counts,
        "by_type": by_type,
        "health_score": _calculate_health_score(counts)
    }

def _calculate_health_score(counts: dict) -> int:
    score = 100
    score -= counts.get("CRITICAL", 0) * 15
    score -= counts.get("HIGH", 0) * 8
    score -= counts.get("MEDIUM", 0) * 3
    score -= counts.get("LOW", 0) * 1
    return max(0, score)