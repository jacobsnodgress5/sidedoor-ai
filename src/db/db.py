#so essentially this file is for running all the needed commands for the db, to upsert and retrieve company and contact info. 

import sqlite3
import os
from typing import Dict, List, Optional
from ..config import DB_PATH, SCHEMA_PATH


def get_db_connection() -> sqlite3.Connection:
    """Establish and return a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize or update the database schema using the schema.sql file."""
    if not os.path.exists(SCHEMA_PATH):
        raise FileNotFoundError(f"Schema file not found at {SCHEMA_PATH}")
    
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()
        
    conn = get_db_connection()
    try:
        conn.executescript(schema_sql)
        
        # Safe column migrations for existing SQLite database
        existing_cols = [r[1] for r in conn.execute("PRAGMA table_info(companies)").fetchall()]
        new_cols = {
            "track": "TEXT DEFAULT 'TRACK_2'",
            "applicant_count": "INTEGER",
            "location": "TEXT",
            "strategic_score": "INTEGER DEFAULT 0",
            "employee_count": "INTEGER",
            "industry": "TEXT",
            "profile_id": "INTEGER DEFAULT 1",
            "selected_for_sourcing": "INTEGER DEFAULT 0"
        }
        for col_name, col_type in new_cols.items():
            if col_name not in existing_cols:
                try:
                    conn.execute(f"ALTER TABLE companies ADD COLUMN {col_name} {col_type}")
                except Exception:
                    pass

        # Migrate profile_id to contacts if not present
        existing_contact_cols = [r[1] for r in conn.execute("PRAGMA table_info(contacts)").fetchall()]
        if "profile_id" not in existing_contact_cols:
            try:
                conn.execute("ALTER TABLE contacts ADD COLUMN profile_id INTEGER DEFAULT 1")
            except Exception:
                pass

        # Migrate sourcing_mode and daily_hunter_limit to profiles if not present
        existing_prof_cols = [r[1] for r in conn.execute("PRAGMA table_info(profiles)").fetchall()]
        if "sourcing_mode" not in existing_prof_cols:
            try:
                conn.execute("ALTER TABLE profiles ADD COLUMN sourcing_mode TEXT DEFAULT 'MANUAL'")
            except Exception:
                pass
        if "daily_hunter_limit" not in existing_prof_cols:
            try:
                conn.execute("ALTER TABLE profiles ADD COLUMN daily_hunter_limit INTEGER DEFAULT 2")
            except Exception:
                pass
        
        # Ensure scraped_jobs table exists
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scraped_jobs (
                id TEXT PRIMARY KEY,
                profile_id INTEGER DEFAULT 1,
                title TEXT NOT NULL,
                company TEXT NOT NULL,
                company_domain TEXT,
                location TEXT,
                url TEXT,
                applicants INTEGER DEFAULT 0,
                category TEXT DEFAULT 'BEST_FIT',
                reason TEXT,
                description TEXT,
                selected_for_sourcing INTEGER DEFAULT 0,
                scraped_date TEXT DEFAULT (DATE('now')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Re-create indexes after columns exist
        conn.execute("CREATE INDEX IF NOT EXISTS idx_companies_track ON companies(track);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_companies_score ON companies(strategic_score);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_contacts_profile ON contacts(profile_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_scraped_jobs_date ON scraped_jobs(scraped_date);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_scraped_jobs_cat ON scraped_jobs(category);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_scraped_jobs_profile ON scraped_jobs(profile_id);")

        # Seed local user profile from message_examples.yaml if table is empty
        seed_initial_profile_if_empty(conn)

        # Seed initial scraped jobs from reports if table is empty
        seed_scraped_jobs_from_reports_if_empty(conn)

        conn.commit()
    finally:
        conn.close()

# -------------------------------------------------------------
# Company Table Operations
# -------------------------------------------------------------
#these functions run sql commands on the database tables
def get_company(domain: str) -> Optional[Dict]:
    """Retrieve a company by its primary domain."""
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT * FROM companies WHERE domain = ?",
            (domain,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def get_all_companies(priority_tier: Optional[int] = None) -> List[Dict]:
    """Retrieve all companies, optionally filtered by priority_tier."""
    conn = get_db_connection()
    try:
        if priority_tier is not None:
            rows = conn.execute(
                "SELECT * FROM companies WHERE priority_tier = ? ORDER BY strategic_score DESC, created_at DESC",
                (priority_tier,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM companies ORDER BY priority_tier ASC, strategic_score DESC, created_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def get_track_1_companies() -> List[Dict]:
    """Retrieve Track 1 companies (<80 applicants / active job posting priority)."""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM companies WHERE track = 'TRACK_1' OR priority_tier = 1 ORDER BY applicant_count ASC, created_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def get_track_2_companies() -> List[Dict]:
    """Retrieve Track 2 companies sorted by Strategic Company Score."""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM companies WHERE track = 'TRACK_2' OR priority_tier = 2 ORDER BY strategic_score DESC, created_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def upsert_company(
    domain: str,
    company_name: str,
    priority_tier: int = 2,
    track: str = "TRACK_2",
    applicant_count: Optional[int] = None,
    location: Optional[str] = None,
    strategic_score: int = 0,
    employee_count: Optional[int] = None,
    industry: Optional[str] = None,
    job_source_url: Optional[str] = None,
    tech_stack: Optional[str] = None,
    key_news: Optional[str] = None
):
    """
    Insert or update a company record with Two-Track intelligence fields.
    """
    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO companies (
                domain, company_name, priority_tier, track, applicant_count, location,
                strategic_score, employee_count, industry, job_source_url, tech_stack, key_news, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(domain) DO UPDATE SET
                company_name = excluded.company_name,
                priority_tier = MIN(companies.priority_tier, excluded.priority_tier),
                track = CASE WHEN excluded.priority_tier = 1 THEN 'TRACK_1' ELSE companies.track END,
                applicant_count = COALESCE(excluded.applicant_count, companies.applicant_count),
                location = COALESCE(excluded.location, companies.location),
                strategic_score = MAX(companies.strategic_score, excluded.strategic_score),
                employee_count = COALESCE(excluded.employee_count, companies.employee_count),
                industry = COALESCE(excluded.industry, companies.industry),
                job_source_url = COALESCE(excluded.job_source_url, companies.job_source_url),
                tech_stack = COALESCE(excluded.tech_stack, companies.tech_stack),
                key_news = COALESCE(excluded.key_news, companies.key_news)
            """,
            (
                domain, company_name, priority_tier, track, applicant_count, location,
                strategic_score, employee_count, industry, job_source_url, tech_stack, key_news
            )
        )
        conn.commit()
    finally:
        conn.close()

# -------------------------------------------------------------
# Contact Table Operations
# -------------------------------------------------------------

def get_contact(linkedin_url: str) -> Optional[Dict]:
    """Retrieve a contact by LinkedIn URL."""
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT * FROM contacts WHERE linkedin_url = ?",
            (linkedin_url,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def get_contacts_by_company(company_domain: str, profile_id: Optional[int] = None) -> List[Dict]:
    """Retrieve all contacts associated with a specific company domain for the target profile."""
    conn = get_db_connection()
    try:
        if profile_id is not None:
            rows = conn.execute(
                "SELECT * FROM contacts WHERE company_domain = ? AND profile_id = ? ORDER BY relevance_score DESC",
                (company_domain, profile_id)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM contacts WHERE company_domain = ? ORDER BY relevance_score DESC",
                (company_domain,)
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def get_all_contacts(status: Optional[str] = None, profile_id: Optional[int] = None) -> List[Dict]:
    """Retrieve all contacts, optionally filtered by outreach_status and profile_id."""
    conn = get_db_connection()
    try:
        query = "SELECT * FROM contacts WHERE 1=1"
        params = []
        if profile_id is not None:
            query += " AND profile_id = ?"
            params.append(profile_id)
        if status:
            query += " AND outreach_status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC"
        
        rows = conn.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def upsert_contact(
    linkedin_url: str,
    company_domain: str,
    full_name: str,
    title: str,
    email: Optional[str] = None,
    classification: Optional[str] = None,
    relevance_score: Optional[int] = None,
    ai_hook: Optional[str] = None,
    draft_email: Optional[str] = None,
    draft_linkedin: Optional[str] = None,
    outreach_status: str = "DRAFTED",
    sent_at: Optional[str] = None,
    profile_id: Optional[int] = None
):
    """Insert or update a contact record scoped to a profile."""
    if profile_id is None:
        active = get_active_profile()
        profile_id = active["id"] if active else 1

    conn = get_db_connection()
    try:
        # Ensure company exists to satisfy foreign key constraint
        conn.execute(
            "INSERT OR IGNORE INTO companies (domain, company_name, profile_id) VALUES (?, ?, ?)",
            (company_domain, company_domain.split('.')[0].capitalize(), profile_id)
        )
        conn.execute(
            """
            INSERT INTO contacts (
                linkedin_url, profile_id, company_domain, full_name, title, email, classification,
                relevance_score, ai_hook, draft_email, draft_linkedin, outreach_status, sent_at, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(linkedin_url) DO UPDATE SET
                profile_id = COALESCE(excluded.profile_id, contacts.profile_id),
                company_domain = excluded.company_domain,
                full_name = excluded.full_name,
                title = excluded.title,
                email = COALESCE(excluded.email, contacts.email),
                classification = COALESCE(excluded.classification, contacts.classification),
                relevance_score = COALESCE(excluded.relevance_score, contacts.relevance_score),
                ai_hook = COALESCE(excluded.ai_hook, contacts.ai_hook),
                draft_email = COALESCE(excluded.draft_email, contacts.draft_email),
                draft_linkedin = COALESCE(excluded.draft_linkedin, contacts.draft_linkedin),
                outreach_status = excluded.outreach_status,
                sent_at = COALESCE(excluded.sent_at, contacts.sent_at)
            """,
            (
                linkedin_url, profile_id, company_domain, full_name, title, email, classification,
                relevance_score, ai_hook, draft_email, draft_linkedin, outreach_status, sent_at
            )
        )
        conn.commit()
    finally:
        conn.close()

def update_contact_status(linkedin_url: str, status: str, sent_at: Optional[str] = None):
    """Update status for a contact. Automatically manages sent_at timestamps."""
    conn = get_db_connection()
    try:
        if status == "SENT":
            conn.execute(
                "UPDATE contacts SET outreach_status = 'SENT', sent_at = CURRENT_TIMESTAMP WHERE linkedin_url = ?",
                (linkedin_url,)
            )
        elif status == "DRAFTED":
            conn.execute(
                "UPDATE contacts SET outreach_status = 'DRAFTED', sent_at = NULL WHERE linkedin_url = ?",
                (linkedin_url,)
            )
        else:
            conn.execute(
                "UPDATE contacts SET outreach_status = ? WHERE linkedin_url = ?",
                (status, linkedin_url)
            )
        conn.commit()
    finally:
        conn.close()

# -------------------------------------------------------------
# API Usage Tracking Operations (Hard Stopper & Daily Safety)
# -------------------------------------------------------------

def record_api_usage(api_name: str, domain: str, credits_used: int = 1):
    """Record an API credit expenditure with timestamp."""
    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO api_usage_log (api_name, domain, credits_used, created_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (api_name.upper(), domain, credits_used)
        )
        conn.commit()
    finally:
        conn.close()

def get_daily_api_usage(api_name: str = "HUNTER") -> int:
    """Return the total number of credits consumed today for the given API."""
    conn = get_db_connection()
    try:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(credits_used), 0) AS total_today
            FROM api_usage_log
            WHERE api_name = ? AND DATE(created_at) = DATE('now')
            """,
            (api_name.upper(),)
        ).fetchone()
        return row["total_today"] if row else 0
    finally:
        conn.close()

# -------------------------------------------------------------
# Multi-Profile & Multi-Campaign Operations
# -------------------------------------------------------------

def seed_initial_profile_if_empty(conn: sqlite3.Connection):
    """Seed initial profile in `profiles` table, migrating from `local_profile` if it exists."""
    # 1. Check if profiles table already has data
    try:
        row = conn.execute("SELECT COUNT(*) AS cnt FROM profiles").fetchone()
        if row and row["cnt"] > 0:
            active = conn.execute("SELECT COUNT(*) AS cnt FROM profiles WHERE is_active = 1").fetchone()
            if not active or active["cnt"] == 0:
                conn.execute("UPDATE profiles SET is_active = 1 WHERE id = (SELECT MIN(id) FROM profiles)")
            return
    except Exception as e:
        print(f"[Profiles Seed Notice] {e}")

    # 2. Check if local_profile table exists and has data to migrate
    try:
        lp_row = conn.execute("SELECT * FROM local_profile WHERE id = 1").fetchone()
        if lp_row:
            lp = dict(lp_row)
            conn.execute("""
                INSERT INTO profiles (
                    id, profile_name, is_active, full_name, email, linkedin_url,
                    alma_mater, degree_major, grad_year, bio_summary, skills,
                    target_roles, target_locations, gemini_api_key, hunter_api_key,
                    sample_hiring_manager, sample_young_professional, is_configured,
                    created_at, updated_at
                ) VALUES (
                    1, 'Data Science & ML (Default)', 1, :full_name, :email, :linkedin_url,
                    :alma_mater, :degree_major, :grad_year, :bio_summary, :skills,
                    :target_roles, :target_locations, :gemini_api_key, :hunter_api_key,
                    :sample_hiring_manager, :sample_young_professional, :is_configured,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """, lp)
            print("[Migration] Migrated existing local_profile into profiles table as Profile #1.")
            return
    except Exception:
        pass

    # 3. Fallback: Seed from message_examples.yaml and .env
    yaml_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config", "message_examples.yaml")
    sender_profile = {}
    hm_sample = ""
    yp_sample = ""
    if os.path.exists(yaml_path):
        try:
            import yaml
            with open(yaml_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
                sender_profile = cfg.get("sender_profile", {})
                user_ex = cfg.get("user_provided_examples", {})
                hm_samples = user_ex.get("hiring_manager_samples", [])
                yp_samples = user_ex.get("young_professional_samples", [])
                if hm_samples:
                    hm_sample = hm_samples[0]
                if yp_samples:
                    yp_sample = yp_samples[0]
        except Exception as e:
            print(f"[Seed Profile Notice] {e}")

    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    hunter_key = os.environ.get("HUNTER_API_KEY", "")

    conn.execute("""
        INSERT OR IGNORE INTO profiles (
            id, profile_name, is_active, full_name, email, linkedin_url, alma_mater, degree_major,
            grad_year, bio_summary, skills, target_roles, target_locations,
            gemini_api_key, hunter_api_key, sample_hiring_manager,
            sample_young_professional, is_configured, created_at, updated_at
        ) VALUES (
            1, 'Primary Track', 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        )
    """, (
        sender_profile.get("name", ""),
        sender_profile.get("email", ""),
        sender_profile.get("linkedin", ""),
        sender_profile.get("alma_mater", ""),
        sender_profile.get("education", ""),
        sender_profile.get("grad_year", ""),
        sender_profile.get("background", ""),
        sender_profile.get("skills", ""),
        sender_profile.get("target_roles", ""),
        "Remote",
        gemini_key,
        hunter_key,
        hm_sample,
        yp_sample
    ))

def get_active_profile() -> Optional[Dict]:
    """Retrieve the currently active profile from SQLite."""
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM profiles WHERE is_active = 1 LIMIT 1").fetchone()
        if not row:
            row = conn.execute("SELECT * FROM profiles ORDER BY id ASC LIMIT 1").fetchone()
            if row:
                conn.execute("UPDATE profiles SET is_active = 1 WHERE id = ?", (row["id"],))
                conn.commit()
        return dict(row) if row else None
    finally:
        conn.close()

def get_profile_by_id(profile_id: int) -> Optional[Dict]:
    """Retrieve a specific profile by its ID."""
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def get_all_profiles() -> List[Dict]:
    """Return all profiles for the profile switcher dropdown."""
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT id, profile_name, full_name, is_active, is_configured, target_roles, target_locations, updated_at
            FROM profiles
            ORDER BY id ASC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def switch_active_profile(profile_id: int) -> Optional[Dict]:
    """Set profile_id as active and deactivate all other profiles."""
    conn = get_db_connection()
    try:
        conn.execute("UPDATE profiles SET is_active = 0")
        conn.execute("UPDATE profiles SET is_active = 1 WHERE id = ?", (profile_id,))
        conn.commit()
        row = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def save_profile(data: Dict, profile_id: Optional[int] = None) -> Dict:
    """
    Save or update a profile.
    If profile_id is None, creates a new profile and activates it.
    If profile_id exists, updates that profile.
    """
    conn = get_db_connection()
    try:
        prof_name = data.get("profile_name", "").strip() or f"{data.get('full_name', 'My Profile')} Campaign"
        
        # Check if profile exists
        existing = None
        if profile_id:
            existing = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()

        if existing:
            conn.execute("""
                UPDATE profiles SET
                    profile_name = :profile_name,
                    full_name = :full_name,
                    email = :email,
                    linkedin_url = :linkedin_url,
                    alma_mater = :alma_mater,
                    degree_major = :degree_major,
                    grad_year = :grad_year,
                    bio_summary = :bio_summary,
                    skills = :skills,
                    target_roles = :target_roles,
                    target_locations = :target_locations,
                    gemini_api_key = CASE 
                        WHEN :gemini_api_key != '' THEN :gemini_api_key 
                        ELSE profiles.gemini_api_key 
                    END,
                    hunter_api_key = CASE 
                        WHEN :hunter_api_key != '' THEN :hunter_api_key 
                        ELSE profiles.hunter_api_key 
                    END,
                    sample_hiring_manager = :sample_hiring_manager,
                    sample_young_professional = :sample_young_professional,
                    is_configured = 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :id;
            """, {
                "id": profile_id,
                "profile_name": prof_name,
                "full_name": data.get("full_name", "").strip(),
                "email": data.get("email", "").strip(),
                "linkedin_url": data.get("linkedin_url", "").strip(),
                "alma_mater": data.get("alma_mater", "").strip(),
                "degree_major": data.get("degree_major", "").strip(),
                "grad_year": str(data.get("grad_year", "")).strip(),
                "bio_summary": data.get("bio_summary", "").strip(),
                "skills": data.get("skills", "").strip(),
                "target_roles": data.get("target_roles", "").strip(),
                "target_locations": data.get("target_locations", "").strip(),
                "gemini_api_key": data.get("gemini_api_key", "").strip(),
                "hunter_api_key": data.get("hunter_api_key", "").strip(),
                "sample_hiring_manager": data.get("sample_hiring_manager", "").strip(),
                "sample_young_professional": data.get("sample_young_professional", "").strip(),
            })
            target_id = profile_id
        else:
            # Set all others to inactive and make new profile active
            conn.execute("UPDATE profiles SET is_active = 0")
            cursor = conn.execute("""
                INSERT INTO profiles (
                    profile_name, is_active, full_name, email, linkedin_url, alma_mater, degree_major,
                    grad_year, bio_summary, skills, target_roles, target_locations,
                    gemini_api_key, hunter_api_key, sample_hiring_manager,
                    sample_young_professional, is_configured, created_at, updated_at
                ) VALUES (
                    :profile_name, 1, :full_name, :email, :linkedin_url, :alma_mater, :degree_major,
                    :grad_year, :bio_summary, :skills, :target_roles, :target_locations,
                    :gemini_api_key, :hunter_api_key, :sample_hiring_manager,
                    :sample_young_professional, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                );
            """, {
                "profile_name": prof_name,
                "full_name": data.get("full_name", "").strip(),
                "email": data.get("email", "").strip(),
                "linkedin_url": data.get("linkedin_url", "").strip(),
                "alma_mater": data.get("alma_mater", "").strip(),
                "degree_major": data.get("degree_major", "").strip(),
                "grad_year": str(data.get("grad_year", "")).strip(),
                "bio_summary": data.get("bio_summary", "").strip(),
                "skills": data.get("skills", "").strip(),
                "target_roles": data.get("target_roles", "").strip(),
                "target_locations": data.get("target_locations", "").strip(),
                "gemini_api_key": data.get("gemini_api_key", "").strip(),
                "hunter_api_key": data.get("hunter_api_key", "").strip(),
                "sample_hiring_manager": data.get("sample_hiring_manager", "").strip(),
                "sample_young_professional": data.get("sample_young_professional", "").strip(),
            })
            target_id = cursor.lastrowid

        conn.commit()
        row = conn.execute("SELECT * FROM profiles WHERE id = ?", (target_id,)).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()

def delete_profile(profile_id: int) -> bool:
    """Delete a profile and its scoped contacts. Returns False if only 1 profile remains."""
    conn = get_db_connection()
    try:
        cnt_row = conn.execute("SELECT COUNT(*) AS cnt FROM profiles").fetchone()
        if cnt_row and cnt_row["cnt"] <= 1:
            return False  # Do not allow deleting the last remaining profile

        # Delete contacts belonging to this profile
        conn.execute("DELETE FROM contacts WHERE profile_id = ?", (profile_id,))
        # Delete profile
        conn.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
        
        # If deleted profile was active, activate first available profile
        active_cnt = conn.execute("SELECT COUNT(*) AS cnt FROM profiles WHERE is_active = 1").fetchone()
        if not active_cnt or active_cnt["cnt"] == 0:
            conn.execute("UPDATE profiles SET is_active = 1 WHERE id = (SELECT MIN(id) FROM profiles)")

        conn.commit()
        return True
    finally:
        conn.close()

# Compatibility Aliases
def get_local_profile() -> Optional[Dict]:
    return get_active_profile()

def save_local_profile(data: Dict) -> Dict:
    active = get_active_profile()
    active_id = active["id"] if active else None
    return save_profile(data, profile_id=active_id)

# -------------------------------------------------------------
# Scraped Jobs Operations & Seed Logic
# -------------------------------------------------------------

def seed_scraped_jobs_from_reports_if_empty(conn: sqlite3.Connection):
    """If scraped_jobs is empty, parse last_report.html and excluded_report.html to populate cache."""
    try:
        cur = conn.execute("SELECT COUNT(*) as cnt FROM scraped_jobs")
        count = cur.fetchone()["cnt"]
        if count > 0:
            return

        from bs4 import BeautifulSoup
        import re

        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        last_report = os.path.join(project_dir, "scraper", "last_report.html")
        excluded_report = os.path.join(project_dir, "scraper", "excluded_report.html")

        imported = 0

        # Import curated jobs (Best Fit and Worse Fit)
        if os.path.exists(last_report):
            with open(last_report, "r", encoding="utf-8") as f:
                soup = BeautifulSoup(f.read(), "html.parser")
            
            cards = soup.find_all("div", class_="job-card")
            for c in cards:
                title_a = c.find("div", class_="job-title").find("a") if c.find("div", class_="job-title") else None
                if not title_a:
                    continue
                title = title_a.text.strip()
                url = title_a.get("href", "")
                
                # Check category from parent section title
                parent_section = c.find_parent("div", class_="section")
                is_worse = parent_section and "worse" in str(parent_section.get("class", [])).lower()
                category = "WORSE_FIT" if is_worse else "BEST_FIT"

                meta = c.find("div", class_="job-meta")
                meta_text = meta.text if meta else ""
                company = meta.find("strong").text.strip() if (meta and meta.find("strong")) else "Unknown"
                
                parts = [p.strip() for p in meta_text.split("·") if p.strip()]
                loc = parts[1] if len(parts) > 1 else "Remote"

                from scraper.scraper import parse_applicant_count
                applicants = parse_applicant_count(meta_text)

                reason_p = c.find("p", class_="job-reason")
                reason = reason_p.text.replace("Match Details:", "").strip() if reason_p else ""

                m = re.search(r'/view/(\d+)', url)
                job_id = m.group(1) if m else url

                slug = re.sub(r'[^a-z0-9\-]', '', company.lower().replace(' ', ''))
                domain = f"{slug}.com" if slug else "unknown.com"

                conn.execute("""
                    INSERT OR IGNORE INTO scraped_jobs (
                        id, profile_id, title, company, company_domain, location, url,
                        applicants, category, reason, description, selected_for_sourcing, scraped_date
                    ) VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, '', 0, DATE('now'))
                """, (job_id, title, company, domain, loc, url, applicants, category, reason))
                imported += 1

        # Import excluded jobs
        if os.path.exists(excluded_report):
            with open(excluded_report, "r", encoding="utf-8") as f:
                soup = BeautifulSoup(f.read(), "html.parser")
            
            cards = soup.find_all("div", class_="job-card")
            for c in cards:
                title_a = c.find("div", class_="job-title").find("a") if c.find("div", class_="job-title") else None
                if not title_a:
                    continue
                title = title_a.text.strip()
                url = title_a.get("href", "")
                meta = c.find("div", class_="job-meta")
                meta_text = meta.text if meta else ""
                company = meta.find("strong").text.strip() if (meta and meta.find("strong")) else "Unknown"
                
                parts = [p.strip() for p in meta_text.split("·") if p.strip()]
                loc = parts[1] if len(parts) > 1 else "On-site"

                from scraper.scraper import parse_applicant_count
                applicants = parse_applicant_count(meta_text)

                reason_p = c.find("p", class_="exclusion-reason")
                reason = reason_p.text.replace("Exclusion Reason:", "").strip() if reason_p else ""

                m = re.search(r'/view/(\d+)', url)
                job_id = m.group(1) if m else url

                slug = re.sub(r'[^a-z0-9\-]', '', company.lower().replace(' ', ''))
                domain = f"{slug}.com" if slug else "unknown.com"

                conn.execute("""
                    INSERT OR IGNORE INTO scraped_jobs (
                        id, profile_id, title, company, company_domain, location, url,
                        applicants, category, reason, description, selected_for_sourcing, scraped_date
                    ) VALUES (?, 1, ?, ?, ?, ?, ?, ?, 'EXCLUDE', ?, '', 0, DATE('now'))
                """, (job_id, title, company, domain, loc, url, applicants, reason))
                imported += 1

        if imported > 0:
            print(f"[SideDoor DB] Automatically seeded {imported} historical jobs into scraped_jobs cache.")
    except Exception as e:
        print(f"[SideDoor DB] Notice: could not seed from report html files: {e}")

def upsert_scraped_job(
    job_id: str,
    title: str,
    company: str,
    company_domain: str,
    location: str,
    url: str,
    applicants: int,
    category: str,
    reason: str,
    description: str = "",
    selected_for_sourcing: int = 0,
    profile_id: int = 1
):
    """Insert or update a scraped job in the daily cache."""
    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO scraped_jobs (
                id, profile_id, title, company, company_domain, location, url,
                applicants, category, reason, description, selected_for_sourcing, scraped_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, DATE('now'))
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                company = excluded.company,
                company_domain = excluded.company_domain,
                location = excluded.location,
                url = excluded.url,
                applicants = excluded.applicants,
                category = excluded.category,
                reason = excluded.reason,
                description = CASE WHEN excluded.description != '' THEN excluded.description ELSE scraped_jobs.description END,
                profile_id = excluded.profile_id
        """, (
            job_id, profile_id, title, company, company_domain, location, url,
            applicants, category, reason, description, selected_for_sourcing
        ))
        conn.commit()
    finally:
        conn.close()

def get_scraped_jobs(
    profile_id: Optional[int] = None,
    date_filter: Optional[str] = None,
    category: Optional[str] = None
) -> List[Dict]:
    """Retrieve scraped jobs with optional filters."""
    conn = get_db_connection()
    try:
        query = "SELECT * FROM scraped_jobs WHERE 1=1"
        params = []
        if profile_id:
            query += " AND profile_id = ?"
            params.append(profile_id)
        if date_filter:
            query += " AND scraped_date = ?"
            params.append(date_filter)
        if category and category != "ALL":
            query += " AND category = ?"
            params.append(category)
        query += " ORDER BY CASE category WHEN 'BEST_FIT' THEN 1 WHEN 'WORSE_FIT' THEN 2 ELSE 3 END, applicants ASC, created_at DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def toggle_job_sourcing(job_id: str, selected: Optional[int] = None) -> Dict:
    """Toggle or set whether a job/company is selected for Hunter sourcing."""
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM scraped_jobs WHERE id = ?", (job_id,)).fetchone()
        if not row:
            return {"success": False, "error": "Job not found"}
        
        current = row["selected_for_sourcing"]
        new_val = (1 if selected else 0) if selected is not None else (0 if current else 1)
        domain = row["company_domain"]
        
        conn.execute("UPDATE scraped_jobs SET selected_for_sourcing = ? WHERE id = ?", (new_val, job_id))
        if domain:
            conn.execute("UPDATE companies SET selected_for_sourcing = ? WHERE domain = ?", (new_val, domain))
        conn.commit()
        return {"success": True, "job_id": job_id, "selected": new_val, "company_domain": domain}
    finally:
        conn.close()

def bulk_toggle_job_sourcing(category: str = "BEST_FIT", selected: int = 1, profile_id: Optional[int] = None) -> int:
    """Bulk select or deselect jobs by category for Hunter sourcing."""
    conn = get_db_connection()
    try:
        query = "UPDATE scraped_jobs SET selected_for_sourcing = ? WHERE category = ?"
        params = [selected, category]
        if profile_id:
            query += " AND profile_id = ?"
            params.append(profile_id)
        cursor = conn.execute(query, params)
        # Also update corresponding companies
        conn.execute("""
            UPDATE companies SET selected_for_sourcing = ?
            WHERE domain IN (SELECT company_domain FROM scraped_jobs WHERE selected_for_sourcing = ?)
        """, (selected, selected))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()

def get_today_scraped_jobs_count(profile_id: Optional[int] = None) -> Dict:
    """Get metrics about today's scraped jobs."""
    conn = get_db_connection()
    try:
        row = conn.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN category = 'BEST_FIT' THEN 1 ELSE 0 END) as best_fit,
                SUM(CASE WHEN category = 'WORSE_FIT' THEN 1 ELSE 0 END) as worse_fit,
                SUM(CASE WHEN category = 'EXCLUDE' THEN 1 ELSE 0 END) as excluded,
                SUM(CASE WHEN selected_for_sourcing = 1 THEN 1 ELSE 0 END) as selected
            FROM scraped_jobs 
            WHERE scraped_date = DATE('now')
        """).fetchone()

        all_time = conn.execute("SELECT COUNT(*) as total FROM scraped_jobs").fetchone()
        
        return {
            "total_today": row["total"] or 0,
            "best_fit_today": row["best_fit"] or 0,
            "worse_fit_today": row["worse_fit"] or 0,
            "excluded_today": row["excluded"] or 0,
            "selected_today": row["selected"] or 0,
            "total_all_time": all_time["total"] or 0,
            "has_scraped_today": bool(row["total"] and row["total"] > 0)
        }
    finally:
        conn.close()

def get_sourcing_settings(profile_id: Optional[int] = None) -> Dict:
    """Retrieve sourcing mode ('MANUAL' vs 'AUTO') and credit limits."""
    conn = get_db_connection()
    try:
        prof = None
        if profile_id:
            row = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
            prof = dict(row) if row else None
        if not prof:
            row = conn.execute("SELECT * FROM profiles WHERE is_active = 1").fetchone()
            prof = dict(row) if row else None
        
        mode = prof.get("sourcing_mode", "MANUAL") if prof else "MANUAL"
        daily_limit = prof.get("daily_hunter_limit", 2) if prof else 2
        today_hunter_credits = get_daily_api_usage("HUNTER")
        
        monthly_row = conn.execute(
            "SELECT COALESCE(SUM(credits_used), 0) as total FROM api_usage_log WHERE api_name = 'HUNTER' AND strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')"
        ).fetchone()
        monthly_hunter_credits = monthly_row["total"] if monthly_row else 0

        return {
            "sourcing_mode": mode or "MANUAL",
            "daily_hunter_limit": daily_limit or 2,
            "today_hunter_used": today_hunter_credits,
            "monthly_hunter_used": monthly_hunter_credits,
            "monthly_quota_estimate": 25,
            "credits_remaining_today": max(0, (daily_limit or 2) - today_hunter_credits),
            "credits_remaining_month": max(0, 25 - monthly_hunter_credits)
        }
    finally:
        conn.close()

def save_sourcing_settings(sourcing_mode: str, daily_hunter_limit: int, profile_id: Optional[int] = None):
    """Save sourcing mode and daily limit to profile."""
    conn = get_db_connection()
    try:
        target_id = profile_id
        if not target_id:
            act = conn.execute("SELECT id FROM profiles WHERE is_active = 1").fetchone()
            target_id = act["id"] if act else 1
        conn.execute(
            "UPDATE profiles SET sourcing_mode = ?, daily_hunter_limit = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (sourcing_mode, daily_hunter_limit, target_id)
        )
        conn.commit()
    finally:
        conn.close()

def get_selected_companies_for_sourcing(profile_id: Optional[int] = None) -> List[Dict]:
    """Retrieve companies explicitly selected by the user for Hunter sourcing."""
    conn = get_db_connection()
    try:
        query = """
            SELECT DISTINCT c.* FROM companies c
            JOIN scraped_jobs j ON c.domain = j.company_domain
            WHERE j.selected_for_sourcing = 1
        """
        params = []
        if profile_id:
            query += " AND (c.profile_id = ? OR j.profile_id = ?)"
            params.extend([profile_id, profile_id])
        query += " ORDER BY c.priority_tier ASC, c.strategic_score DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()



