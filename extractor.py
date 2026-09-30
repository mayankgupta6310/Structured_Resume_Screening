import datetime
import json
import logging
import os
import re
import time
from typing import Optional, Tuple
from dateutil import parser as date_parser
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import ValidationError

from schema import ResumeSchema, WorkExperience

load_dotenv()
logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-3.6-flash"
FALLBACK_MODEL = "gemini-3.6-flash"


class ExtractionError(Exception):
    """Raised when resume extraction fails after retries."""
    pass


def parse_date_to_year_month(date_str: str) -> Optional[Tuple[int, int]]:
    """
    Parses a date string (e.g., 'Jan 2020', '2020-05', '06/2021', '2022') into (year, month).
    Returns None if unparseable.
    """
    if not date_str or not date_str.strip():
        return None

    cleaned = date_str.strip().lower()

    # Handle 'present', 'current', 'now', 'ongoing'
    if any(k in cleaned for k in ["present", "current", "now", "ongoing", "today"]):
        now = datetime.datetime.now()
        return (now.year, now.month)

    # Clean punctuation
    cleaned_text = re.sub(r"[^\w\s/.-]", " ", date_str).strip()

    # Match simple 4-digit year like '2022'
    year_only_match = re.fullmatch(r"(\d{4})", cleaned_text)
    if year_only_match:
        return (int(year_only_match.group(1)), 1)

    try:
        dt = date_parser.parse(cleaned_text, default=datetime.datetime(2000, 1, 1), fuzzy=True)
        return (dt.year, dt.month)
    except Exception:
        # Fallback: find any 4-digit year
        year_match = re.search(r"\b(19\d\d|20\d\d)\b", cleaned_text)
        if year_match:
            return (int(year_match.group(1)), 1)
        return None


def calculate_duration_months(start_date: str, end_date: str) -> Optional[int]:
    """
    Calculates duration in months between start_date and end_date.
    Includes both starting and ending months (e.g. Jan 2020 to Jan 2020 is 1 month).
    """
    start_ym = parse_date_to_year_month(start_date)
    end_ym = parse_date_to_year_month(end_date)

    if not start_ym or not end_ym:
        return None

    start_year, start_month = start_ym
    end_year, end_month = end_ym

    diff = (end_year - start_year) * 12 + (end_month - start_month) + 1
    return max(1, diff) if diff > 0 else 1


def enrich_resume_durations(resume: ResumeSchema) -> ResumeSchema:
    """
    Computes duration_months for each work experience entry if missing or recomputable,
    and updates total_experience_years.
    """
    total_months = 0
    has_any_duration = False

    for exp in resume.work_experience:
        calc_months = calculate_duration_months(exp.start_date, exp.end_date)
        if calc_months is not None and calc_months > 0:
            exp.duration_months = calc_months
            total_months += calc_months
            has_any_duration = True
        elif exp.duration_months is not None and exp.duration_months > 0:
            total_months += exp.duration_months
            has_any_duration = True

    if has_any_duration:
        resume.total_experience_years = round(total_months / 12.0, 1)
    elif resume.total_experience_years is None and not resume.work_experience:
        resume.total_experience_years = 0.0

    return resume


def check_missing_fields(resume: ResumeSchema) -> ResumeSchema:
    """
    Programmatically verifies expected fields and ensures missing_fields is accurate.
    """
    existing_missing = set(resume.missing_fields)

    checks = [
        ("email", resume.email is None or str(resume.email).strip() == ""),
        ("phone", resume.phone is None or not str(resume.phone).strip()),
        ("location", resume.location is None or not str(resume.location).strip()),
        ("linkedin_url", resume.linkedin_url is None or not str(resume.linkedin_url).strip()),
        ("github_url", resume.github_url is None or not str(resume.github_url).strip()),
        ("summary", resume.summary is None or not str(resume.summary).strip()),
        ("technical_skills", len(resume.technical_skills) == 0),
        ("work_experience", len(resume.work_experience) == 0),
        ("education", len(resume.education) == 0),
        ("certifications", len(resume.certifications) == 0),
        ("projects", len(resume.projects) == 0),
    ]

    for field_name, is_missing in checks:
        if is_missing and field_name not in existing_missing:
            resume.missing_fields.append(field_name)

    # Ensure list is deduplicated and sorted
    resume.missing_fields = sorted(list(set(resume.missing_fields)))
    return resume


SYSTEM_PROMPT = """You are an expert resume parsing AI.
Your task is to analyze the provided raw resume text and extract all information into a strict, structured JSON format adhering exactly to the provided schema.

Guidelines:
1. Extract all factual information accurately without hallucinating details.
2. Extract candidate contact, web, and social links:
   - LinkedIn profile URL into `linkedin_url`
   - GitHub profile URL into `github_url`
   - Portfolio, personal website, or blog link into `portfolio_url`
3. If the resume text contains an 'Extracted Hyperlinks' section (e.g., 'Link: [visible text] -> [URL]'), resolve those URLs to the appropriate fields:
   - Match portfolio/website URLs to `portfolio_url`
   - Match LinkedIn URLs to `linkedin_url`
   - Match GitHub URLs to `github_url`
4. For missing information (e.g. if no phone, email, github, portfolio, or certifications are present), set the corresponding fields to null or empty lists, and list the missing field names in `missing_fields`.
5. Self-report a `parsing_confidence` score between 0.0 and 1.0 based on how clean, complete, and unambiguous the resume text is (e.g., 0.95 for a complete, well-formatted resume; 0.50 for a partial or fragmented resume).
6. Extract work experience dates faithfully (e.g., "Jan 2021", "2020", "Present").
7. Extract education start_year and end_year as integers. If only graduation year is provided, estimate start_year or set start_year = end_year - 4 for bachelor's or end_year - 2 for master's if reasonable.
8. The output must strictly follow the JSON schema provided.
"""


