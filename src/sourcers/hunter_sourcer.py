import os
import re
import urllib.parse
import requests
from typing import List, Dict, Optional
from pydantic import BaseModel, Field

from ..config import HUNTER_API_KEY

class HunterCandidate(BaseModel):
    full_name: str
    title: str
    linkedin_url: str
    synthesized_email: str
    email_status: str = Field(default="VERIFIED", description="'VERIFIED', 'PATTERN_GENERATED', or 'INVALID'")
    classification: str = Field(description="'Hiring Manager' or 'Young Professional'")
    relevance_score: int = Field(default=80, description="0 to 100")
    ai_hook: Optional[str] = Field(default=None)

class HunterSourcingResult(BaseModel):
    candidates: List[HunterCandidate]

def get_hunter_domain_pattern(domain: str, api_key: Optional[str] = None) -> str:
    """
    Query Hunter.io Domain Search API to detect the corporate email pattern.
    Returns pattern string such as '{first}.{last}', '{first}', or '{f}{last}'.
    """
    key = api_key or HUNTER_API_KEY
    if not key:
        try:
            from ..db.db import get_active_profile
            active_prof = get_active_profile()
            if active_prof:
                key = active_prof.get("hunter_api_key")
        except Exception:
            pass

    if key:
        try:
            url = f"https://api.hunter.io/v2/domain-search?domain={domain}&api_key={key}"
            res = requests.get(url, timeout=8)
            if res.status_code == 200:
                data = res.json()
                pattern = data.get("data", {}).get("pattern")
                if pattern:
                    return pattern
        except Exception as e:
            print(f"[Hunter.io] Pattern notice for {domain}: {e}")

    return "{first}.{last}"

def synthesize_email(full_name: str, domain: str, pattern: str) -> str:
    """
    Synthesize a work email address from a person's real name, company domain, and Hunter pattern.
    """
    parts = re.sub(r'[^a-zA-Z\s]', '', full_name).strip().lower().split()
    if not parts:
        return f"contact@{domain}"
    
    first = parts[0]
    last = parts[-1] if len(parts) > 1 else ""
    f = first[0] if first else ""
    l = last[0] if last else ""

    if not last:
        return f"{first}@{domain}"

    if pattern == "{first}.{last}":
        return f"{first}.{last}@{domain}"
    elif pattern == "{first}":
        return f"{first}@{domain}"
    elif pattern == "{f}{last}":
        return f"{f}{last}@{domain}"
    elif pattern == "{f}.{last}":
        return f"{f}.{last}@{domain}"
    elif pattern == "{first}_{last}":
        return f"{first}_{last}@{domain}"
    elif pattern == "{first}{l}":
        return f"{first}{l}@{domain}"
    elif pattern == "{first}.{l}":
        return f"{first}.{l}@{domain}"
    elif pattern == "{last}.{first}":
        return f"{last}.{first}@{domain}"
    elif pattern == "{last}":
        return f"{last}@{domain}"
    else:
        return f"{first}.{last}@{domain}"

