#outreach message generator file. Contains all function needed to format information and then a big function to generate the messaged, presumably with other functions and classes. 
import os
import re
import yaml
import json
import time
from typing import Optional, Dict, List
from pydantic import BaseModel, Field
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import get_gemini_client, DEFAULT_MODEL

# Load few-shot template config
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config", "message_examples.yaml")

#loads example messages from the message config file
def load_message_config() -> Dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}

#class for results when scanning a person to reach out to
class TopicScanResult(BaseModel):
    scanned_topic: str = Field(description="The primary technical or career topic discovered (e.g., 'your work on distributed ML pipelines', 'your transition into engineering')")
    authentic_compliment: str = Field(description="A genuine, non-generic compliment regarding their background or project focus")

#class for drafting messages, options for the description for both email and linkedIn
class GeneratedCopy(BaseModel):
    draft_email: Optional[str] = Field(default=None, description="Direct email draft, structured in 3 parts with subject line, ending with an open-ended ask to connect")
    draft_linkedin: Optional[str] = Field(default=None, description="LinkedIn note strictly under 300 characters, ending with an open-ended ask to connect")

#will retry this function up to 3 times. calls gemini with the config file, and prompt given in the function call. 
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=False)
def _call_gemini_topic_scan(client, prompt: str):
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=TopicScanResult,
        temperature=0.2
    )
    return client.models.generate_content(
        model=DEFAULT_MODEL,
        contents=prompt,
        config=config
    )

#does exactly what it says in function topic, using the given prompt and the name and company name
def scan_profile_for_topic(profile_text: str, candidate_name: str, company_name: str, alma_mater: Optional[str] = None, profile: Optional[Dict] = None) -> TopicScanResult:
    """
    Dedicated AI Scanner: Analyzes a Young Professional's profile snippet, headline, or background
    to find the single most compelling and authentic topic to connect over.
    """
    if not alma_mater:
        if profile and profile.get("alma_mater"):
            alma_mater = profile.get("alma_mater")
        else:
            try:
                from ..db.db import get_active_profile
                active_prof = get_active_profile()
                if active_prof:
                    alma_mater = active_prof.get("alma_mater")
            except Exception:
                alma_mater = None

    alumni_hint = f", or {alma_mater} alumni bond" if alma_mater else ""

    client = get_gemini_client()
    prompt = f"""
    Analyze the profile details for {candidate_name} at {company_name}:
    "{profile_text}"

    Extract:
    1. A natural, specific technical or career topic to connect over (e.g. specific tool, transition from college to their role, technical focus{alumni_hint}).
    2. A brief, genuine observation/compliment about their journey or technical focus.

    Avoid exaggerated flattery. Keep it grounded and conversational as coming from a fellow professional or recent graduate.
    """

    try:
        response = _call_gemini_topic_scan(client, prompt)
        if response and response.text:
            parsed = json.loads(response.text)
            return TopicScanResult(**parsed)
    except Exception as e:
        print(f"[Topic Scanner] Fallback used: {e}")

    return TopicScanResult(
        scanned_topic=f"your work and technical journey at {company_name}",
        authentic_compliment=f"really impressed by the growth and focus of your team at {company_name}"
    )

#same thing as calling topic scan but for class based on email vs. linkedIn
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=False)
def _call_gemini_copywriter(client, prompt: str):
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=GeneratedCopy,
        temperature=0.3
    )
    return client.models.generate_content(
        model=DEFAULT_MODEL,
        contents=prompt,
        config=config
    )

#function to actually get first name out of a profile, removing titles. 
def extract_clean_first_name(name: str) -> str:
    if not name:
        return "there"
    clean = re.sub(r'(?i)\b(data|scientist|engineer|lead|manager|senior|director|vp|head|recruiter|at|inc|llc|pwc|ey|kpmg|prospect)\b', '', name).strip()
    parts = clean.split()
    if parts and len(parts[0]) > 1:
        return parts[0].capitalize()
    raw_parts = name.strip().split()
    if raw_parts and len(raw_parts[0]) > 1:
        return raw_parts[0].capitalize()
    return "there"

