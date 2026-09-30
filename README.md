# Resume Structured Output Agent

An AI agent that extracts unstructured resume documents (PDF & DOCX) into a strictly validated, schema-compliant JSON format using **Google Gemini API Native Structured Outputs (`response_schema`)** and **Pydantic v2**, presented through an interactive **Streamlit** web application.

---

## 🌟 Key Features

- **Multi-Format Extraction**: Ingests both `.pdf` (via `pdfplumber`) and `.docx` (via `python-docx`) resumes cleanly, including tables and formatting.
- **Strict Schema Enforcement**: Guarantees output structure via Google Gemini's native structured outputs (`response_schema=ResumeSchema`) — zero hallucinated schemas or broken JSON.
- **Automatic Duration & Experience Math**: Intelligently parses start/end dates across formats (e.g. `Jan 2021 - Present`, `2018 - 2022`), computes duration in months for each job, and sums total years of experience.
- **Self-Reported Confidence & Missing Field Auditing**: LLM reports a `parsing_confidence` score (0.0 to 1.0) and lists `missing_fields` (e.g., missing phone, certifications, github), supplemented with programmatic validation.
- **Robust Error Handling & Validation Recovery**: Automatically catches Pydantic validation errors and triggers an immediate self-correction retry with Gemini. Gracefully identifies scanned/image-only PDFs or empty files and alerts the user.
- **Modern Streamlit Dashboard**: Clean, responsive interface with candidate overview metrics, timeline cards for work history, skills badges, raw JSON inspector, and 1-click JSON export.

---

## 🛠️ Tech Stack

- **AI Engine**: Google Gemini API (`gemini-3.6-flash`) via `google-genai` Python SDK
- **Data Validation & Contract**: Pydantic v2 & `email-validator`
- **Document Processing**: `pdfplumber` (PDFs) and `python-docx` (Word documents)
- **Web UI**: Streamlit
- **Date Arithmetic**: `python-dateutil`
- **Sample Generation**: `reportlab`

---

## 📋 Data Contract (`schema.py`)

The extraction strictly conforms to the following Pydantic models:

```python
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
```

---

## 🚀 Quick Start

### 1. Clone & Navigate to Project
```bash
cd "d:\Resume Screening"
```

### 2. Set Up Virtual Environment & Dependencies
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure Google Gemini API Key
Create a `.env` file from the provided `.env.example`:
```bash
copy .env.example .env
```
Edit `.env` and set your key:
```env
GEMINI_API_KEY=AIzaSy...
```
The app reads the key only on the server. It is intentionally not entered through the browser UI, so visitors cannot inspect it from the page.

### 4. Generate Test Sample Resumes
Run the generator script to create test resumes (PDF, DOCX, and scanned dummy):
```powershell
.venv\Scripts\python generate_samples.py
```

### 5. Launch the Streamlit App
```powershell
.venv\Scripts\streamlit run app.py
```

Open your browser to `http://localhost:8501`.

---

## 🧪 Testing

Run the automated test pipeline:
```powershell
.venv\Scripts\python test_pipeline.py
```
This tests:
- Schema instantiation and type validation
- Date range parser and experience duration math
- Missing field detection logic
- PDF text extraction via `pdfplumber`
- DOCX text extraction via `python-docx`
- Scanned/empty PDF error detection
- End-to-end Gemini extraction (if `GEMINI_API_KEY` is provided)

---

## 📄 Example JSON Outputs

### Example 1: Senior Full-Stack Engineer (`sample_resume_complete.pdf`)

