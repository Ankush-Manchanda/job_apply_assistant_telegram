from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from .database import Base


class Source(Base):
    __tablename__ = "sources"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    source_type = Column(String(50), nullable=False, default="rss")
    url = Column(String(1000), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    selector = Column(String(250), default="")
    title_selector = Column(String(250), default="")
    link_selector = Column(String(250), default="")
    location_hint = Column(String(200), default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class FilterProfile(Base):
    __tablename__ = "filter_profiles"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False, default="Default")
    title_keywords = Column(Text, default="Data Analyst\nBusiness Analyst\nBI Analyst\nReporting Analyst\nAnalyst Intern\nMIS Analyst")
    must_have_skills = Column(Text, default="Excel\nSQL\nPower BI\nPython")
    locations = Column(Text, default="Gurugram\nNoida\nDelhi NCR\nRemote")
    exclude_keywords = Column(Text, default="unpaid\nsales\ncommission\nfield work\n3+ years\n4+ years\n5+ years")
    min_score = Column(Integer, default=45)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Resume(Base):
    __tablename__ = "resumes"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    filename = Column(String(255), nullable=False)
    target_role = Column(String(150), default="General")
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(500), unique=True, index=True)
    platform = Column(String(100), default="Unknown")
    title = Column(String(300), nullable=False)
    company = Column(String(300), default="Unknown")
    location = Column(String(200), default="")
    url = Column(String(1000), nullable=False)
    description = Column(Text, default="")
    posted_raw = Column(String(100), default="")
    score = Column(Integer, default=0)
    matched = Column(Boolean, default=False)
    notified = Column(Boolean, default=False)
    status = Column(String(50), default="new")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class Application(Base):
    __tablename__ = "applications"
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, nullable=False)
    resume_id = Column(Integer, nullable=True)
    status = Column(String(50), default="saved")
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
