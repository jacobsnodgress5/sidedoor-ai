import os
import sys
from typing import List, Dict, Optional

# Ensure project root is in path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.db import ( #importing sql functions from db file
    init_db,
    get_company,
    save_company,
    get_contacts,
    get_contact,
    save_contact,
    get_outreach,
    log_outreach
)
from src.agents.company_profiler import profile_company #imports profile function company which uses gemini
from src.agents.contact_sourcer import source_contacts #imports contact info sourcing function, uses gemini 
from src.agents.copywriter import generate_outreach_drafts #cody for providing context to gemini so it can generate person specific outreach messages

#function to do basically all of the backend work. company profiling, contact sourcing, and message generation
def process_company(domain: str, company_hint: Optional[str] = None) -> Dict:
    """
    Execute profiling, contact sourcing, and copywriting for a single company domain.
    Utilizes caching to avoid duplicate search engine/API queries and duplicate outreach drafting.
    """
    print(f"\n==========================================")
    print(f"Processing company domain: {domain}")
    print(f"==========================================")

    # 1. Company Profiling (with cache lookup)
    company_info = get_company(domain)
    if company_info:
        print(f"-> [CACHE HIT] Found cached profile for '{company_info['company_name']}'")
    else:
        print(f"-> [CACHE MISS] Profiling company domain '{domain}' via Gemini...")
        profile = profile_company(domain, company_hint)
        # Store in DB
        save_company(
            domain=domain,
            company_name=profile.company_name,
            funding_stage=profile.funding_stage,
            employee_count=profile.employee_count,
            tech_stack=", ".join(profile.tech_stack),
            key_news=profile.key_news
        )
        company_info = get_company(domain)
        print(f"-> [SUCCESS] Saved company profile: {company_info['company_name']}")

    # 2. Sourcing Contacts (with cache check)
    print(f"-> Sourcing contacts for {company_info['company_name']}...")
    contacts = get_contacts(domain)
    
    if not contacts:
        print("-> [CACHE MISS] No cached contacts found. Sourcing new contacts...")
        sourced = source_contacts(domain, company_info['company_name'])
        for c in sourced:
            # Save to cache
            save_contact(
                linkedin_url=c.linkedin_url,
                company_domain=domain,
                full_name=c.full_name,
                title=c.title,
                classification=c.classification,
                profile_data={"experience_summary": c.experience_summary},
                relevance_score=c.relevance_score,
                ai_hook=c.ai_hook
            )
        contacts = get_contacts(domain)
    else:
        print(f"-> [CACHE HIT] Found {len(contacts)} cached contacts.")

    # 3. Generating Outreach Drafts for Sourced Contacts
    results = []
    for contact in contacts:
        linkedin_url = contact['linkedin_url']
        print(f"\n   Checking outreach status for {contact['full_name']} ({contact['title']})...")
        
        outreach = get_outreach(linkedin_url)
        if outreach:
            print(f"   -> [PREVENT DOUBLE-CONTACT] Outreach draft already exists in log (Status: {outreach['status']}). Skipping drafting.")
            draft_content = outreach['draft_used']
        else:
            print(f"   -> [DRAFTING] Generating personalized networking drafts...")
            drafts = generate_outreach_drafts(
                contact_name=contact['full_name'],
                contact_title=contact['title'],
                contact_classification=contact['classification'],
                ai_hook=contact['ai_hook'],
                company_name=company_info['company_name']
            )
            
            # Combine drafts into a text layout for saving
            draft_content = f"LINKEDIN NOTE:\n{drafts.linkedin_connect_request}\n\nEMAIL NOTE:\n{drafts.email_or_inmail_message}"
            
            # Save to outreach log
            log_outreach(
                linkedin_url=linkedin_url,
                draft_used=draft_content,
                channel="LinkedIn Connect / Email",
                status="Drafted"
            )
            print(f"   -> [SUCCESS] Saved outreach draft for {contact['full_name']}")

        results.append({
            "contact": contact,
            "drafts": draft_content
        })

    return {
        "company": company_info,
        "results": results
    }

#runs the process company function for a list of domains
def run_pipeline(domains: List[str]):
    """Run the pipeline coordinator for a list of company domains."""
    print("Initializing SideDoor AI caching database...")
    init_db()
    
    all_results = []
    for domain in domains:
        try:
            res = process_company(domain)
            all_results.append(res)
        except Exception as e:
            print(f"Error processing {domain}: {e}")
            
    print("\n==========================================")
    print("Pipeline Execution Summary:")
    print("==========================================")
    for idx, r in enumerate(all_results):
        company = r["company"]
        print(f"\n{idx+1}. Company: {company['company_name']} ({company['domain']})")
        print(f"   Funding: {company['funding_stage']} | Employees: {company['employee_count']}")
        print(f"   Tech Stack: {company['tech_stack']}")
        print(f"   Sourced Contacts:")
        for res in r["results"]:
            c = res["contact"]
            print(f"   - {c['full_name']} ({c['title']}) - Class: {c['classification']} (Relevance: {c['relevance_score']})")
            print(f"     LinkedIn: {c['linkedin_url']}")
            print(f"     Icebreaker Hook: {c['ai_hook']}")
            print(f"     --- Generated Drafts ---")
            print(res["drafts"])
            print(f"     ------------------------")

if __name__ == "__main__":
    # If run directly, run with standard search test targets
    test_domains = ["vercel.com", "replicate.com"]
    run_pipeline(test_domains)