def extract_resume_from_text(
    resume_text: str,
    api_key: Optional[str] = None,
    model: str = DEFAULT_MODEL
) -> ResumeSchema:
    """
    Extracts structured resume data from raw text using Google Gemini API native structured output.
    Validates output with Pydantic and retries once upon validation failure.
    
    Args:
        resume_text: Plain text of the resume.
        api_key: Gemini API key (optional, falls back to GEMINI_API_KEY env var).
        model: Gemini model name to use (default: 'gemini-3.6-flash').
        
    Returns:
        Validated and enriched ResumeSchema instance.
        
    Raises:
        ExtractionError: If API key is missing or extraction fails.
    """
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        raise ExtractionError(
            "Gemini API key is not configured. Please provide it in the UI sidebar, "
            "set the GEMINI_API_KEY environment variable, or create a .env file."
        )

    try:
        client = genai.Client(api_key=key)
    except Exception as e:
        raise ExtractionError(f"Failed to initialize Gemini Client: {str(e)}") from e

    prompt = f"Please extract the structured information from the following resume text:\n\n{resume_text}"

    def _call_gemini(target_model: str, user_prompt: str = prompt):
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                return client.models.generate_content(
                    model=target_model,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        response_mime_type="application/json",
                        response_schema=ResumeSchema,
                    ),
                )
            except Exception as err:
                err_str = str(err)
                if "API_KEY_INVALID" in err_str or "API key not valid" in err_str:
                    raise ExtractionError(
                        "Invalid Google Gemini API Key. Please verify your key or obtain a new free key from "
                        "Google AI Studio (https://aistudio.google.com/apikey). Note: Valid Gemini keys typically start with 'AIzaSy' and are 39 characters long."
                    ) from err
                if ("503" in err_str or "UNAVAILABLE" in err_str or "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "high demand" in err_str) and attempt < max_attempts:
                    sleep_sec = float(2 * attempt)
                    delay_match = re.search(r"retry in (\d+(?:\.\d+)?)s", err_str, re.IGNORECASE)
                    if delay_match:
                        sleep_sec = min(float(delay_match.group(1)) + 1.5, 60.0)
                    logger.warning(f"Transient Gemini API issue (attempt {attempt}/{max_attempts}). Waiting {sleep_sec:.1f}s before retry...")
                    time.sleep(sleep_sec)
                    continue
                raise err

    # First attempt with native structured output (response_schema=ResumeSchema)
    try:
        response = _call_gemini(model)
    except ExtractionError:
        raise
    except Exception as e:
        # If default model fails for another reason, try fallback model if distinct
        if model == DEFAULT_MODEL and FALLBACK_MODEL != DEFAULT_MODEL:
            try:
                response = _call_gemini(FALLBACK_MODEL)
            except ExtractionError:
                raise
            except Exception as e_inner:
                raise ExtractionError(f"Gemini API call failed: {str(e_inner)}") from e_inner
        else:
            raise ExtractionError(f"Gemini API call failed: {str(e)}") from e

    # Parse and validate response
    raw_text_output = response.text
    if not raw_text_output:
        raise ExtractionError("Gemini returned an empty response.")

    try:
        # If response.parsed is an instance of ResumeSchema, use it; otherwise validate JSON text
        if hasattr(response, "parsed") and isinstance(response.parsed, ResumeSchema):
            resume_obj = response.parsed
        else:
            resume_obj = ResumeSchema.model_validate_json(raw_text_output)
    except (ValidationError, Exception) as val_err:
        logger.warning("First validation attempt failed: %s. Retrying with error feedback...", val_err)
        # Attempt 2: send the error details back to Gemini to fix
        error_details = str(val_err)
        retry_prompt = (
            f"The previous extraction attempt failed Pydantic validation with the following error:\n{error_details}\n\n"
            f"Here is the previous raw output:\n{raw_text_output}\n\n"
            f"Original resume text:\n{resume_text}\n\n"
            f"Please correct the data to strictly adhere to the ResumeSchema specification."
        )

        try:
            retry_response = _call_gemini(model, retry_prompt)
            if hasattr(retry_response, "parsed") and isinstance(retry_response.parsed, ResumeSchema):
                resume_obj = retry_response.parsed
            else:
                resume_obj = ResumeSchema.model_validate_json(retry_response.text)
        except Exception as retry_err:
            raise ExtractionError(
                f"Resume extraction failed validation after retry. Errors: {str(retry_err)}"
            ) from retry_err

    # Enrich durations and experience
    resume_obj = enrich_resume_durations(resume_obj)

    # Ensure missing_fields is comprehensively populated
    resume_obj = check_missing_fields(resume_obj)

    return resume_obj
