from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Iterable
from urllib.parse import urljoin

import feedparser
import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from .config import settings
from .models import Application, FilterProfile, Job, Resume, Source

TIMEOUT = 20


def normalize_lines(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def active_filter(db: Session) -> FilterProfile:
    profile = db.query(FilterProfile).filter(FilterProfile.enabled.is_(True)).order_by(FilterProfile.id.asc()).first()
    if not profile:
        profile = FilterProfile(min_score=settings.default_min_score)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def score_job(job_title: str, location: str, description: str, profile: FilterProfile) -> tuple[int, bool, list[str]]:
    text = f"{job_title}\n{location}\n{description}".lower()
    score = 0
    reasons: list[str] = []

    for keyword in normalize_lines(profile.title_keywords):
        if keyword.lower() in text:
            score += 30
            reasons.append(f"title:{keyword}")
            break

    location_hits = 0
    for loc in normalize_lines(profile.locations):
        if loc.lower() in text:
            location_hits += 1
    if location_hits:
        score += min(20, location_hits * 10)
        reasons.append("location")

    skill_hits = 0
    for skill in normalize_lines(profile.must_have_skills):
        if skill.lower() in text:
            skill_hits += 1
    if skill_hits:
        score += min(30, skill_hits * 8)
        reasons.append(f"skills:{skill_hits}")

    for bad in normalize_lines(profile.exclude_keywords):
        if bad.lower() in text:
            score -= 25
            reasons.append(f"exclude:{bad}")

    if "intern" in text or "fresher" in text or "entry level" in text or "0-1" in text:
        score += 10
        reasons.append("early-career")

    if "easy apply" in text or "quick apply" in text or "apply now" in text:
        score += 5
        reasons.append("easy-apply-ish")

    matched = score >= profile.min_score
    return max(score, 0), matched, reasons


def telegram_enabled() -> bool:
    return bool(settings.telegram_bot_token and settings.telegram_chat_id)


def send_telegram_message(message: str) -> tuple[bool, str]:
    if not telegram_enabled():
        return False, "Telegram is not configured"

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": message,
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=TIMEOUT)
        if resp.ok:
            return True, "sent"
        return False, f"Telegram error: {resp.text[:200]}"
    except Exception as exc:  # pragma: no cover
        return False, str(exc)


def format_job_message(job: Job) -> str:
    dashboard_url = f"{settings.app_base_url.rstrip('/')}/jobs/{job.id}"
    return (
        f"🚀 New matched job\n\n"
        f"Role: {job.title}\n"
        f"Company: {job.company}\n"
        f"Location: {job.location or 'Not specified'}\n"
        f"Score: {job.score}\n"
        f"Platform: {job.platform}\n\n"
        f"Review: {dashboard_url}\n"
        f"Apply link: {job.url}"
    )


def safe_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()


def hash_external_id(*parts: str) -> str:
    joined = "|".join(part.strip() for part in parts if part)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def fetch_rss(source: Source) -> list[dict]:
    parsed = feedparser.parse(source.url)
    items: list[dict] = []
    for entry in parsed.entries:
        title = safe_text(getattr(entry, "title", "Untitled"))
        link = safe_text(getattr(entry, "link", ""))
        summary = safe_text(getattr(entry, "summary", ""))
        company = safe_text(getattr(entry, "author", "Unknown"))
        if not company and hasattr(entry, "tags"):
            company = ", ".join(tag.term for tag in entry.tags[:1])
        location = safe_text(getattr(entry, "location", "")) or source.location_hint
        posted_raw = safe_text(getattr(entry, "published", "")) or safe_text(getattr(entry, "updated", ""))
        items.append(
            {
                "external_id": hash_external_id(source.url, link or title, posted_raw),
                "platform": source.name,
                "title": title,
                "company": company or "Unknown",
                "location": location,
                "url": link,
                "description": summary,
                "posted_raw": posted_raw,
            }
        )
    return items


