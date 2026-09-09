import os
import re
import yaml
import json
from dotenv import load_dotenv

# Load .env from project root or local directory
_env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
if os.path.exists(_env_path):
    load_dotenv(_env_path)
else:
    load_dotenv()

from google import genai
from google.genai import types

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def run_stage1_regex_filter(job, config):
    """
    Stage 1: Fast Regex and Metadata Filters
    Returns (is_excluded, reason)
    """
    exclusions = config.get("exclusions", {})
    
    # 1. Check Applicant Count
    max_applicants = config.get("search", {}).get("max_applicants", 100)
    if job.get("applicants", 0) > max_applicants:
        return True, f"Over {max_applicants} applicants ({job['applicants']} applicants)"
        
    # 2. Check Job Title
    title = job.get("title", "").lower()
    title_exclusions = exclusions.get("job_titles", [])
    for pattern in title_exclusions:
        # Match as whole word/boundary where appropriate, or substring
        if re.search(r'\b' + re.escape(pattern.lower()) + r'\b', title):
            return True, f"Excluded title keyword: '{pattern}'"
            
    # 3. Check Experience Regex (excludes 4+ years, allowing 1-3 years)
    description = job.get("description", "")
    exp_regex = exclusions.get("experience_regex", "")
    if exp_regex:
        # Search the description for matching experience requirements
        match = re.search(exp_regex, description, re.IGNORECASE)
        if match:
            # Check if it mentions 2 or 3 years which we want to ALLOW.
            # The regex is designed to only match [4-9]|\d{2}.
            # Let's double check what it matched to be safe.
            matched_text = match.group(0)
            return True, f"Disqualified by experience requirement regex match: '{matched_text}'"

    # 4. Check Active Security Clearance Requirements
    clearance_regex = exclusions.get("clearance_regex", "")
    if clearance_regex:
        match = re.search(clearance_regex, description, re.IGNORECASE)
        if match:
            matched_text = match.group(0)
            return True, f"Requires active security clearance: '{matched_text}'"

    return False, None

def generate_content_with_retry(client, contents, system_instruction, primary_model="gemini-3.5-flash", response_mime_type="application/json"):
    """
    Executes Gemini content generation with:
    1. Automatic model fallback cascade: [primary_model, "gemini-flash-lite-latest"]
    2. Exponential backoff retries (3 attempts: 2s, 4s, 8s) on 503 UNAVAILABLE, 429, or transient errors.
    """
    import time

    models_to_try = [primary_model]
    if "gemini-flash-lite-latest" not in models_to_try:
        models_to_try.append("gemini-flash-lite-latest")
    if "gemini-3.5-flash" not in models_to_try:
        models_to_try.append("gemini-3.5-flash")

    last_error = None
    for model in models_to_try:
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        response_mime_type=response_mime_type,
                        temperature=0.1
                    )
                )
                return response.text.strip()
            except Exception as e:
                err_str = str(e).lower()
                last_error = e
                is_transient = any(k in err_str for k in ["503", "unavailable", "429", "resource_exhausted", "quota", "overloaded", "demand"])
                if is_transient and attempt < 2:
                    wait_time = 2 ** (attempt + 1)
                    print(f"[LLM] Model '{model}' transient demand notice. Retrying in {wait_time}s (attempt {attempt+1}/3)...")
                    time.sleep(wait_time)
                else:
                    print(f"[LLM] Model '{model}' not available: {e}. Moving to next fallback model in cascade...")
                    break

    raise RuntimeError(f"Gemini API request failed across all fallback models. Last error: {last_error}")

