import os
import sys
import time
import concurrent.futures
from typing import List, Dict, Optional

# Ensure project root in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.config import DAILY_MESSAGE_CAP, MAX_HUNTER_CREDITS_PER_DAY
from src.db.db import (
    init_db,
    get_all_companies,
    get_track_1_companies,
    get_track_2_companies,
    get_contacts_by_company,
    upsert_contact,
    get_db_connection,
    record_api_usage,
    get_daily_api_usage,
    get_active_profile,
    get_profile_by_id,
    get_sourcing_settings,
    get_selected_companies_for_sourcing
)
from src.sourcers.hunter_sourcer import (
    source_hunter_candidates,
    HunterCandidate
)
from src.agents.copywriter import generate_personalized_copy

def _process_single_outreach(task: Dict) -> Dict:
    """Worker function to generate copy and upsert a contact with rate pacing."""
    cand = task["candidate"]
    channel = task["channel"]
    is_track_1 = task["is_track_1"]
    comp_name = task["company_name"]
    domain = task["domain"]
    tech_stack = task.get("tech_stack")
    target_class = task["target_class"]
    email = task.get("email")
    profile = task.get("profile")
    profile_id = task.get("profile_id", 1)

    target_roles = (profile.get("target_roles") if profile else None) or "Technology Professional"
    primary_role = target_roles.split(",")[0].strip() if target_roles else "Role"

    copy = generate_personalized_copy(
        contact_name=cand.full_name,
        contact_title=cand.title,
        contact_classification=target_class,
        company_name=comp_name,
        job_applied=is_track_1,
        job_title=primary_role if is_track_1 else None,
        ai_hook=cand.ai_hook,
        channel_preference=channel,
        tech_stack=tech_stack,
        profile=profile
    )

    upsert_contact(
        linkedin_url=cand.linkedin_url,
        company_domain=domain,
        full_name=cand.full_name,
        title=cand.title,
        email=email,
        classification=target_class,
        relevance_score=cand.relevance_score,
        ai_hook=cand.ai_hook,
        draft_email=copy.draft_email,
        draft_linkedin=copy.draft_linkedin,
        outreach_status="DRAFTED",
        profile_id=profile_id
    )

    if channel == "EMAIL" and email:
        print(f"  -> [Hunter Email Draft] {cand.full_name} ({cand.title}) | {email}")
    else:
        print(f"  -> [LinkedIn Note Draft] {cand.full_name} ({comp_name}) [{len(copy.draft_linkedin or '')} chars]")

    return {
        "source": "Hunter",
        "candidate": cand,
        "email": email,
        "draft_email": copy.draft_email,
        "draft_linkedin": copy.draft_linkedin,
        "is_backup": False
    }

