import os
import re
import sys
from typing import List, Dict, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.db.db import init_db, upsert_company, get_company
from src.agents.company_scorer import calculate_strategic_company_score

# Common tech keywords to extract concisely (top 3-5)
TECH_KEYWORDS = [
    "Python", "SQL", "PostgreSQL", "PyTorch", "TensorFlow", "Scikit-Learn",
    "Spark", "Databricks", "AWS", "GCP", "Azure", "Snowflake", "dbt",
    "Docker", "Kubernetes", "C++", "R", "Tableau", "Power BI", "Kafka",
    "FastAPI", "React", "Next.js", "Git", "XGBoost"
]

def clean_company_name(name: str) -> str:
    """Clean company name by stripping legal suffixes."""
    if not name:
        return ""
    cleaned = re.sub(r'(?i)\b(inc|llc|corp|ltd|co|corporation|technologies|solutions|group|holdings)\b\.?', '', name)
    return cleaned.strip().strip(",.-")

def resolve_company_domain(company_name: str) -> str:
    """
    Generate or resolve a standardized domain for the company.
    """
    cleaned = clean_company_name(company_name).lower()
    slug = re.sub(r'[^a-z0-9\-]', '', cleaned.replace(' ', ''))
    if not slug:
        slug = "unknown"
    return f"{slug}.com"

def extract_concise_tech_stack(description: str, limit: int = 5) -> str:
    """Extract top 3-5 tech keywords mentioned in job description."""
    if not description:
        return ""
    found = []
    desc_lower = description.lower()
    for kw in TECH_KEYWORDS:
        pattern = r'\b' + re.escape(kw.lower()) + r'\b'
        if re.search(pattern, desc_lower):
            found.append(kw)
            if len(found) >= limit:
                break
    return ", ".join(found) if found else ""

def parse_applicant_count(raw_val) -> int:
    """Parse integer applicant count."""
    if isinstance(raw_val, int):
        return raw_val
    if not raw_val:
        return 0
    matches = re.findall(r'\d+', str(raw_val).replace(',', ''))
    return int(matches[0]) if matches else 0

def ingest_scraped_jobs(jobs: List[Dict]) -> Dict:
    """
    Ingest a list of scraped jobs into the companies table with Two-Track intelligence:
    - Track 1: Active job with < 80 applicants (High Urgency -> Priority Tier 1).
    - Track 2: Strategic scoring (Location 30 pts, Industry 45 pts, Size 15 pts, Tech 10 pts).
    """
    if not jobs:
        print("[Ingest] No jobs provided to ingest.")
        return {"total_companies": 0, "track_1": 0, "track_2": 0}

    init_db()
    
    companies_map: Dict[str, Dict] = {}
    for job in jobs:
        comp_name = job.get("company", "").strip()
        if not comp_name:
            continue
            
        apps = parse_applicant_count(job.get("applicants", 0))
        location = job.get("location", "Los Angeles, CA")
        job_link = job.get("link", "")
        desc = job.get("description", "")
        category = job.get("category", "EXCLUDE")
        
        # Track 1 condition: < 80 applicants
        is_track_1 = (apps > 0 and apps < 80) or (category == "BEST_FIT" and apps < 80)

        if comp_name not in companies_map:
            companies_map[comp_name] = {
                "company_name": comp_name,
                "is_track_1": is_track_1,
                "min_applicants": apps if apps > 0 else 999,
                "location": location,
                "job_link": job_link,
                "descriptions": [desc] if desc else []
            }
        else:
            if is_track_1:
                companies_map[comp_name]["is_track_1"] = True
            if apps > 0 and apps < companies_map[comp_name]["min_applicants"]:
                companies_map[comp_name]["min_applicants"] = apps
            if job_link and not companies_map[comp_name]["job_link"]:
                companies_map[comp_name]["job_link"] = job_link
            if desc:
                companies_map[comp_name]["descriptions"].append(desc)

    track_1_count = 0
    track_2_count = 0

    for comp_name, info in companies_map.items():
        domain = resolve_company_domain(comp_name)
        all_desc = " ".join(info["descriptions"])
        tech_stack = extract_concise_tech_stack(all_desc, limit=4)
        
        # Determine Track
        tier = 1 if info["is_track_1"] else 2
        track = "TRACK_1" if info["is_track_1"] else "TRACK_2"
        min_apps = info["min_applicants"] if info["min_applicants"] < 999 else None

        # Calculate Strategic Company Score for Track 2 evaluation
        score_res = calculate_strategic_company_score(
            company_name=comp_name,
            location=info["location"],
            description_or_industry=all_desc,
            employee_count=None,
            tech_stack=tech_stack
        )
        strat_score = score_res["strategic_score"]

        upsert_company(
            domain=domain,
            company_name=comp_name,
            priority_tier=tier,
            track=track,
            applicant_count=min_apps,
            location=info["location"],
            strategic_score=strat_score,
            employee_count=None,
            industry=None,
            job_source_url=info["job_link"],
            tech_stack=tech_stack if tech_stack else None,
            key_news=None
        )
        
        if tier == 1:
            track_1_count += 1
        else:
            track_2_count += 1

    print(f"\n[SideDoor Ingest] Successfully ingested {len(companies_map)} companies:")
    print(f"  - Track 1 (Active <80 Applicants): {track_1_count}")
    print(f"  - Track 2 (Strategic Scoring Candidates): {track_2_count}")

    return {
        "total_companies": len(companies_map),
        "track_1": track_1_count,
        "track_2": track_2_count
    }

if __name__ == "__main__":
    test_jobs = [
        {
            "company": "Scale AI",
            "title": "Data Scientist",
            "link": "https://linkedin.com/jobs/view/123",
            "applicants": 42, # < 80 -> Track 1
            "location": "Los Angeles, CA",
            "category": "BEST_FIT",
            "description": "Looking for Python, SQL, and PyTorch experience."
        },
        {
            "company": "Rippling",
            "title": "Data Engineer",
            "link": "https://linkedin.com/jobs/view/456",
            "applicants": 120, # >= 80 -> Track 2 Strategic
            "location": "San Francisco, CA (Remote)",
            "category": "WORSE_FIT",
            "description": "Experience with Snowflake, Spark, and AWS required in data infrastructure."
        }
    ]
    ingest_scraped_jobs(test_jobs)
