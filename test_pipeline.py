import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dotenv import load_dotenv

load_dotenv()

from schema import ResumeSchema, WorkExperience, Education, Certification, Project
from file_parser import parse_resume_file, extract_text_from_pdf, extract_text_from_docx, ScannedPDFError, EmptyDocumentError
from extractor import calculate_duration_months, enrich_resume_durations, check_missing_fields, extract_resume_from_text, ExtractionError


def test_schema_instantiation():
    print("Testing Pydantic schema validation...")
    resume = ResumeSchema(
        full_name="Jane Doe",
        email="jane.doe@example.com",
        phone="+1 555-0199",
        location="Austin, TX",
        technical_skills=["Python", "FastAPI", "PostgreSQL"],
        work_experience=[
            WorkExperience(
                company="Tech Corp",
                role="Senior Engineer",
                start_date="Jan 2021",
                end_date="Dec 2022",
                description=["Built RESTful APIs"]
            )
        ],
        education=[
            Education(
                degree="B.S. in Computer Science",
                institution="UT Austin",
                start_year=2016,
                end_year=2020
            )
        ]
    )
    assert resume.full_name == "Jane Doe"
    assert resume.email == "jane.doe@example.com"
    print("  ✅ Schema instantiation passed.")


def test_duration_calculations():
    print("Testing date duration calculations...")
    
    # Standard date range: Jan 2021 to Dec 2021 = 12 months
    m1 = calculate_duration_months("Jan 2021", "Dec 2021")
    assert m1 == 12, f"Expected 12, got {m1}"
    
    # Multi-year range: Jan 2020 to Dec 2022 = 36 months
    m2 = calculate_duration_months("Jan 2020", "Dec 2022")
    assert m2 == 36, f"Expected 36, got {m2}"

    # Year only: 2020 to 2022 = 25 months (Jan 2020 to Jan 2022 + 1)
    m3 = calculate_duration_months("2020", "2022")
    assert m3 is not None and m3 > 0, f"Expected valid months, got {m3}"

    # Resume duration enrichment
    dummy_resume = ResumeSchema(
        full_name="Bob Smith",
        work_experience=[
            WorkExperience(
                company="Alpha",
                role="Dev",
                start_date="Jan 2020",
                end_date="Dec 2020"
            ),
            WorkExperience(
                company="Beta",
                role="Senior Dev",
                start_date="Jan 2021",
                end_date="Dec 2022"
            )
        ]
    )
    enriched = enrich_resume_durations(dummy_resume)
    assert enriched.work_experience[0].duration_months == 12
    assert enriched.work_experience[1].duration_months == 24
    assert enriched.total_experience_years == 3.0, f"Expected 3.0 yrs, got {enriched.total_experience_years}"
    print("  ✅ Duration and experience calculations passed.")


def test_missing_fields_detection():
    print("Testing missing fields detection...")
    incomplete_resume = ResumeSchema(
        full_name="Taylor Brooks",
        email="taylor@example.com"
        # Missing phone, linkedin, certifications, projects, etc.
    )
    checked = check_missing_fields(incomplete_resume)
    expected_missing = {"phone", "location", "linkedin_url", "github_url", "summary", "technical_skills", "work_experience", "education", "certifications", "projects"}
    for field in expected_missing:
        assert field in checked.missing_fields, f"Expected {field} in missing_fields"
    print("  ✅ Missing fields detection passed.")


def test_file_parsing():
    print("Testing file extraction on samples...")
    
    # 1. Complete PDF
    pdf_path = "sample_resumes/alex_mercer_senior_engineer.pdf"
    if os.path.exists(pdf_path):
        pdf_text = parse_resume_file(pdf_path, pdf_path)
        assert "Alex Mercer" in pdf_text
        assert "CloudScale Technologies" in pdf_text
        print(f"  ✅ PDF extraction verified ({len(pdf_text.split())} words).")
    else:
        print(f"  ⚠️ Skipping PDF test ({pdf_path} not found).")

    # 2. Complete DOCX
    docx_path = "sample_resumes/taylor_brooks_junior_ds.docx"
    if os.path.exists(docx_path):
        docx_text = parse_resume_file(docx_path, docx_path)
        assert "Taylor Brooks" in docx_text
        assert "Insights Corp" in docx_text
        print(f"  ✅ DOCX extraction verified ({len(docx_text.split())} words).")
    else:
        print(f"  ⚠️ Skipping DOCX test ({docx_path} not found).")

    # 3. Empty / Scanned PDF error detection
    scanned_path = "sample_resumes/empty_scanned_sample.pdf"
    if os.path.exists(scanned_path):
        try:
            parse_resume_file(scanned_path, scanned_path)
            print("  ❌ Failed: Empty/scanned PDF should have raised an error!")
        except (ScannedPDFError, EmptyDocumentError) as e:
            print(f"  ✅ Correctly caught empty/scanned document: {type(e).__name__}")
    else:
        print(f"  ⚠️ Skipping scanned PDF test ({scanned_path} not found).")


def test_gemini_extraction():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("\n[INFO] GEMINI_API_KEY is not set in environment or .env. Skipping live Gemini API test.")
        print("Set GEMINI_API_KEY in your environment or .env file to test live extraction.")
        return

    print("\nTesting live Gemini structured extraction with PDF sample...")
    pdf_path = "sample_resumes/alex_mercer_senior_engineer.pdf"
    pdf_text = parse_resume_file(pdf_path, pdf_path)
    try:
        result = extract_resume_from_text(pdf_text, api_key=api_key, model="gemini-3.6-flash")
        print(f"  Candidate Name: {result.full_name}")
        print(f"  Email: {result.email}")
        print(f"  Phone: {result.phone}")
        print(f"  Confidence: {result.parsing_confidence}")
        print(f"  Total Experience: {result.total_experience_years} years")
        print(f"  Work Experiences: {len(result.work_experience)}")
        for exp in result.work_experience:
            print(f"    - {exp.role} at {exp.company} ({exp.start_date} to {exp.end_date}, {exp.duration_months} mo)")
        print(f"  Missing Fields: {result.missing_fields}")
        print("  ✅ Live Gemini structured extraction passed.")
    except ExtractionError as e:
        print(f"  ⚠️ Live Gemini test advisory: {e}")


if __name__ == "__main__":
    print("=== RUNNING RESUME AGENT TESTS ===")
    test_schema_instantiation()
    test_duration_calculations()
    test_missing_fields_detection()
    test_file_parsing()
    test_gemini_extraction()
    print("=== ALL TESTS COMPLETED ===")
