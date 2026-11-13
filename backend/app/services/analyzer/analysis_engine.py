import asyncio
import json
import logging
import uuid
from pathlib import Path

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.base import AsyncSessionLocal
from app.models.repository import File, AnalysisIssue, RepositoryJob
from app.services.analyzer.complexity_analyzer import analyze_complexity
from app.services.analyzer.security_analyzer import analyze_security
from app.services.analyzer.smell_analyzer import analyze_smells
from app.config.settings import settings

SUPPORTED_LANGUAGES = ("python", "javascript", "typescript", "notebook", "json", "java", "go", "cpp")
logger = logging.getLogger(__name__)


def calculate_health_score(counts: dict, scanned_loc: int) -> int:
    """Heuristic: severity-weighted findings per 1,000 scanned lines.

    The 1,000-line floor avoids exaggerated penalties on tiny repositories.
    A density of 20 gives 50/100; critical/high findings cap the rating.
    This is a prioritization signal, not a security certification.
    """
    weighted = sum(counts.get(level, 0) * weight for level, weight in
                   (("CRITICAL", 15), ("HIGH", 8), ("MEDIUM", 3), ("LOW", 1)))
    density = weighted * 1000 / max(1000, scanned_loc)
    score = round(100 / (1 + density / 20))
    if counts.get("CRITICAL", 0):
        score = min(score, 49)
    elif counts.get("HIGH", 0):
        score = min(score, 79)
    return score


def source_snapshot(repo_id, files):
    root = (Path(settings.UPLOAD_DIR) / repo_id).resolve()
    for file_id, path, language in files:
        if language not in SUPPORTED_LANGUAGES:
            continue
        relative = path.replace('\\', '/')
        candidates = [root / relative]
        if '/' in relative:
            candidates.append(root / relative.split('/', 1)[1])
        candidate = next((p.resolve() for p in candidates
                          if p.resolve().is_relative_to(root) and p.is_file()), None)
        if candidate is None:
            raise ValueError('Source files are missing. Import this repository again before scanning.')
        yield file_id, path, language, candidate.read_text(encoding='utf-8', errors='replace')


def source_key(file_id, path, language, content):
    from app.services.result_cache import fingerprint
    return file_id, path, language, fingerprint(content)


def snapshot_key(sources, files):
    from app.services import result_cache as cache
    version = cache.code_version('analyzer/analysis_engine.py', 'analyzer/complexity_analyzer.py',
                                 'analyzer/security_analyzer.py', 'analyzer/smell_analyzer.py', 'documents.py',
                                 'analyzer/compiled_analyzer.py', 'parser/compiled_parser.py', '../../requirements.txt')
    return cache.fingerprint(version, sorted(sources), sorted([tuple(f) for f in files]))


def analysis_key(repo_id, files):
    return snapshot_key([source_key(*source) for source in source_snapshot(repo_id, files)], files)


def _scan_files(repo_id: str, files: list) -> tuple[list, dict]:
    sources = source_snapshot(repo_id, files)
    source_keys = []
    findings = []
    scanned_files = scanned_loc = 0
    notebook_scanned = notebook_skipped = json_validated = 0
    compiled_scanned = 0
    exclusions = []
    for file_id, path, language, content in sources:
        source_keys.append(source_key(file_id, path, language, content))
        if language in ('java', 'go', 'cpp'):
            from app.services.analyzer.compiled_analyzer import analyze_compiled
            checks, exclusion = analyze_compiled(path, content, language)
            if exclusion:
                exclusions.append({'path': path, 'reason': exclusion})
            else:
                compiled_scanned += 1
                scanned_files += 1
                scanned_loc += len(content.splitlines())
                for issue in checks:
                    findings.append(dict(id=str(uuid.uuid4()), repository_id=repo_id, file_id=file_id,
                        issue_type=issue.issue_type, severity=issue.severity, message=issue.message,
                        line=issue.line, suggestion=issue.suggestion))
            continue
        units = [(content, language, 0, '')]
        if language in ('json', 'notebook'):
            from app.services.documents import document_view
            view = document_view(content, language)
            units = []
            if language == 'json':
                json_validated += int(view['valid'])
                exclusions.append({'path': path, 'reason': 'JSON validated; no code health score' if view['valid'] else '; '.join(view['warnings'])})
            elif not view['valid']:
                exclusions.append({'path': path, 'reason': '; '.join(view['warnings'])})
            else:
                for cell in view['cells']:
                    if cell['cell_type'] != 'code' or not cell['source'].strip():
                        continue
                    if cell['analysis_supported']:
                        notebook_scanned += 1
                        units.append((cell['source'], 'python', cell['start_line'] - 1, f"Cell {cell['number']}: "))
                    else:
                        notebook_skipped += 1
                        exclusions.append({'path': path, 'reason': f"Cell {cell['number']}: {cell['reason']}"})
        if units:
            scanned_files += 1
        for source, unit_language, offset, label in units:
            scanned_loc += len(source.splitlines())
            for analyzer in (analyze_complexity, analyze_security, analyze_smells):
                for issue in analyzer(path, source, unit_language):
                    findings.append(dict(
                        id=str(uuid.uuid4()), repository_id=repo_id, file_id=file_id,
                        issue_type=issue.issue_type, severity=issue.severity,
                        message=label + issue.message, line=(issue.line + offset) if issue.line else None, suggestion=issue.suggestion,
                    ))
    return findings, {"scanned_files": scanned_files, "scanned_loc": scanned_loc,
                      "unsupported_files": len(files) - scanned_files,
                      "notebook_cells_scanned": notebook_scanned, "notebook_cells_skipped": notebook_skipped,
                      "json_files_validated": json_validated, "exclusions": exclusions,
                      "compiled_files_scanned": compiled_scanned,
                      "cache_key": snapshot_key(source_keys, files)}


async def run_analysis(db: AsyncSession, repo_id: str, job: RepositoryJob) -> dict:
    rows = (await db.execute(select(File.id, File.path, File.language)
                            .where(File.repository_id == repo_id))).all()
    # File I/O and AST work must not block authentication, polling or health checks.
    findings, coverage = await asyncio.to_thread(_scan_files, repo_id, rows)
    # Replace results and mark completion in one transaction, never publish half a scan.
    await db.execute(delete(AnalysisIssue).where(AnalysisIssue.repository_id == repo_id))
    db.add_all([AnalysisIssue(**finding) for finding in findings])
    job.status = 'COMPLETED'
    job.progress = 100
    job.message = json.dumps(coverage)
    job.error_message = None
    await db.commit()
    return coverage


async def run_analysis_job(repo_id: str, job_id: str):
    # Background work owns its session; the request session may already be closed.
    async with AsyncSessionLocal() as db:
        job = await db.get(RepositoryJob, job_id)
        if job is None:
            return
        try:
            await run_analysis(db, repo_id, job)
        except Exception:
            await db.rollback()
            logger.exception("Analysis failed for repository %s", repo_id)
            job = await db.get(RepositoryJob, job_id)
            if job is not None:
                job.status = 'FAILED'
                job.error_message = 'Scan failed. Check that source files are available or import the repository again. Previous results were retained.'
                await db.commit()
