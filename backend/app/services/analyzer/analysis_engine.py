import uuid
import os
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.models.repository import Repository, File, AnalysisIssue
from app.services.analyzer.complexity_analyzer import analyze_complexity
from app.services.analyzer.security_analyzer import analyze_security
from app.services.analyzer.smell_analyzer import analyze_smells
from app.config.settings import settings

def generate_id() -> str:
    return str(uuid.uuid4())

def read_file_content(file_path: str) -> str:
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception:
        return ""

async def run_analysis(
    db: AsyncSession,
    repo_id: str
) -> dict:
    print(f"⏳ Running analysis for repo {repo_id}...")

    # Get all files
    result = await db.execute(
        select(File).where(File.repository_id == repo_id)
    )
    files = result.scalars().all()

    # Delete existing issues
    await db.execute(
        delete(AnalysisIssue).where(
            AnalysisIssue.repository_id == repo_id
        )
    )
    await db.commit()

    total_issues = 0
    severity_counts = {
        "CRITICAL": 0, "HIGH": 0,
        "MEDIUM": 0, "LOW": 0
    }

    repo_dir = os.path.join(settings.UPLOAD_DIR, repo_id)

    for file in files:
        if file.language not in ("python", "javascript", "typescript"):
            continue

        # Find actual file path
        file_full_path = os.path.join(repo_dir, file.path)
        if not os.path.exists(file_full_path):
            # Try without first directory component
            parts = file.path.split('/', 1)
            if len(parts) > 1:
                file_full_path = os.path.join(repo_dir, parts[1])

        if not os.path.exists(file_full_path):
            continue

        content = read_file_content(file_full_path)
        if not content:
            continue

        all_issues = []

        # Run all analyzers
        complexity_issues = analyze_complexity(
            file.path, content, file.language
        )
        security_issues = analyze_security(
            file.path, content, file.language
        )
        smell_issues = analyze_smells(
            file.path, content, file.language
        )

        # Convert to DB records
        for issue in complexity_issues:
            all_issues.append(AnalysisIssue(
                id=generate_id(),
                repository_id=repo_id,
                file_id=file.id,
                issue_type=issue.issue_type,
                severity=issue.severity,
                message=issue.message,
                line=issue.line,
                suggestion=issue.suggestion
            ))

        for issue in security_issues:
            all_issues.append(AnalysisIssue(
                id=generate_id(),
                repository_id=repo_id,
                file_id=file.id,
                issue_type=issue.issue_type,
                severity=issue.severity,
                message=issue.message,
                line=issue.line,
                suggestion=issue.suggestion
            ))

        for issue in smell_issues:
            all_issues.append(AnalysisIssue(
                id=generate_id(),
                repository_id=repo_id,
                file_id=file.id,
                issue_type=issue.issue_type,
                severity=issue.severity,
                message=issue.message,
                line=issue.line,
                suggestion=issue.suggestion
            ))

        for issue in all_issues:
            db.add(issue)
            severity_counts[issue.severity] = \
                severity_counts.get(issue.severity, 0) + 1
            total_issues += 1

    await db.commit()

    print(f"✅ Analysis complete! Found {total_issues} issues")
    return {
        "total_issues": total_issues,
        "severity_counts": severity_counts
    }