import json
from typing import List, Optional
from pydantic import BaseModel, Field
from google.genai import types
from ..config import get_gemini_client, DEFAULT_MODEL

#made a class for companies which have important fields in them
class CompanyProfile(BaseModel):
    company_name: str = Field(description="The official name of the company.")
    funding_stage: Optional[str] = Field(description="The funding stage of the company (e.g. Seed, Series A, IPO, Bootstrapped, Public).")
    employee_count: Optional[int] = Field(description="Approximate number of employees.")
    tech_stack: List[str] = Field(description="List of technologies, frameworks, or software used by the company.")
    key_news: Optional[str] = Field(description="Brief summary of recent company news, press releases, or key events.")

#function to profile a company. Get's geminin client using api in env file, aquery is asks gemini to research the company. prompt is a detailed version asking for specific info.  query is pasted into prompt
#give config for the respond to be in json, low temp for this situation since creativity not needed, response schema in class of company profile. model, prompt and config are passed to gemini's response function. 
#then overall the function returns an instance of the company class with info sourced from google search organized by gemini into the data structure. 
def profile_company(domain: str, company_hint: Optional[str] = None) -> CompanyProfile:
    """
    Research a company's domain and return structured profile details.
    Leverages Gemini's built-in Google Search Grounding to find current data.
    """
    client = get_gemini_client()
    
    query = f"Research the company that owns the domain '{domain}'"
    if company_hint:
        query += f" (hint/name: {company_hint})"
        
    prompt = f"""
    You are an expert market researcher. Query current sources to find detailed information about the company associated with the domain: {domain}.
    
    Specifically, retrieve:
    1. Official company name.
    2. Funding stage (e.g. Seed, Series A, Series B, IPO, Public, Bootstrapped, Private).
    3. Approximate employee count.
    4. Tech stack (technologies, software, frameworks, or services used by the company).
    5. Key recent news (summary of press releases or major events in the last 12 months).
    
    Research Query: {query}
    """
    
    # Configure Gemini with Google Search tool and structured JSON output schema
    config = types.GenerateContentConfig(
        tools=[{"google_search": {}}],  # Google Search grounding
        response_mime_type="application/json",
        response_schema=CompanyProfile,
        temperature=0.1
    )
    
    response = client.models.generate_content(
        model=DEFAULT_MODEL,
        contents=prompt,
        config=config
    )
    
    try:
        # Load the JSON string into the Pydantic model
        profile_data = json.loads(response.text)
        return CompanyProfile(**profile_data)
    except Exception as e:
        # Fallback in case of parsing issues, parse using basic LLM call
        fallback_prompt = f"""
        Extract the structured JSON from the text below. Make sure it follows this schema:
        {CompanyProfile.model_json_schema()}
        
        Text:
        {response.text}
        """
        fallback_response = client.models.generate_content(
            model=DEFAULT_MODEL,
            contents=fallback_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=CompanyProfile
            )
        )
        profile_data = json.loads(fallback_response.text)
        return CompanyProfile(**profile_data)