#the overall message generation function includes all arguments needed and info to prompt gemini as needed.
def generate_personalized_copy(
    contact_name: str,
    contact_title: str,
    contact_classification: str, # "Hiring Manager" or "Young Professional"
    company_name: str,
    job_applied: bool = False,
    job_title: Optional[str] = None,
    profile_snippet: Optional[str] = None,
    ai_hook: Optional[str] = None,
    channel_preference: str = "EMAIL", # "EMAIL" or "LINKEDIN"
    tech_stack: Optional[str] = None,
    profile: Optional[Dict] = None
) -> GeneratedCopy:
    """
    Generate high-converting outreach copy trained on user examples:
    1. Hello / Context Hook
    2. Specific Compliment & Mutual Interest
    3. Open-ended polite call-to-action asking to chat further (NO scheduling/Calendly links)
    """
    # Resolve active profile details dynamically
    if not profile:
        try:
            from ..db.db import get_local_profile
            profile = get_local_profile()
        except Exception:
            profile = None

    cfg = load_message_config()
    sender_cfg = cfg.get("sender_profile", {})
    user_examples_cfg = cfg.get("user_provided_examples", {})

    if profile:
        sender_name = profile.get("full_name") or sender_cfg.get("name", "Job Seeker")
        alma_mater = profile.get("alma_mater") or sender_cfg.get("alma_mater", "")
        degree_major = profile.get("degree_major") or sender_cfg.get("degree_major", "")
        grad_year = profile.get("grad_year") or sender_cfg.get("grad_year", "")
        bio_summary = profile.get("bio_summary") or sender_cfg.get("background", "")
        skills = profile.get("skills") or "Engineering, Software, Data"
        target_roles = profile.get("target_roles") or "Technology"
        sample_hm = profile.get("sample_hiring_manager")
        sample_yp = profile.get("sample_young_professional")
    else:
        sender_name = sender_cfg.get("name", "Job Seeker")
        alma_mater = sender_cfg.get("alma_mater", "")
        degree_major = sender_cfg.get("education", "")
        grad_year = ""
        bio_summary = sender_cfg.get("background", "")
        skills = "Engineering, Software, Data"
        target_roles = "Technology"
        sample_hm = None
        sample_yp = None

    client = get_gemini_client()
    first_name = extract_clean_first_name(contact_name)
    sender_first_name = extract_clean_first_name(sender_name)
    tech_focus = tech_stack if tech_stack else "modern technology and engineering systems"

    # Determine Archetype
    is_hiring_manager = ("hiring manager" in contact_classification.lower()) or any(k in contact_title.lower() for k in ["manager", "director", "vp", "lead", "head", "recruiter"])

    # Collect relevant user sample messages to train the prompt (preferring profile voice samples)
    sample_texts = []
    if is_hiring_manager:
        if sample_hm and sample_hm.strip():
            sample_texts.append(f"-- User Voice Sample (Hiring Manager Outreach):\n{sample_hm.strip()}")
        elif user_examples_cfg.get("hiring_manager_samples"):
            for sample in user_examples_cfg["hiring_manager_samples"]:
                sample_texts.append(f"-- Sample (Hiring Manager):\n{sample.strip()}")
    else:
        if sample_yp and sample_yp.strip():
            sample_texts.append(f"-- User Voice Sample (Young Professional Outreach):\n{sample_yp.strip()}")
        elif user_examples_cfg.get("young_professional_samples"):
            for sample in user_examples_cfg["young_professional_samples"]:
                sample_texts.append(f"-- Sample (Young Professional):\n{sample.strip()}")

    user_style_guidance = "\n\n".join(sample_texts) if sample_texts else "Write in a natural, authentic, professional, and conversational tone."

    if ai_hook:
        hook_guidance = ai_hook
    elif not is_hiring_manager:
        hook_guidance = f"{alma_mater} alumni connection or mutual interest in {degree_major}" if alma_mater else f"shared technical interest in {tech_focus}"
    else:
        primary_role = target_roles.split(",")[0].strip() if target_roles else "engineering"
        hook_guidance = f"Growth and initiatives in {primary_role}"

    edu_str = f"{degree_major}" + (f" from {alma_mater}" if alma_mater else "") + (f" ({grad_year})" if grad_year else "")

    prompt = f"""
    You are an AI trained to write personalized outreach exactly in the authentic voice and style of {sender_name} ({edu_str}, {bio_summary}).

    **Sender Profile:**
    - Name: {sender_name}
    - Education: {edu_str}
    - Background: {bio_summary}
    - Core Skills & Expertise: {skills}
    - Target Focus: {target_roles}

    **Training Examples (Learn tone, syntax, and voice from these real samples):**
    {user_style_guidance}

    **Current Recipient:**
    - Name: {contact_name} ({first_name})
    - Title: {contact_title}
    - Category: {'Hiring Manager' if is_hiring_manager else 'Young Professional in Similar Role'}
    - Company: {company_name}
    - Job Context: {'Applied for ' + str(job_title) if (job_applied and job_title) else 'No specific job applied (Proactive networking)'}
    - Technical Focus: {tech_focus}
    - Topic / Hook Context: {hook_guidance}
    - Requested Channel: {channel_preference}

    **Structure Requirements (3-Part Formula):**
    1. Part 1: Hello & Context / Hook
    2. Part 2: Genuine Compliment & Mutual Interest (Why {sender_first_name} is interested in them and their specific technical challenges)
    3. Part 3: Open-Ended Call to Action (Politely asking if they would be open to a brief chat or coffee conversation sometime).

    **CRITICAL RULES:**
    - DO NOT INCLUDE ANY CALENDLY LINKS OR SCHEDULING URLS. The sender will send the link manually in a follow-up.
    - End cleanly with an open-ended question (e.g., 'Would you be open to a brief chat sometime next week?' or 'Would love to hear your perspective if you ever have a few minutes for a quick conversation!').
    - If Channel is 'EMAIL':
      - Under 125 words.
      - Punchy subject line.
    - If Channel is 'LINKEDIN':
      - STRICTLY UNDER 300 CHARACTERS.
    """

    try:
        response = _call_gemini_copywriter(client, prompt)
        if response and response.text:
            parsed = json.loads(response.text)
            copy_obj = GeneratedCopy(**parsed)
            if copy_obj.draft_email:
                copy_obj.draft_email = copy_obj.draft_email.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
            if copy_obj.draft_linkedin:
                copy_obj.draft_linkedin = copy_obj.draft_linkedin.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
                if len(copy_obj.draft_linkedin) > 298:
                    copy_obj.draft_linkedin = copy_obj.draft_linkedin[:295] + "..."
            return copy_obj
    except Exception as e:
        print(f"[Copywriter] Error/fallback: {e}")

    grad_str = f" from {alma_mater}" if alma_mater else ""
    major_str = f" in {degree_major}" if degree_major else ""
    subject_tag = f" - {sender_name}" + (f" ({alma_mater})" if alma_mater else "")

    if channel_preference == "EMAIL":
        return GeneratedCopy(
            draft_email=f"Subject: Connecting regarding {company_name}{subject_tag}\n\nHi {first_name},\n\nI recently graduated{grad_str}{major_str} and have been following {company_name}'s technical growth. I'd love to connect to learn more about your team's work!\n\nWould you be open to a brief conversation sometime next week?\n\nBest,\n{sender_first_name}",
            draft_linkedin=None
        )
    else:
        return GeneratedCopy(
            draft_email=None,
            draft_linkedin=f"Hi {first_name}, I saw your work at {company_name}! As a recent{grad_str}{major_str} grad, I'd love to connect and hear a bit about your journey if you're open to it! - {sender_first_name}"
        )