def run_daily_allocation(
    daily_cap: int = DAILY_MESSAGE_CAP,
    companies_per_day: Optional[int] = None,
    contacts_per_company: int = 10,
    profile_id: Optional[int] = None
) -> Dict:
    """
    Execute Hunter-Driven Daily Prospecting with Safety Controls:
    - Hard daily credit stopper: Respects configured daily_hunter_limit (default: 2/day).
    - Mode aware:
        - MANUAL (default): Only sources contacts for companies explicitly selected in Daily Jobs.
        - AUTO: Prioritizes Track 1 (active <80 applicants) and Track 2 strategic scoring.
    - Daily batch hold: If the daily cap was already reached today, holds existing review cards without re-querying.
    - Scoped to active profile/campaign and conserves Hunter's credits.
    """
    init_db()

    active_profile = get_profile_by_id(profile_id) if profile_id else get_active_profile()
    prof_id = active_profile["id"] if active_profile else 1
    prof_name = active_profile.get("profile_name") or active_profile.get("full_name") if active_profile else "Default"

    # Fetch sourcing settings & daily limit
    sourcing_settings = get_sourcing_settings(prof_id)
    sourcing_mode = sourcing_settings.get("sourcing_mode", "MANUAL")
    daily_hunter_limit = sourcing_settings.get("daily_hunter_limit") or MAX_HUNTER_CREDITS_PER_DAY
    effective_companies_limit = companies_per_day if companies_per_day is not None else daily_hunter_limit

    print("=" * 70)
    print(f"SIDEDOOR AI: PROSPECTING ENGINE [{prof_name}] (Mode: {sourcing_mode}, Cap: {daily_cap}, Daily Hunter Limit: {daily_hunter_limit})")
    print("=" * 70)

    # 1. Daily Credit & Batch Hold Check
    today_hunter_usage = get_daily_api_usage("HUNTER")
    print(f"[Daily Credit Monitor] Hunter searches used today: {today_hunter_usage} / {daily_hunter_limit} allowed")

    conn = get_db_connection()
    existing_drafts = conn.execute(
        "SELECT * FROM contacts WHERE outreach_status = 'DRAFTED' AND profile_id = ? ORDER BY created_at DESC",
        (prof_id,)
    ).fetchall()
    conn.close()

    # If daily credit cap is already reached, activate safety hold
    if today_hunter_usage >= daily_hunter_limit:
        print(f"\n[DAILY SAFETY LOCK ACTIVATED] Daily limit of {daily_hunter_limit} Hunter searches reached for today.")
        if existing_drafts:
            print(f"[HOLDING BATCH] Preserving today's {len(existing_drafts)} review cards (0 additional Hunter credits spent).")
            return {
                "status": "DAILY_LIMIT_HOLD",
                "message": f"Daily limit of {daily_hunter_limit} Hunter searches reached. Holding today's {len(existing_drafts)} prospects.",
                "hunter": [dict(r) for r in existing_drafts],
                "total_drafted": len(existing_drafts),
                "companies": list(set(r["company_domain"] for r in existing_drafts)),
                "today_credits_used": today_hunter_usage,
                "daily_credit_limit": daily_hunter_limit,
                "sourcing_mode": sourcing_mode
            }
        else:
            print("[NOTICE] No pending drafts found in cache. Daily search quota will reset tomorrow.")
            return {
                "status": "DAILY_LIMIT_REACHED",
                "message": f"Daily limit of {daily_hunter_limit} Hunter searches reached for today. Resets tomorrow.",
                "hunter": [],
                "total_drafted": 0,
                "companies": [],
                "today_credits_used": today_hunter_usage,
                "daily_credit_limit": daily_hunter_limit,
                "sourcing_mode": sourcing_mode
            }

    # 2. Select companies based on Sourcing Mode (MANUAL vs AUTO)
    ordered_companies = []
    if sourcing_mode == "MANUAL":
        selected_comps = get_selected_companies_for_sourcing(prof_id)
        if not selected_comps:
            print("\n[Manual Sourcing Notice] No companies currently selected for sourcing.")
            return {
                "status": "NO_COMPANIES_SELECTED",
                "message": "Manual selection mode is active, but you haven't selected any companies yet. Please select the companies you want to source on the Daily Jobs page or switch to Automatic mode in Settings.",
                "hunter": [dict(r) for r in existing_drafts] if existing_drafts else [],
                "total_drafted": len(existing_drafts) if existing_drafts else 0,
                "companies": [],
                "today_credits_used": today_hunter_usage,
                "daily_credit_limit": daily_hunter_limit,
                "sourcing_mode": "MANUAL"
            }
        ordered_companies = selected_comps
        print(f"[Manual Sourcing] Sourcing from {len(ordered_companies)} user-selected companies (Limit: {effective_companies_limit}).")
    else:
        track_1_comps = get_track_1_companies()
        track_2_comps = get_track_2_companies()
        all_comps = get_all_companies()

        if not all_comps:
            print("[Allocation] No companies found in database. Ingest companies first.")
            return {
                "status": "NO_COMPANIES_IN_DB",
                "message": "No companies found in database. Please run the job scraper first.",
                "hunter": [],
                "total_drafted": 0,
                "companies": [],
                "today_credits_used": today_hunter_usage,
                "daily_credit_limit": daily_hunter_limit,
                "sourcing_mode": sourcing_mode
            }

        print(f"[Auto Allocation] Total companies in DB: {len(all_comps)}")
        print(f"  - Track 1 (Active <80 Apps): {len(track_1_comps)}")
        print(f"  - Track 2 (Strategic Scored): {len(track_2_comps)}")

        # Priority pool: Track 1 companies first, then top-scored Track 2 companies
        seen_domains = set()
        for c in track_1_comps + track_2_comps:
            if c["domain"] not in seen_domains:
                ordered_companies.append(c)
                seen_domains.add(c["domain"])

    target_companies = []
    tasks = []
    hunter_results = []

    for comp in ordered_companies:
        domain = comp["domain"]
        comp_name = comp["company_name"]
        is_track_1 = (comp.get("priority_tier") == 1 or comp.get("track") == "TRACK_1")

        # 1. Check database cache to avoid redundant Hunter API credits
        cached_contacts = get_contacts_by_company(domain, profile_id=prof_id)
        candidates = []

        if cached_contacts:
            print(f"\n-> [CACHE HIT] Using {len(cached_contacts)} cached contacts for {comp_name} ({domain}) [0 Hunter credits spent]")
            # If all contacts already have drafted copy, reuse them directly without extra Gemini calls
            already_drafted = all(bool(c.get("draft_email") or c.get("draft_linkedin")) for c in cached_contacts)
            if already_drafted:
                for c in cached_contacts[:contacts_per_company]:
                    cand_obj = HunterCandidate(
                        full_name=c["full_name"],
                        title=c["title"],
                        linkedin_url=c["linkedin_url"],
                        synthesized_email=c["email"] or "",
                        email_status="VERIFIED" if c["email"] else "PATTERN_GENERATED",
                        classification=c["classification"] or "Young Professional",
                        relevance_score=c["relevance_score"] or 80,
                        ai_hook=c["ai_hook"]
                    )
                    hunter_results.append({
                        "source": "Hunter (Cached)",
                        "candidate": cand_obj,
                        "email": c["email"],
                        "draft_email": c["draft_email"],
                        "draft_linkedin": c["draft_linkedin"],
                        "is_backup": False
                    })
                target_companies.append(comp)
                if len(target_companies) >= effective_companies_limit:
                    break
                continue

            candidates = [
                HunterCandidate(
                    full_name=c["full_name"],
                    title=c["title"],
                    linkedin_url=c["linkedin_url"],
                    synthesized_email=c["email"] or "",
                    email_status="VERIFIED" if c["email"] else "PATTERN_GENERATED",
                    classification=c["classification"] or "Young Professional",
                    relevance_score=c["relevance_score"] or 80,
                    ai_hook=c["ai_hook"]
                )
                for c in cached_contacts[:contacts_per_company]
            ]
        else:
            # Check hard credit stopper before consuming live API credit
            current_credits = get_daily_api_usage("HUNTER")
            if current_credits >= daily_hunter_limit:
                print(f"-> [Daily Credit Stopper] Daily limit of {daily_hunter_limit} searches reached. Stopping live sourcing.")
                break

            print(f"\n-> [HUNTER API] Sourcing up to {contacts_per_company} real contacts for {comp_name} ({domain})...")
            candidates = source_hunter_candidates(comp_name, domain, count=contacts_per_company, profile=active_profile)
            # Record credit expenditure
            record_api_usage("HUNTER", domain, credits_used=1)
            print(f"-> [Credit Logged] Consumed 1 Hunter search credit for {domain} (Today: {get_daily_api_usage('HUNTER')}/{daily_hunter_limit})")

        if not candidates:
            print(f"-> [Notice] No indexed contacts found for {comp_name} ({domain}). Checking next company...")
            continue

        target_companies.append(comp)
        print(f"-> [Added Company] {comp_name} ({len(candidates)} contacts)")

        for cand in candidates:
            # Determine channel: use EMAIL if verified work email present, else LINKEDIN
            has_email = bool(cand.synthesized_email and "@" in cand.synthesized_email and not cand.synthesized_email.startswith("contact@"))
            preferred_channel = "EMAIL" if has_email else "LINKEDIN"

            tasks.append({
                "source": "Hunter",
                "candidate": cand,
                "channel": preferred_channel,
                "is_track_1": is_track_1,
                "company_name": comp_name,
                "domain": domain,
                "tech_stack": comp.get("tech_stack"),
                "target_class": cand.classification,
                "email": cand.synthesized_email if has_email else None,
                "profile": active_profile,
                "profile_id": prof_id
            })

        if len(target_companies) >= effective_companies_limit:
            break

    # Limit to daily_cap
    if tasks:
        tasks = tasks[:daily_cap]
        print(f"\n[Outreach Drafting] Generating personalized copy for {len(tasks)} new contacts across {len(target_companies)} companies...")

        # Rate-paced concurrent execution (2 workers with short inter-call pacing to respect free RPM limits)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_to_task = {}
            for t in tasks:
                future = executor.submit(_process_single_outreach, t)
                future_to_task[future] = t
                time.sleep(0.5)  # Pace task dispatch

            for future in concurrent.futures.as_completed(future_to_task):
                try:
                    res = future.result()
                    hunter_results.append(res)
                except Exception as e:
                    print(f"[Worker Error] Drafting failed: {e}")

    print(f"\n[Allocation Complete] Total {len(hunter_results)} real prospect outreaches prepared:")
    emails_count = sum(1 for r in hunter_results if r["email"])
    linkedin_count = len(hunter_results) - emails_count
    print(f"  - Verified Corporate Emails: {emails_count}")
    print(f"  - LinkedIn Notes: {linkedin_count}")

    return {
        "status": "SUCCESS",
        "hunter": hunter_results,
        "total_drafted": len(hunter_results),
        "companies": [c["company_name"] for c in target_companies],
        "today_credits_used": get_daily_api_usage("HUNTER"),
        "daily_credit_limit": daily_hunter_limit,
        "sourcing_mode": sourcing_mode
    }

if __name__ == "__main__":
    run_daily_allocation()


