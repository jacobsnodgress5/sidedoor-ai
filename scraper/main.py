import os
import sys
import yaml
from dotenv import load_dotenv

# Load root .env
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_dotenv_path = os.path.join(_project_root, ".env")
if os.path.exists(_dotenv_path):
    load_dotenv(_dotenv_path)
else:
    load_dotenv()

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

try:
    from scraper.scraper import scrape_jobs
    from scraper.filter import evaluate_all_jobs
    from scraper.notifier import send_email
except (ImportError, ModuleNotFoundError):
    from scraper import scrape_jobs
    from filter import evaluate_all_jobs
    from notifier import send_email

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    cfg = {}
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}

    try:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from src.db.db import get_active_profile
        active_prof = get_active_profile()
        if active_prof:
            search_cfg = cfg.setdefault("search", {})
            raw_kw = active_prof.get("linkedin_search_keywords")
            if raw_kw:
                kws = [k.strip() for k in raw_kw.replace("\n", ",").split(",") if k.strip()]
                if kws:
                    search_cfg["keywords"] = kws
            elif active_prof.get("target_roles"):
                roles = [r.strip() for r in active_prof["target_roles"].split(",") if r.strip()]
                if roles:
                    search_cfg["keywords"] = [f"{r} entry level" for r in roles[:4]]

            if active_prof.get("linkedin_geo_id"):
                search_cfg["geo_id"] = str(active_prof["linkedin_geo_id"]).strip()
            if active_prof.get("linkedin_time_range") is not None:
                search_cfg["time_range"] = str(active_prof["linkedin_time_range"]).strip()
            if active_prof.get("linkedin_location_name"):
                search_cfg["location_name"] = str(active_prof["linkedin_location_name"]).strip()

            cfg["active_profile_name"] = active_prof.get("profile_name", "Default Campaign")
    except Exception:
        pass

    return cfg

def main():
    # Initialize floating desktop progress card overlay
    try:
        from progress_overlay import start_overlay, update_overlay, close_overlay
        start_overlay()
        update_overlay(5.0, "Initializing scraper pipeline...", "Starting session...")
    except Exception:
        start_overlay = update_overlay = close_overlay = None

    print("=" * 60)
    print("LINKEDIN JOB SCRAPER & FILTER PIPELINE")
    print("=" * 60)
    
    # 1. Load config
    try:
        config = load_config()
        camp_name = config.get("active_profile_name", "Default")
        kws = config.get("search", {}).get("keywords", [])
        loc = config.get("search", {}).get("location_name", "Los Angeles, CA")
        print(f"[System] Active Campaign: '{camp_name}'")
        print(f"[System] Search Location: {loc}")
        print(f"[System] Search Keywords: {kws}")
    except Exception as e:
        print(f"[ERROR] Failed to load configuration: {e}")
        if close_overlay: close_overlay()
        return
        
    # 2. Check login session
    auth_file = os.path.join(os.path.dirname(__file__), "auth.json")
    if not os.path.exists(auth_file):
        print(f"[ERROR] Session state file '{auth_file}' not found.")
        print("Please run: python login.py")
        print("to log in manually once and save your authentication state.")
        if close_overlay: close_overlay()
        return
        
    # 3. Scrape jobs
    print("\n[System] Step 1: Scraping jobs from LinkedIn...")
    try:
        raw_jobs = scrape_jobs()
    except Exception as e:
        print(f"[ERROR] Scraper failed: {e}")
        if close_overlay: close_overlay()
        return
        
    if not raw_jobs:
        print("[System] No jobs were scraped. Stopping pipeline.")
        if update_overlay:
            update_overlay(100.0, "No new jobs found.", "Pipeline complete.")
            import time; time.sleep(2)
            close_overlay()
        return

    # 4. Filter and categorize jobs
    print(f"\n[System] Step 2: Evaluating {len(raw_jobs)} job postings...")
    if update_overlay:
        update_overlay(60.0, "Evaluating jobs with Gemini AI...", f"Scraped: {len(raw_jobs)} | Evaluating...")
    best_fit, worse_fit, excluded_count = evaluate_all_jobs(raw_jobs)
    
    # Print out results log
    for idx, job in enumerate(raw_jobs):
        category = job.get("category", "EXCLUDE")
        reason = job.get("reason", "")
        log_prefix = f"  [{idx+1}/{len(raw_jobs)}] {job['title']} at {job['company']}"
        if category == "BEST_FIT":
            print(f"{log_prefix} -> \033[92m[BEST FIT]\033[0m: {reason}")
        elif category == "WORSE_FIT":
            print(f"{log_prefix} -> \033[93m[WORSE FIT]\033[0m: {reason}")
        else:
            print(f"{log_prefix} -> [EXCLUDED]: {reason}")
            
    print(f"\n[System] Evaluation complete. Results:")
    print(f"  - Best Fit: {len(best_fit)}")
    print(f"  - Worse Fit / Stretch: {len(worse_fit)}")
    print(f"  - Excluded: {excluded_count}")

    # 5. Send daily email report
    print("\n[System] Step 3: Sending email notification...")
    if update_overlay:
        update_overlay(80.0, "Generating HTML report & notifications...", f"Best Fit: {len(best_fit)} | Excluded: {excluded_count}")
    excluded = [job for job in raw_jobs if job.get("category") == "EXCLUDE"]
    email_success = send_email(best_fit, worse_fit, excluded)
    
    if email_success:
        print("[System] Daily job report emailed successfully!")
    else:
        print("[System] Email sending failed. (Check last_report.html for local results).")

    # 6. Hook: Ingest companies and jobs into SideDoor AI database
    print("\n[System] Step 4: Caching jobs & companies in SideDoor AI database...")
    if update_overlay:
        update_overlay(90.0, "SideDoor AI: Caching jobs in Daily Jobs...", "Saving jobs to database...")
    # Project root is the parent directory (when inside repo/scraper/)
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if not os.path.exists(os.path.join(project_root, "src")):
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "networking_research_agent"))

    try:
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from src.ingest_companies import ingest_scraped_jobs
        
        ingest_res = ingest_scraped_jobs(raw_jobs)
        print(f"[System] SideDoor Ingestion complete: {ingest_res.get('total_jobs', len(raw_jobs))} jobs ({ingest_res['total_companies']} companies) cached.")
        print("[System] Jobs are ready for review! Visit the Daily Jobs tab to select companies for contact sourcing.")
    except Exception as ing_err:
        print(f"[Warning] SideDoor ingestion encountered notice: {ing_err}")

    if update_overlay:
        update_overlay(100.0, "Scraping & evaluation complete!", "Complete!")
        import time; time.sleep(1)
        close_overlay()
    print("\n[System] All scraping & qualification steps completed.")
        
    print("\n" + "=" * 60)
    print("PIPELINE EXECUTION COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()
