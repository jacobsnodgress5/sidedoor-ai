import json
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from google.genai import types
from ..config import get_gemini_client, DEFAULT_MODEL

#contactinfo class
class ContactInfo(BaseModel):
    linkedin_url: str = Field(description="The LinkedIn profile URL of the contact.")
    full_name: str = Field(description="Full name of the contact.")
    title: str = Field(description="Their current job title.")
    classification: str = Field(description="Classification: must be exactly one of 'Hiring Manager', 'Advisory Mentor', or 'Peer'.")
    experience_summary: str = Field(description="Summary of past experience, education, or achievements.")
    relevance_score: int = Field(description="Relevance score from 0 to 100 (high is more relevant for networking/outreach).")
    ai_hook: str = Field(description="A highly personalized hook or icebreaker based on their background (e.g., a specific skill, mutual school/location, or company tech).")

#class which is simply a list of contact info
class ContactList(BaseModel):
    contacts: List[ContactInfo]

#works similar to the company sourcing function, just for contacts. 
def source_contacts(
    company_domain: str,
    company_name: str,
    limit: int = 3,
    target_roles: Optional[str] = None,
    alma_mater: Optional[str] = None,
    profile: Optional[Dict] = None
) -> List[ContactInfo]:
    """
    Source relevant contacts for a company. Uses Google Search Grounding to find key employees
    and structures them into a list of classified and scored contacts aligned with user goals.
    """
    if not profile:
        try:
            from ..db.db import get_active_profile
            profile = get_active_profile()
        except Exception:
            profile = None

    if not target_roles and profile:
        target_roles = profile.get("target_roles")
    if not alma_mater and profile:
        alma_mater = profile.get("alma_mater")

    target_focus = target_roles if target_roles else "Engineering and Technology"
    alumni_str = f" or alumni from {alma_mater}" if alma_mater else ""

    client = get_gemini_client()
    
    prompt = f"""
    You are an expert talent sourcing agent. Your task is to find key personnel working at '{company_name}' (domain: {company_domain}) whom a job seeker targeting {target_focus} should reach out to.
    
    Find up to {limit} people working at the company. Specifically, look for:
    1. Hiring Managers (e.g., Engineering Manager, Director, VP, Recruiter, or Talent Acquisition).
    2. Advisory Mentors (e.g., Senior Engineers, Leads, or Technical Specialists).
    3. Experienced Peers (e.g., professionals in roles related to {target_focus}{alumni_str}).
    
    For each contact found, classify them, score them (0-100) based on how helpful they would be to connect with for an outreach campaign in {target_focus}, and generate an 'ai_hook' (a personalized hook/icebreaker mentioning their role/company).
    
    Include their LinkedIn URLs (estimate them or find them from search results, e.g. linkedin.com/in/username).
    """
    
    config = types.GenerateContentConfig(
        tools=[{"google_search": {}}],  # Google Search grounding
        response_mime_type="application/json",
        response_schema=ContactList,
        temperature=0.2
    )
    
    response = client.models.generate_content(
        model=DEFAULT_MODEL,
        contents=prompt,
        config=config
    )
    
    try:
        contact_list = json.loads(response.text)
        return ContactList(**contact_list).contacts
    except Exception:
        # Fallback parsing
        fallback_prompt = f"""
        Extract the structured JSON from the text below. Make sure it follows this schema:
        {ContactList.model_json_schema()}
        
        Text:
        {response.text}
        """
        fallback_response = client.models.generate_content(
            model=DEFAULT_MODEL,
            contents=fallback_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ContactList
            )
        )
        contact_list = json.loads(fallback_response.text)
        return ContactList(**contact_list).contacts
