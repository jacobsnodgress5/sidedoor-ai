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
            "profile_id": "INTEGER DEFAULT 1"
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
        
        # Re-create indexes after columns exist
        conn.execute("CREATE INDEX IF NOT EXISTS idx_companies_track ON companies(track);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_companies_score ON companies(strategic_score);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_contacts_profile ON contacts(profile_id);")

        # Seed local user profile from message_examples.yaml if table is empty
        seed_initial_profile_if_empty(conn)

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


