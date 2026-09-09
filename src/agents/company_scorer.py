#visit this file to change how companies are scored adding or removing preferences or adjusting weights. 
import re
from typing import Dict, Optional, Tuple

# Strategic Scoring Weights:
# - Location (LA / Remote): 30 pts
# - Industry & Domain: 45 pts
# - Company Size: 15 pts
# - Tech Stack Alignment: 10 pts
# Total: 100 pts
#
#keywords in job description for scoring
LA_KEYWORDS = ["los angeles", "la", "santa monica", "culver city", "venice", "playa vista", "el segundo", "pasadena", "irvine", "burbank", "southern california", "ca", "remote", "united states (remote)"]
#SF_KEYWORDS = ["san francisco", "bay area", "palo alto", "mountain view", "sunnyvale", "san jose", "california"]

#domains close to job im looking for
HIGH_ALIGNMENT_DOMAINS = [
    "artificial intelligence", "machine learning", "data infrastructure", "deep learning",
    "scientific computing", "predictive analytics", "generative ai", "computer vision",
    "natural language processing", "llm", "ai platform", "analytics", "data platform"
]

MEDIUM_ALIGNMENT_DOMAINS = [
    "fintech", "financial services", "healthtech", "biotech", "saas", "b2b software",
    "cloud computing", "cybersecurity", "e-commerce", "edtech", "climate tech"
]
#adds score based on locations
def score_location(location: Optional[str], target_locations: Optional[str] = None) -> Tuple[int, str]:
    """Score location (Max 30 pts). Adapts to user profile target locations, prioritizing Remote."""
    if not location:
        return 15, "Location unspecified (+15 pts)"
    
    loc_lower = location.lower()
    if "remote" in loc_lower:
        return 30, "Remote flexibility (+30 pts)"

    if target_locations:
        # User defined locations (e.g. "Austin, TX; Seattle, WA; Remote")
        target_list = [t.strip().lower() for t in re.split(r'[,;]+', target_locations) if t.strip()]
        for t in target_list:
            if t == "remote":
                continue
            # Match city name or state token
            parts = [p for p in re.split(r'[\s,]+', t) if len(p) > 2]
            if t in loc_lower or (parts and all(p in loc_lower for p in parts)):
                return 30, f"Target Location Match ({t.title()}) (+30 pts)"
        return 10, "Outside primary target locations (+10 pts)"
    else:
        # Default fallback to LA area
        if any(k in loc_lower for k in LA_KEYWORDS):
            return 30, "Greater Los Angeles or Remote (+30 pts)"
        else:
            return 10, "Other US / Global (+10 pts)"

#score for industry
def score_industry_domain(description_or_industry: Optional[str], company_name: str, target_roles: Optional[str] = None) -> Tuple[int, str]:
    """Score industry and core mission (Max 45 pts). Adapts to target roles or high alignment sectors."""
    text = f"{company_name} {description_or_industry or ''}".lower()
    
    if target_roles:
        roles_list = [r.strip().lower() for r in re.split(r'[,;]+', target_roles) if r.strip()]
        role_keywords = set()
        for r in roles_list:
            role_keywords.add(r)
            for w in r.split():
                if len(w) > 2 and w not in ["and", "the", "for", "with", "engineer", "manager", "lead"]:
                    role_keywords.add(w)

        matches = [k for k in role_keywords if k in text]
        if len(matches) >= 2 or any(r in text for r in roles_list):
            matched_term = matches[0] if matches else roles_list[0]
            return 45, f"High Alignment with Target Roles ({matched_term.title()}) (+45 pts)"
        elif len(matches) == 1:
            return 35, f"Moderate Alignment with Target Roles ({matches[0].title()}) (+35 pts)"
        elif any(k in text for k in HIGH_ALIGNMENT_DOMAINS + MEDIUM_ALIGNMENT_DOMAINS):
            return 25, "Related Technology Sector (+25 pts)"
        else:
            return 15, "General Industry / Business (+15 pts)"
    else:
        if any(k in text for k in HIGH_ALIGNMENT_DOMAINS):
            return 45, "High Alignment Domain (AI / ML / Data Infrastructure) (+45 pts)"
        elif any(k in text for k in MEDIUM_ALIGNMENT_DOMAINS):
            return 30, "Target Sector (Fintech / SaaS / HealthTech) (+30 pts)"
        else:
            return 15, "General Technology / Business (+15 pts)"

