import io
import json
import os
import streamlit as st
from dotenv import load_dotenv

from file_parser import parse_resume_file, ScannedPDFError, EmptyDocumentError, FileParserError
from extractor import extract_resume_from_text, ExtractionError, DEFAULT_MODEL, FALLBACK_MODEL
from schema import ResumeSchema

load_dotenv()

# Streamlit Page Config
st.set_page_config(
    page_title="Resume Structured Output Agent",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for modern UI
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #64748B;
        margin-bottom: 1.5rem;
    }
    .badge {
        display: inline-block;
        padding: 4px 10px;
        margin: 2px 4px;
        border-radius: 12px;
        font-size: 0.85rem;
        font-weight: 500;
    }
    .badge-tech {
        background-color: #EFF6FF;
        color: #1D4ED8;
        border: 1px solid #BFDBFE;
    }
    .badge-soft {
        background-color: #F0FDF4;
        color: #15803D;
        border: 1px solid #BBF7D0;
    }
    .badge-missing {
        background-color: #FEF2F2;
        color: #B91C1C;
        border: 1px solid #FECACA;
    }
    .contact-card {
        background-color: #F8FAFC;
        border-radius: 8px;
        padding: 1rem 1.2rem;
        border: 1px solid #E2E8F0;
        margin-bottom: 1rem;
    }
    .experience-card {
        background-color: #FFFFFF;
        border-radius: 8px;
        padding: 1rem;
        border-left: 4px solid #3B82F6;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        margin-bottom: 0.8rem;
    }
