-- Table 1: Companies
CREATE TABLE IF NOT EXISTS companies (
    domain TEXT PRIMARY KEY,
    profile_id INTEGER DEFAULT 1,             -- Scoped to profile/campaign
    company_name TEXT NOT NULL,
    priority_tier INTEGER NOT NULL DEFAULT 2, -- 1 = Track 1 (<80 applicants), 2 = Track 2
    track TEXT DEFAULT 'TRACK_2',             -- 'TRACK_1' (Active <80 apps) or 'TRACK_2' (Strategic Scoring)
    applicant_count INTEGER,
    location TEXT,
    strategic_score INTEGER DEFAULT 0,        -- 0 to 100 points (Location 30, Industry 45, Size 15, Tech 10)
    employee_count INTEGER,
    industry TEXT,
    job_source_url TEXT,
    tech_stack TEXT,                          -- Concise list of key tools (e.g. PyTorch, SQL)
    key_news TEXT,                            -- Optional short summary + link
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table 2: Contacts
CREATE TABLE IF NOT EXISTS contacts (
    linkedin_url TEXT PRIMARY KEY,
    profile_id INTEGER DEFAULT 1,             -- Scoped to profile/campaign
    company_domain TEXT NOT NULL,
    full_name TEXT NOT NULL,
    title TEXT NOT NULL,
    email TEXT,
    classification TEXT,                      -- 'Hiring Manager', 'Young Professional'
    relevance_score INTEGER,                  -- 0 to 100
    ai_hook TEXT,                             -- Personalized icebreaker (NULL if no obvious link)
    draft_email TEXT,                         -- Drafted email body (NULL if LinkedIn used)
    draft_linkedin TEXT,                      -- Drafted note <300 chars (NULL if email used)
    outreach_status TEXT NOT NULL DEFAULT 'DRAFTED', -- 'DRAFTED', 'APPROVED', 'SENT', 'SKIPPED'
    sent_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(company_domain) REFERENCES companies(domain) ON DELETE CASCADE
);

-- Table 3: API Usage Log (Daily credit tracking and hard cap stopper)
CREATE TABLE IF NOT EXISTS api_usage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    api_name TEXT NOT NULL,                   -- 'HUNTER', 'GEMINI', 'APOLLO'
    domain TEXT NOT NULL,
    credits_used INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_api_usage_date ON api_usage_log(api_name, created_at);

-- Table 4: User Profiles & Search Campaigns (Multi-Profile Support)
CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_name TEXT NOT NULL,               -- e.g. 'Data Science & ML (Default)'
    is_active INTEGER DEFAULT 0,              -- 1 if currently selected active profile
    full_name TEXT NOT NULL,
    email TEXT,
    linkedin_url TEXT,
    alma_mater TEXT,
    degree_major TEXT,
    grad_year TEXT,
    bio_summary TEXT,
    skills TEXT,
    target_roles TEXT,
    target_locations TEXT,
    gemini_api_key TEXT,
    hunter_api_key TEXT,
    sample_hiring_manager TEXT,
    sample_young_professional TEXT,
    is_configured INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