#score for company size.
def score_company_size(employee_count: Optional[int]) -> Tuple[int, str]:
    """Score company size (Max 15 pts). Sweet spot: 50-500 employees."""
    if not employee_count:
        return 10, "Size unknown (Default +10 pts)"
    
    if 50 <= employee_count <= 500:
        return 15, "Sweet Spot Scaleup (50-500 employees) (+15 pts)"
    elif 500 < employee_count <= 2000:
        return 12, "Mid-size Tech (500-2,000 employees) (+12 pts)"
    elif employee_count > 2000:
        return 10, "Enterprise (2,000+ employees) (+10 pts)"
    else:
        return 8, "Early Stage (<50 employees) (+8 pts)"

#score based on tech stack.
def score_tech_stack(tech_stack: Optional[str], skills: Optional[str] = None) -> Tuple[int, str]:
    """Score tech stack alignment (Max 10 pts). Adapts to user's profile skills."""
    if not tech_stack:
        return 5, "Tech stack not detected (+5 pts)"
    
    tech_lower = tech_stack.lower()
    
    if skills:
        user_skills = [s.strip().lower() for s in re.split(r'[,;]+', skills) if s.strip()]
        matches = [s for s in user_skills if s in tech_lower]
        if len(matches) >= 2:
            return 10, f"Strong Skill Alignment: {', '.join(matches[:3])} (+10 pts)"
        elif len(matches) == 1:
            return 7, f"Moderate Skill Alignment: {matches[0]} (+7 pts)"
        else:
            return 4, "General Tech Stack (+4 pts)"
    else:
        core_skills = ["python", "pytorch", "sql", "xgboost", "postgres", "spark", "pandas"]
        matches = [s for s in core_skills if s in tech_lower]
        
        if len(matches) >= 2:
            return 10, f"Strong Stack Alignment: {', '.join(matches)} (+10 pts)"
        elif len(matches) == 1:
            return 7, f"Moderate Stack Alignment: {matches[0]} (+7 pts)"
        else:
            return 4, "General Tech Stack (+4 pts)"

#calls all functions for a given company, found in db, and returns total and score breakdown and reasons for each.
def calculate_strategic_company_score(
    company_name: str,
    location: Optional[str] = None,
    description_or_industry: Optional[str] = None,
    employee_count: Optional[int] = None,
    tech_stack: Optional[str] = None,
    profile: Optional[Dict] = None
) -> Dict:
    """
    Calculate the 100-point Strategic Company Score for Track 2.
    Formula: Location (30) + Industry (45) + Size (15) + Tech Stack (10)
    Dynamically adapts to target profile if provided or active.
    """
    if not profile:
        try:
            from ..db.db import get_local_profile
            profile = get_local_profile()
        except Exception:
            profile = None

    target_locs = profile.get("target_locations") if profile else None
    target_roles = profile.get("target_roles") if profile else None
    skills = profile.get("skills") if profile else None

    # Check both tech stack and description against user's skills
    tech_content = f"{tech_stack or ''} {description_or_industry or ''}".strip() if description_or_industry else (tech_stack or "")

    loc_score, loc_reason = score_location(location, target_locations=target_locs)
    ind_score, ind_reason = score_industry_domain(description_or_industry, company_name, target_roles=target_roles)
    size_score, size_reason = score_company_size(employee_count)
    tech_score, tech_reason = score_tech_stack(tech_content, skills=skills)

    total = loc_score + ind_score + size_score + tech_score

    return {
        "strategic_score": total,
        "breakdown": {
            "location_pts": loc_score,
            "industry_pts": ind_score,
            "size_pts": size_score,
            "tech_stack_pts": tech_score
        },
        "reasons": [loc_reason, ind_reason, size_reason, tech_reason]
    }
