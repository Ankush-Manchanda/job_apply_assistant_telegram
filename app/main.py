from __future__ import annotations

import shutil
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc
from sqlalchemy.orm import Session

from .config import RESUME_DIR, settings
from .database import Base, SessionLocal, engine, get_db
from .models import Application, FilterProfile, Job, Resume, Source
from .schemas import SourceCreate
from .services import (
    active_filter,
    find_resume,
    poll_sources,
    save_application,
    seed_defaults,
    send_telegram_message,
)

scheduler = BackgroundScheduler(timezone="Asia/Kolkata")


def scheduled_poll() -> None:
    db = SessionLocal()
    try:
        poll_sources(db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_defaults(db)
    finally:
        db.close()

    if not scheduler.running:
        scheduler.add_job(
            scheduled_poll,
            "interval",
            minutes=max(5, settings.job_check_interval_minutes),
            id="job-poll",
            replace_existing=True,
        )
        scheduler.start()
    yield
    if scheduler.running:
        scheduler.shutdown(wait=False)


app = FastAPI(title=settings.app_name, lifespan=lifespan)
@app.get("/health")
def health():
    return {"status": "healthy"}
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    jobs = db.query(Job).order_by(desc(Job.created_at)).limit(50).all()
    resumes = db.query(Resume).order_by(desc(Resume.created_at)).all()
    sources = db.query(Source).order_by(Source.id.asc()).all()
    profile = active_filter(db)
    stats = {
        "total_jobs": db.query(Job).count(),
        "matched_jobs": db.query(Job).filter(Job.matched.is_(True)).count(),
        "applied_jobs": db.query(Job).filter(Job.status == "applied").count(),
        "new_jobs": db.query(Job).filter(Job.status == "new").count(),
    }
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "jobs": jobs,
            "resumes": resumes,
            "sources": sources,
            "profile": profile,
            "stats": stats,
            "settings": settings,
        },
    )


@app.post("/sources")
def add_source(
    name: str = Form(...),
    source_type: str = Form(...),
    url: str = Form(...),
    enabled: bool = Form(True),
    selector: str = Form(""),
    title_selector: str = Form(""),
    link_selector: str = Form(""),
    location_hint: str = Form(""),
    db: Session = Depends(get_db),
):
    source = Source(
        name=name,
        source_type=source_type,
        url=url,
        enabled=enabled,
        selector=selector,
        title_selector=title_selector,
        link_selector=link_selector,
        location_hint=location_hint,
    )
    db.add(source)
    db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.post("/sources/{source_id}/toggle")
def toggle_source(source_id: int, db: Session = Depends(get_db)):
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    source.enabled = not source.enabled
    db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.post("/profile")
def update_profile(
    title_keywords: str = Form(...),
    must_have_skills: str = Form(...),
    locations: str = Form(...),
    exclude_keywords: str = Form(...),
    min_score: int = Form(...),
    db: Session = Depends(get_db),
):
    profile = active_filter(db)
    profile.title_keywords = title_keywords
    profile.must_have_skills = must_have_skills
    profile.locations = locations
    profile.exclude_keywords = exclude_keywords
    profile.min_score = min_score
    db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.post("/resumes")
def upload_resume(
    name: str = Form(...),
    target_role: str = Form("General"),
    notes: str = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    filename = f"{int(datetime.utcnow().timestamp())}_{file.filename}"
    destination = RESUME_DIR / filename
    with destination.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    resume = Resume(name=name, filename=filename, target_role=target_role, notes=notes)
    db.add(resume)
    db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail(job_id: int, request: Request, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    resumes = db.query(Resume).order_by(desc(Resume.created_at)).all()
    applications = db.query(Application).filter(Application.job_id == job.id).order_by(desc(Application.created_at)).all()
    return templates.TemplateResponse(
        "job_detail.html",
        {"request": request, "job": job, "resumes": resumes, "applications": applications},
    )


@app.post("/jobs/{job_id}/status")
def update_job_status(job_id: int, status: str = Form(...), db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.status = status
    job.updated_at = datetime.utcnow()
    db.commit()
    return RedirectResponse(url=f"/jobs/{job_id}", status_code=303)


@app.post("/jobs/{job_id}/save-application")
def save_job_application(
    job_id: int,
    resume_id: int | None = Form(None),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    save_application(db, job_id=job.id, resume_id=resume_id, notes=notes)
    return RedirectResponse(url=f"/jobs/{job.id}", status_code=303)


@app.get("/resumes/{resume_id}/download")
def download_resume(resume_id: int, db: Session = Depends(get_db)):
    from fastapi.responses import FileResponse

    resume = find_resume(db, resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    path = RESUME_DIR / resume.filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File missing on server")
    return FileResponse(path, filename=resume.filename)


@app.post("/run-check")
def run_manual_check(db: Session = Depends(get_db)):
    poll_sources(db)
    return RedirectResponse(url="/", status_code=303)


@app.post("/test-telegram")
def test_telegram():
    ok, msg = send_telegram_message(
        f"✅ Test message from {settings.app_name}\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return RedirectResponse(url="/", status_code=303)