def fetch_html(source: Source) -> list[dict]:
    resp = requests.get(source.url, timeout=TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    selector = source.selector or "a"
    nodes = soup.select(selector)
    items: list[dict] = []
    for node in nodes[:100]:
        title = safe_text(node.select_one(source.title_selector).get_text(" ", strip=True) if source.title_selector and node.select_one(source.title_selector) else node.get_text(" ", strip=True))
        href_node = node.select_one(source.link_selector) if source.link_selector else node
        href = href_node.get("href", "") if href_node else ""
        link = urljoin(source.url, href) if href else source.url
        if not title or not link:
            continue
        items.append(
            {
                "external_id": hash_external_id(source.url, link, title),
                "platform": source.name,
                "title": title,
                "company": source.name,
                "location": source.location_hint,
                "url": link,
                "description": title,
                "posted_raw": "",
            }
        )
    return items


def fetch_from_source(source: Source) -> list[dict]:
    if source.source_type == "rss":
        return fetch_rss(source)
    if source.source_type == "html":
        return fetch_html(source)
    return []


def upsert_jobs(db: Session, jobs_data: Iterable[dict]) -> list[Job]:
    profile = active_filter(db)
    new_jobs: list[Job] = []

    for item in jobs_data:
        if not item.get("url"):
            continue
        existing = db.query(Job).filter(Job.external_id == item["external_id"]).first()
        if existing:
            continue

        score, matched, reasons = score_job(
            item.get("title", ""),
            item.get("location", ""),
            item.get("description", ""),
            profile,
        )
        job = Job(
            external_id=item["external_id"],
            platform=item.get("platform", "Unknown"),
            title=item.get("title", "Untitled"),
            company=item.get("company", "Unknown"),
            location=item.get("location", ""),
            url=item.get("url", ""),
            description=f"{item.get('description', '')}\n\nReasons: {', '.join(reasons)}",
            posted_raw=item.get("posted_raw", ""),
            score=score,
            matched=matched,
            notified=False,
            status="new",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(job)
        db.flush()
        new_jobs.append(job)

    db.commit()
    return new_jobs


def poll_sources(db: Session) -> dict:
    sources = db.query(Source).filter(Source.enabled.is_(True)).all()
    all_new_jobs: list[Job] = []
    errors: list[str] = []

    for source in sources:
        try:
            rows = fetch_from_source(source)
            new_jobs = upsert_jobs(db, rows)
            all_new_jobs.extend(new_jobs)
        except Exception as exc:
            errors.append(f"{source.name}: {exc}")

    matched_jobs = [job for job in all_new_jobs if job.matched and not job.notified]
    telegram_sent = 0
    telegram_errors: list[str] = []

    for job in matched_jobs:
        ok, msg = send_telegram_message(format_job_message(job))
        if ok:
            job.notified = True
            job.updated_at = datetime.utcnow()
            telegram_sent += 1
        else:
            telegram_errors.append(f"{job.title}: {msg}")
    db.commit()

    return {
        "sources_checked": len(sources),
        "new_jobs": len(all_new_jobs),
        "matched_jobs": len(matched_jobs),
        "telegram_sent": telegram_sent,
        "errors": errors + telegram_errors,
    }


def seed_defaults(db: Session) -> None:
    if not db.query(FilterProfile).count():
        db.add(FilterProfile(min_score=settings.default_min_score))

    if not db.query(Source).count():
        db.add_all(
            [
                Source(name="RemoteOK", source_type="rss", url="https://remoteok.com/remote-data-jobs.rss", enabled=True, location_hint="Remote"),
                Source(name="We Work Remotely", source_type="rss", url="https://weworkremotely.com/categories/remote-data-jobs.rss", enabled=True, location_hint="Remote"),
            ]
        )
    db.commit()


def save_application(db: Session, job_id: int, resume_id: int | None, notes: str = "") -> Application:
    record = Application(job_id=job_id, resume_id=resume_id, notes=notes, status="saved")
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def find_resume(db: Session, resume_id: int | None) -> Resume | None:
    if resume_id is None:
        return None
    return db.query(Resume).filter(Resume.id == resume_id).first()
