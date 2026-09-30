from typing import Optional
from pydantic import BaseModel, Field, EmailStr


class WorkExperience(BaseModel):
    company: str
    role: str
    start_date: str
    end_date: str
    duration_months: Optional[int] = None
    description: list[str] = Field(default_factory=list)


class Education(BaseModel):
    degree: str
    institution: str
    start_year: int
    end_year: int
    grade: Optional[str] = None


class Certification(BaseModel):
    name: str
    issuer: str
    year: Optional[int] = None


class Project(BaseModel):
    title: str
    description: str
    tech_used: list[str] = Field(default_factory=list)


class ResumeSchema(BaseModel):
    full_name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    summary: Optional[str] = None
    technical_skills: list[str] = Field(default_factory=list)
    soft_skills: list[str] = Field(default_factory=list)
    work_experience: list[WorkExperience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    total_experience_years: Optional[float] = None
    parsing_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    missing_fields: list[str] = Field(default_factory=list)