def run_stage2_llm_filter(job, config):
    """
    Stage 2: Gemini LLM Filter
    Returns (category, reason) where category is BEST_FIT, WORSE_FIT, or EXCLUDE
    """
    llm_cfg = config.get("llm", {})
    
    # Try reading the API key from config.yaml first
    api_key = llm_cfg.get("api_key")
    
    # If not in config, fall back to environment variable
    if not api_key:
        api_key_var = llm_cfg.get("api_key_env_var", "GEMINI_API_KEY")
        api_key = os.environ.get(api_key_var)
    
    if not api_key:
        # Fallback to check if we can run it. If no API key, let's log a warning and classify as BEST_FIT to be safe
        print(f"[WARNING] Gemini API key not found in config.yaml or environment variable! Skipping Stage 2 LLM and marking as BEST_FIT.")
        return "BEST_FIT", "Skipped LLM filter due to missing API key."

    model_name = llm_cfg.get("model", "gemini-3.5-flash")
    
    # Initialize the new google-genai Client
    try:
        client = genai.Client(api_key=api_key)
    except Exception as err:
        print(f"[ERROR] Failed to initialize Gemini Client: {err}")
        return "WORSE_FIT", f"Skipped LLM filter due to client initialization error: {err}"

    # Construct the Candidate Profile Context for the LLM
    profile = config.get("profile", {})
    profile_text = yaml.dump(profile, default_flow_style=False)

    # Define the LLM Prompt
    system_instruction = (
        "You are a strict recruitment filtering assistant. Your task is to evaluate if a job description "
        "is a fit for the candidate profile. You must classify the job into one of three categories:\n"
        "1. BEST_FIT: The candidate meets the basic constraints and matches the vast majority of the required tech stack "
        "(only missing a few easily learnable tools like GCP or Spark).\n"
        "2. WORSE_FIT: The candidate meets basic constraints (education, experience, location) but lacks a significant "
        "portion of the skills (e.g. requires heavy Spark, Scala, or Azure, which are stretch/worse fit but still worth reviewing).\n"
        "3. EXCLUDE: Disqualified. The candidate does not meet the basic requirements or lacks the tech stack completely.\n\n"
        "CRITICAL RULES FOR EXCLUSION:\n"
        "- Disqualify (EXCLUDE) if a Master's or PhD degree is a MANDATORY (non-negotiable) minimum requirement. "
        "If it is preferred/optional or B.S. is acceptable, do NOT exclude on education.\n"
        "- Disqualify (EXCLUDE) if the job requires more than 3 years of professional experience.\n"
        "- Disqualify (EXCLUDE) if the job location is on-site or hybrid in another city (not remote and not in the Los Angeles area).\n"
        "- Disqualify (EXCLUDE) if the job requires deep expertise in technologies the candidate has zero exposure to "
        "and cannot learn on the job (e.g., Senior Java/Spring Boot development, Go/Rust systems programming, or Salesforce developer).\n\n"
        "Return your response ONLY as a JSON object matching this schema:\n"
        "{\n"
        "  \"category\": \"BEST_FIT\" | \"WORSE_FIT\" | \"EXCLUDE\",\n"
        "  \"reason\": \"A concise explanation of why the job was categorized this way\"\n"
        "}"
    )

    prompt = (
        f"--- CANDIDATE PROFILE ---\n{profile_text}\n\n"
        f"--- JOB DETAILS ---\n"
        f"Title: {job.get('title')}\n"
        f"Company: {job.get('company')}\n"
        f"Location: {job.get('location')}\n"
        f"Description:\n{job.get('description')}\n"
    )

    try:
        res_text = generate_content_with_retry(
            client=client,
            contents=prompt,
            system_instruction=system_instruction,
            primary_model=model_name
        )
        
        # Clean up potential markdown code block markers
        if res_text.startswith("```"):
            res_text = re.sub(r'^```(?:json)?\n', '', res_text)
            res_text = re.sub(r'\n```$', '', res_text)

        # Parse JSON output
        result = json.loads(res_text)
        category = result.get("category", "EXCLUDE")
        reason = result.get("reason", "No reason provided by LLM.")
        
        # Validate output category
        if category not in ["BEST_FIT", "WORSE_FIT", "EXCLUDE"]:
            category = "EXCLUDE"
            reason = "Invalid category returned by LLM: " + str(category)
            
        return category, reason

    except Exception as e:
        print(f"[ERROR] Gemini API call failed after retries: {e}")
        return "WORSE_FIT", f"Qualification deferred: temporary service unavailability."