</style>
""", unsafe_allow_html=True)


# Sidebar Configuration
with st.sidebar:
    st.header("⚙️ Settings")
    
    # Keep the secret server-side; never send it to the browser as a widget value.
    env_key = os.getenv("GEMINI_API_KEY", "").strip()
    if env_key:
        st.success("✅ Gemini API key configured on the server.")
    else:
        st.error("❌ Gemini API key is not configured on the server.")
    st.caption("Set `GEMINI_API_KEY` in `.env` or the server environment.")

    
    model_choice = st.selectbox(
        "Gemini Model",
        options=[
            "gemini-3.6-flash",
            "gemini-2.5-flash",
            "gemini-2.0-flash"
        ],
        index=0,
        help="Select the Gemini model for structured extraction."
    )

    st.markdown("---")
    st.subheader("🧪 Quick Test Samples")
    st.caption("Don't have a resume handy? Try one of the generated test samples:")
    
    sample_files = {
        "Alex Mercer (Senior Full-Stack - PDF)": "sample_resumes/alex_mercer_senior_engineer.pdf",
        "Taylor Brooks (Junior DS - DOCX)": "sample_resumes/taylor_brooks_junior_ds.docx",
        "Empty / Scanned PDF (Error Test)": "sample_resumes/empty_scanned_sample.pdf"
    }
    
    selected_sample = st.selectbox("Choose a sample resume:", ["None"] + list(sample_files.keys()))
    load_sample_btn = st.button("Load Selected Sample", use_container_width=True)

    st.markdown("---")
    st.caption("Powered by **Google Gemini API** & **Pydantic v2**.")


# Main UI Header
st.markdown('<div class="main-header">📄 Resume Structured Output Agent</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">Upload a PDF or DOCX resume to extract validated, structured JSON with strict Pydantic schema enforcement via Google Gemini.</div>',
    unsafe_allow_html=True
)

# Handle file upload or sample selection
uploaded_file = st.file_uploader(
    "Choose a resume file (PDF or DOCX)",
    type=["pdf", "docx"],
    help="Upload your candidate resume in PDF or DOCX format."
)

active_file_source = None
active_filename = None

if load_sample_btn and selected_sample != "None":
    sample_path = sample_files[selected_sample]
    if os.path.exists(sample_path):
        with open(sample_path, "rb") as f:
            active_file_source = io.BytesIO(f.read())
        active_filename = os.path.basename(sample_path)
        st.session_state["sample_loaded"] = {
            "source": active_file_source,
            "filename": active_filename
        }
    else:
        st.warning(f"Sample file '{sample_path}' not found on disk. Run generate_samples.py first.")
elif "sample_loaded" in st.session_state and uploaded_file is None:
    active_file_source = st.session_state["sample_loaded"]["source"]
    active_filename = st.session_state["sample_loaded"]["filename"]

if uploaded_file is not None:
    active_file_source = uploaded_file
    active_filename = uploaded_file.name
    if "sample_loaded" in st.session_state:
        del st.session_state["sample_loaded"]

# Action Button
if active_file_source is not None:
    st.info(f"📁 Document selected: **{active_filename}**")
    parse_col1, parse_col2 = st.columns([1, 4])
    with parse_col1:
        start_extraction = st.button("🚀 Extract Resume", type="primary", use_container_width=True)

    if start_extraction:
        # Check API key
        active_key = env_key or None
        if not active_key:
            st.error("❌ Google Gemini API Key is required. Set GEMINI_API_KEY in `.env` or the server environment.")
            st.stop()

        # Step 1: Extract Text from File
        with st.status("🔍 Processing Resume...", expanded=True) as status:
            try:
                st.write(f"Extracting plain text from `{active_filename}`...")
                raw_text = parse_resume_file(active_file_source, active_filename)
                st.write(f"✅ Text extracted successfully ({len(raw_text.split())} words).")
            except ScannedPDFError as spe:
                status.update(label="❌ Scanned PDF detected", state="error", expanded=True)
                st.error(f"**Scanned Document Warning**: {str(spe)}")
                st.stop()
            except EmptyDocumentError as ede:
                status.update(label="❌ Document has no readable text", state="error", expanded=True)
                st.error(f"**Empty Document Warning**: {str(ede)}")
                st.stop()
            except FileParserError as fpe:
                status.update(label="❌ Parsing failed", state="error", expanded=True)
                st.error(f"**File Processing Error**: {str(fpe)}")
                st.stop()
            except Exception as ex:
                status.update(label="❌ Unexpected Error", state="error", expanded=True)
                st.error(f"**Unexpected Error**: {str(ex)}")
                st.stop()

            # Step 2: Call Gemini Agent with Structured Output
            try:
                st.write(f"Calling Gemini ({model_choice}) with native structured output enforcement...")
                resume_data: ResumeSchema = extract_resume_from_text(
                    raw_text,
                    api_key=active_key,
                    model=model_choice
                )
                st.write("✅ Structured extraction & Pydantic validation successful!")
                status.update(label="🎉 Resume Extracted Successfully!", state="complete", expanded=False)
                st.session_state["extracted_resume"] = resume_data
            except ExtractionError as ee:
                status.update(label="❌ Extraction failed", state="error", expanded=True)
                st.error(f"**Extraction Error**: {str(ee)}")
                st.stop()
            except Exception as ex:
                status.update(label="❌ Processing Error", state="error", expanded=True)
                st.error(f"**Error**: {str(ex)}")
                st.stop()

# Display Extracted Results
if "extracted_resume" in st.session_state:
    data: ResumeSchema = st.session_state["extracted_resume"]
    
    st.markdown("---")

    # Header Card: Candidate Overview & Metrics
    header_col1, header_col2, header_col3 = st.columns([2, 1, 1])

    with header_col1:
        st.subheader(f"👤 {data.full_name}")
        contact_items = []
        if data.email:
            contact_items.append(f"📧 [{data.email}](mailto:{data.email})")
        if data.phone:
            contact_items.append(f"📞 {data.phone}")
        if data.location:
            contact_items.append(f"📍 {data.location}")
        linkedin = getattr(data, "linkedin_url", None)
        if linkedin:
            contact_items.append(f"🔗 [LinkedIn]({linkedin})")
        github = getattr(data, "github_url", None)
        if github:
            contact_items.append(f"💻 [GitHub]({github})")
        portfolio = getattr(data, "portfolio_url", None)
        if portfolio:
            contact_items.append(f"🌐 [Portfolio]({portfolio})")

        st.markdown(" • ".join(contact_items) if contact_items else "*No contact details found*")

    with header_col2:
        conf_val = data.parsing_confidence if data.parsing_confidence is not None else 0.0
        conf_pct = int(conf_val * 100)
        st.metric(
            label="Parsing Confidence",
            value=f"{conf_pct}%",
            help="Confidence reported by the LLM based on resume clarity and completeness."
        )
        st.progress(conf_val)

    with header_col3:
        exp_years = f"{data.total_experience_years} yrs" if data.total_experience_years is not None else "N/A"
        st.metric(
            label="Total Experience",
            value=exp_years,
            help="Sum of all work experience durations calculated from dates."
        )

    # Missing Fields Warning Banner
    if data.missing_fields:
        st.warning("**Missing / Unspecified Fields Detected:**", icon="⚠️")
        missing_badges = " ".join([f'<span class="badge badge-missing">⚠️ {f}</span>' for f in data.missing_fields])
        st.markdown(missing_badges, unsafe_allow_html=True)

    # Professional Summary
    if data.summary:
        with st.expander("📝 Professional Summary", expanded=True):
            st.write(data.summary)

    # Work Experience Section
    with st.expander(f"💼 Work Experience ({len(data.work_experience)})", expanded=True):
        if not data.work_experience:
            st.info("No work experience entries extracted.")
        else:
            for idx, exp in enumerate(data.work_experience, start=1):
                dur_str = f"({exp.duration_months} months)" if exp.duration_months else ""
                st.markdown(
                    f"**{exp.role}** at **{exp.company}**  \n"
                    f"*{exp.start_date} — {exp.end_date}* {dur_str}"
                )
                if exp.description:
                    for bullet in exp.description:
                        st.markdown(f"- {bullet}")
                st.markdown("---")

    # Education Section
    with st.expander(f"🎓 Education ({len(data.education)})", expanded=True):
        if not data.education:
            st.info("No education entries extracted.")
        else:
            for edu in data.education:
                grade_str = f"| Grade: {edu.grade}" if edu.grade else ""
                st.markdown(
                    f"**{edu.degree}**  \n"
                    f"{edu.institution} ({edu.start_year} – {edu.end_year}) {grade_str}"
                )
                st.markdown("---")

    # Skills Section
    with st.expander("🛠️ Skills", expanded=True):
        col_t, col_s = st.columns(2)
        with col_t:
            st.markdown("**Technical Skills:**")
            if data.technical_skills:
                badges = " ".join([f'<span class="badge badge-tech">{s}</span>' for s in data.technical_skills])
                st.markdown(badges, unsafe_allow_html=True)
            else:
                st.caption("None listed")
        with col_s:
            st.markdown("**Soft Skills:**")
            if data.soft_skills:
                badges = " ".join([f'<span class="badge badge-soft">{s}</span>' for s in data.soft_skills])
                st.markdown(badges, unsafe_allow_html=True)
            else:
                st.caption("None listed")

    # Key Projects Section
    with st.expander(f"🚀 Projects ({len(data.projects)})", expanded=True):
        if not data.projects:
            st.info("No projects extracted.")
        else:
            for proj in data.projects:
                st.markdown(f"**{proj.title}**")
                st.write(proj.description)
                if proj.tech_used:
                    tech_pills = " ".join([f'<span class="badge badge-tech">{t}</span>' for t in proj.tech_used])
                    st.markdown(tech_pills, unsafe_allow_html=True)
                st.markdown("---")

    # Certifications Section
    with st.expander(f"📜 Certifications ({len(data.certifications)})", expanded=True):
        if not data.certifications:
            st.info("No certifications extracted.")
        else:
            for cert in data.certifications:
                year_str = f"({cert.year})" if cert.year else ""
                st.markdown(f"- **{cert.name}** — *{cert.issuer}* {year_str}")

    # Full Validated JSON & Download Button
    st.markdown("### 📥 Validated JSON Output")
    json_str = data.model_dump_json(indent=2)
    
    col_dl1, col_dl2 = st.columns([2, 5])
    with col_dl1:
        st.download_button(
            label="💾 Download JSON",
            data=json_str,
            file_name=f"{data.full_name.replace(' ', '_')}_structured_resume.json",
            mime="application/json",
            type="primary",
            use_container_width=True
        )

    with st.expander("View Full Raw JSON", expanded=False):
        st.code(json_str, language="json")