def source_hunter_candidates(
    company_name: str,
    domain: str,
    count: int = 10,
    target_roles: Optional[str] = None,
    api_key: Optional[str] = None,
    profile: Optional[Dict] = None
) -> List[HunterCandidate]:
    """
    Source real prospective contacts from Hunter.io Domain Search.
    Extracts real names, job titles, verified corporate emails, and genuine LinkedIn URLs.
    Dynamically aligns scoring and credentials to the active user profile.
    """
    # 1. Resolve API key
    key = api_key or HUNTER_API_KEY
    if not key:
        if profile and profile.get("hunter_api_key"):
            key = profile.get("hunter_api_key")
        else:
            try:
                from ..db.db import get_active_profile
                active_prof = get_active_profile()
                if active_prof:
                    key = active_prof.get("hunter_api_key")
            except Exception:
                pass

    if not key:
        print("[Hunter.io] HUNTER_API_KEY is not configured in .env or active profile.")
        return []

    # 2. Resolve target roles for relevance scoring
    if not target_roles:
        if profile and profile.get("target_roles"):
            target_roles = profile.get("target_roles")
        else:
            try:
                from ..db.db import get_active_profile
                active_prof = get_active_profile()
                if active_prof:
                    target_roles = active_prof.get("target_roles")
            except Exception:
                pass

    role_tokens = set()
    if target_roles:
        for r in re.split(r'[,;]+', target_roles):
            for w in r.strip().lower().split():
                if len(w) > 2 and w not in ["and", "the", "for", "with", "lead", "manager", "director"]:
                    role_tokens.add(w)

    if not role_tokens:
        role_tokens = {"data", "machine learning", "ml", "ai", "engineer", "software", "analytics"}

    url = "https://api.hunter.io/v2/domain-search"
    params = {
        "domain": domain,
        "api_key": key,
        "limit": count
    }

    try:
        print(f"[Hunter.io] Querying domain search for '{company_name}' ({domain}) [limit={count}]...")
        res = requests.get(url, params=params, timeout=10)
        if res.status_code != 200:
            print(f"[Hunter.io] API returned status {res.status_code}: {res.text[:200]}")
            return []

        data = res.json().get("data", {})
        emails_list = data.get("emails", [])
        if not emails_list:
            print(f"[Hunter.io] No indexed emails/contacts found for domain: {domain}")
            return []

        candidates: List[HunterCandidate] = []
        seen_names = set()

        for item in emails_list:
            first_name = (item.get("first_name") or "").strip()
            last_name = (item.get("last_name") or "").strip()
            full_name = f"{first_name} {last_name}".strip()

            # Skip entries without a real human name
            if not full_name or len(full_name.split()) < 2:
                continue

            if full_name.lower() in seen_names:
                continue
            seen_names.add(full_name.lower())

            title = item.get("position") or "Team Member"
            email_val = item.get("value")
            direct_linkedin = item.get("linkedin")

            # If direct LinkedIn URL is missing, provide a Google X-Ray search query rather than a fake slug
            if direct_linkedin and "linkedin.com/in/" in direct_linkedin:
                linkedin_url = direct_linkedin
            else:
                encoded_q = urllib.parse.quote_plus(f'site:linkedin.com/in/ "{full_name}" "{company_name}"')
                linkedin_url = f"https://www.google.com/search?q={encoded_q}"

            # Classification
            t_lower = title.lower()
            seniority = (item.get("seniority") or "").lower()
            is_hm = (
                any(k in t_lower for k in [
                    "director", "vp", "president", "head", "manager", "lead",
                    "recruiter", "talent", "chief", "founder", "officer"
                ])
                or seniority in ["executive", "senior"]
            )
            classification = "Hiring Manager" if is_hm else "Young Professional"

            # Relevance Scoring aligned with user's target roles
            matched_target_role = any(k in t_lower for k in role_tokens)
            if matched_target_role:
                relevance = 95 if is_hm else 90
            elif any(k in t_lower for k in ["recruiter", "talent", "hiring", "people"]):
                relevance = 90
            elif is_hm:
                relevance = 85
            else:
                relevance = 80

            ai_hook = f"Leading initiatives as {title} at {company_name}" if is_hm else f"Work as {title} at {company_name}"

            pattern = data.get("pattern") or "{first}.{last}"
            candidates.append(HunterCandidate(
                full_name=full_name,
                title=title,
                linkedin_url=linkedin_url,
                synthesized_email=email_val or synthesize_email(full_name, domain, pattern),
                email_status="VERIFIED" if email_val else "PATTERN_GENERATED",
                classification=classification,
                relevance_score=relevance,
                ai_hook=ai_hook
            ))

        # Sort candidates by relevance score descending
        candidates.sort(key=lambda x: x.relevance_score, reverse=True)
        print(f"[Hunter.io] Successfully sourced {len(candidates)} real prospective contacts for {domain}.")
        return candidates[:count]

    except Exception as e:
        print(f"[Hunter.io] Exception querying domain search: {e}")
        return []