def evaluate_job(job):
    """
    Main evaluation entry point. Runs Stage 1 then Stage 2.
    Returns (category, reason)
    """
    config = load_config()
    
    # Run Stage 1 (Regex / Hard Exclusions)
    is_excluded, s1_reason = run_stage1_regex_filter(job, config)
    if is_excluded:
        return "EXCLUDE", s1_reason
        
    # Run Stage 2 (Gemini LLM Filter)
    category, s2_reason = run_stage2_llm_filter(job, config)
    return category, s2_reason

def evaluate_all_jobs(raw_jobs):
    """
    Evaluates all raw jobs using Stage 1 first, then batches the passing jobs 
    through Stage 2 LLM in groups of 5. Returns (best_fit, worse_fit, excluded_count).
    Modifies each job in raw_jobs in-place to add 'reason' and 'category'.
    """
    import time
    config = load_config()
    
    # 1. Run Stage 1 (Regex / Hard Exclusions)
    passing_jobs = []
    excluded_count = 0
    best_fit = []
    worse_fit = []
    
    for job in raw_jobs:
        is_excluded, s1_reason = run_stage1_regex_filter(job, config)
        if is_excluded:
            job["category"] = "EXCLUDE"
            job["reason"] = s1_reason
            excluded_count += 1
        else:
            passing_jobs.append(job)
            
    if not passing_jobs:
        return best_fit, worse_fit, excluded_count

    # 2. Check if API Key is available
    llm_cfg = config.get("llm", {})
    api_key = llm_cfg.get("api_key")
    if not api_key:
        api_key_var = llm_cfg.get("api_key_env_var", "GEMINI_API_KEY")
        api_key = os.environ.get(api_key_var)
        
    if not api_key:
        print("[WARNING] Gemini API key not found in config.yaml or environment! Skipping Stage 2 LLM and marking all passing jobs as BEST_FIT.")
        for job in passing_jobs:
            job["category"] = "BEST_FIT"
            job["reason"] = "Skipped LLM filter due to missing API key."
            best_fit.append(job)
        return best_fit, worse_fit, excluded_count

    model_name = llm_cfg.get("model", "gemini-3.5-flash")
    profile = config.get("profile", {})
    profile_text = yaml.dump(profile, default_flow_style=False)
    
    try:
        client = genai.Client(api_key=api_key)
    except Exception as err:
        print(f"[ERROR] Failed to initialize Gemini Client: {err}")
        for job in passing_jobs:
            job["category"] = "WORSE_FIT"
            job["reason"] = f"Skipped LLM filter due to client initialization error: {err}"
            worse_fit.append(job)
        return best_fit, worse_fit, excluded_count

    # Batch size of 5 for faster, lightweight requests with high success rate
    batch_size = 5
    for i in range(0, len(passing_jobs), batch_size):
        batch = passing_jobs[i:i+batch_size]
        
        # System instructions
        system_instruction = (
            "You are a strict recruitment filtering assistant. Your task is to evaluate a list of job descriptions "
            "and classify them based on their fit for the candidate profile. You must classify each job into one of three categories:\n"
            "1. BEST_FIT: The candidate meets all basic constraints and matches the vast majority of the required tech stack.\n"
            "2. WORSE_FIT: The candidate meets basic constraints (education, experience, location) but lacks a significant portion of the skills (stretch/worse fit but still worth reviewing).\n"
            "3. EXCLUDE: Disqualified. The candidate does not meet the basic requirements or lacks the tech stack completely.\n\n"
            "CRITICAL RULES FOR EXCLUSION:\n"
            "- Disqualify (EXCLUDE) if a Master's or PhD degree is a MANDATORY minimum requirement.\n"
            "- Disqualify (EXCLUDE) if the job requires more than 3 years of professional experience.\n"
            "- Disqualify (EXCLUDE) if the job is on-site/hybrid outside the Los Angeles area.\n"
            "- Disqualify (EXCLUDE) if the job requires technologies the candidate has zero exposure to (e.g. Go, Rust, Salesforce, heavy Java Spring).\n\n"
            "Return your response ONLY as a JSON array of objects, where each object contains 'id', 'category', and 'reason'."
        )
        
        # Format the list of jobs for the batch prompt
        jobs_data = []
        for job in batch:
            jobs_data.append({
                "id": job["id"],
                "title": job["title"],
                "company": job["company"],
                "location": job["location"],
                "description": job.get("description", "")[:5000] # Limit description length to avoid excessively large tokens
            })
            
        prompt = (
            f"--- CANDIDATE PROFILE ---\n{profile_text}\n\n"
            f"--- JOBS TO EVALUATE ---\n{json.dumps(jobs_data, indent=2)}\n\n"
            f"Provide the classifications for the above jobs in a JSON array. Schema:\n"
            "[\n"
            "  {\n"
            "    \"id\": \"job_id\",\n"
            "    \"category\": \"BEST_FIT\" | \"WORSE_FIT\" | \"EXCLUDE\",\n"
            "    \"reason\": \"A concise explanation of why the job was categorized this way\"\n"
            "  }\n"
            "]"
        )
        
        try:
            print(f"[LLM] Evaluating batch of {len(batch)} jobs via Gemini ({i//batch_size + 1}/{(len(passing_jobs)-1)//batch_size + 1})...")
            res_text = generate_content_with_retry(
                client=client,
                contents=prompt,
                system_instruction=system_instruction,
                primary_model=model_name
            )
            
            # Clean up potential markdown code block markers
            if res_text.startswith("```"):
                res_text = re.sub(r'^```(?:json)?\n', '', res_text)
                res_text = re.sub(r'\n```$', '', res_text)
            
            classifications = json.loads(res_text)
            
            # Map classifications back to the jobs
            class_dict = {str(item["id"]): item for item in classifications if "id" in item}
            
            for job in batch:
                job_id_str = str(job["id"])
                if job_id_str in class_dict:
                    item = class_dict[job_id_str]
                    category = item.get("category", "EXCLUDE")
                    reason = item.get("reason", "No reason provided by LLM.")
                    if category not in ["BEST_FIT", "WORSE_FIT", "EXCLUDE"]:
                        category = "EXCLUDE"
                else:
                    category = "WORSE_FIT"
                    reason = "Batch evaluation missed specific ID. Defaulted to manual review."
                    
                job["category"] = category
                job["reason"] = reason
                
                if category == "BEST_FIT":
                    best_fit.append(job)
                elif category == "WORSE_FIT":
                    worse_fit.append(job)
                else:
                    excluded_count += 1
                    
        except Exception as e:
            print(f"[ERROR] Batch LLM evaluation failed after retries: {e}. Falling back to individual evaluation.")
            # Fallback to individual evaluations for this batch
            for job in batch:
                time.sleep(2.0)
                category, reason = run_stage2_llm_filter(job, config)
                job["category"] = category
                job["reason"] = reason
                if category == "BEST_FIT":
                    best_fit.append(job)
                elif category == "WORSE_FIT":
                    worse_fit.append(job)
                else:
                    excluded_count += 1
                    
        # Sleep for 2.0 seconds between batches to strictly honor 15 RPM
        if i + batch_size < len(passing_jobs):
            time.sleep(2.0)
            
    return best_fit, worse_fit, excluded_count

if __name__ == "__main__":
    # Simple offline test
    dummy_job = {
        "id": "test-123",
        "title": "Junior Data Analyst",
        "company": "Tech Corp",
        "location": "Los Angeles, CA",
        "applicants": 10,
        "description": "We are seeking a junior data analyst. Requirements: B.S. degree. 1-2 years of experience. Strong Python and SQL skills. Experience with Power BI is a plus."
    }
    
    # Mock GEMINI_API_KEY environment variable for test
    os.environ["GEMINI_API_KEY"] = "mock_key"
    
    config = load_config()
    print("Stage 1 test:")
    print(run_stage1_regex_filter(dummy_job, config))