```json
{
  "full_name": "Alex Mercer",
  "email": "alex.mercer@example.com",
  "phone": "+1 (555) 234-5678",
  "location": "San Francisco, CA",
  "linkedin_url": "https://linkedin.com/in/alex-mercer",
  "github_url": "https://github.com/alexmercer-dev",
  "summary": "Passionate Senior Full-Stack Software Engineer with over 6 years of experience architecting and building scalable cloud-native web applications, distributed systems, and modern microservices.",
  "technical_skills": [
    "Python",
    "FastAPI",
    "Django",
    "TypeScript",
    "React",
    "Next.js",
    "Node.js",
    "PostgreSQL",
    "Redis",
    "Docker",
    "Kubernetes",
    "AWS",
    "GraphQL",
    "Git",
    "CI/CD"
  ],
  "soft_skills": [
    "Agile Leadership",
    "System Design Mentorship",
    "Technical Writing",
    "Problem Solving",
    "Cross-Functional Communication"
  ],
  "work_experience": [
    {
      "company": "CloudScale Technologies",
      "role": "Staff Software Engineer",
      "start_date": "Jan 2022",
      "end_date": "Present",
      "duration_months": 33,
      "description": [
        "Architected high-throughput microservices using FastAPI and Redis, decreasing API response latency by 45% for 2M+ daily active users.",
        "Led migration of legacy monolith into containerized Kubernetes services on AWS EKS, improving deployment cycle time from bi-weekly to daily.",
        "Mentored an engineering squad of 8 frontend and backend engineers, conducting code reviews and system design workshops."
      ]
    },
    {
      "company": "DataPulse Analytics",
      "role": "Senior Backend Engineer",
      "start_date": "Jun 2019",
      "end_date": "Dec 2021",
      "duration_months": 31,
      "description": [
        "Designed real-time event streaming pipeline processing 10,000 events/sec using Apache Kafka and Python.",
        "Re-engineered database indexing and query patterns on PostgreSQL, reducing slow query counts by 60%."
      ]
    }
  ],
  "education": [
    {
      "degree": "B.S. in Computer Science",
      "institution": "University of California, Berkeley",
      "start_year": 2013,
      "end_year": 2017,
      "grade": "GPA 3.85 / 4.0"
    }
  ],
  "certifications": [
    {
      "name": "AWS Certified Solutions Architect - Associate",
      "issuer": "Amazon Web Services",
      "year": 2022
    },
    {
      "name": "Certified Kubernetes Administrator - CKA",
      "issuer": "Cloud Native Computing Foundation",
      "year": 2023
    }
  ],
  "projects": [
    {
      "title": "FlowTrack - Workflow Automation Engine",
      "description": "An open-source distributed task runner built with Python, Celery, and WebSockets enabling real-time DAG execution visualization.",
      "tech_used": ["Python", "Celery", "Redis", "React", "WebSockets"]
    }
  ],
  "total_experience_years": 7.3,
  "parsing_confidence": 0.98,
  "missing_fields": []
}
```

### Example 2: Incomplete Junior Candidate (`sample_resume_junior.docx`)

```json
{
  "full_name": "Taylor Brooks",
  "email": "taylor.brooks@example.com",
  "phone": null,
  "location": "Seattle, WA",
  "linkedin_url": null,
  "github_url": "https://github.com/taylorbrooks-ds",
  "summary": "Motivated Junior Data Scientist with strong foundational skills in Python, machine learning, and statistical analysis.",
  "technical_skills": ["Python", "Pandas", "Scikit-Learn", "SQL", "Matplotlib", "Seaborn", "Git"],
  "soft_skills": ["Teamwork", "Critical Thinking", "Analytical Mindset"],
  "work_experience": [
    {
      "company": "Insights Corp",
      "role": "Data Science Intern",
      "start_date": "Jun 2023",
      "end_date": "Sep 2023",
      "duration_months": 4,
      "description": [
        "Built customer churn classification model achieving 82% ROC-AUC using Random Forests.",
        "Cleaned and preprocessed customer telemetry dataset containing 500k+ rows with Pandas."
      ]
    }
  ],
  "education": [
    {
      "degree": "B.S. in Statistics",
      "institution": "University of Washington",
      "start_year": 2020,
      "end_year": 2024,
      "grade": null
    }
  ],
  "certifications": [],
  "projects": [
    {
      "title": "Housing Price Predictor",
      "description": "Regression modeling on King County housing data using XGBoost and Streamlit.",
      "tech_used": ["Python", "XGBoost", "Streamlit"]
    }
  ],
  "total_experience_years": 0.3,
  "parsing_confidence": 0.85,
  "missing_fields": [
    "certifications",
    "linkedin_url",
    "phone"
  ]
}
```

---

## 🛡️ Edge Cases Handled

1. **Scanned / Image-Only PDFs**: Detected using text density heuristics and flags an explicit `ScannedPDFError` with an actionable error message rather than failing silently.
2. **Missing Dates / Open-Ended Ranges**: Recognizes `"Present"`, `"Current"`, `"Now"` and computes tenure relative to current date.
3. **Pydantic Validation Recovery**: If the LLM produces an invalid type (e.g. malformed email or string instead of int for education year), the error details are sent back in an automated 1-step retry loop.
4. **Flexible API Key Storage**: Key can be supplied via environment variable, `.env` file, or typed dynamically in the UI sidebar.
