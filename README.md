# SideDoor AI
> **Spamming job applications isn't the only option. Local-First AI Career Networking Agent**

SideDoor AI is built to help you streamline cold networking so you can focus on connecting with people who can help you find your next job.

100% free to self-host, local-first, and zero code required to configure.

No message goes out with out your approval, but you don't have to do the work.

---

## Features

-  **Two-Track Prospecting Engine**:
  - **Track 1 (Early Bird / Recently Applied)**: Prioritizes active roles with `< 80 applicants` where reaching out immediately gives a massive advantage.
  - **Track 2 (Strategic Scoring)**: Evaluates companies on a 100-point rubric matching your target locations, technical skills, and target industries.
- **Multi-Campaign & Multi-Profile Support**:
  - Run multiple search tracks concurrently based on your different job profiles (e.g. *Data Science (LA)* vs. *Full Stack (Remote)*).
  - Completely isolated contacts, drafts, and analytics per profile.
  - Switch between profiles in 1 click from the navbar.
- 📄 **AI Resume Auto-Import**:
  - Paste raw resume text into the setup wizard and let Gemini auto-extract your skills, education, target roles, and background summary. Additionally you can include your profile information manually, and adjust the AI auto import afterwards.
- **Authentic AI Copywriter**:
  - Trains Gemini on your real outreach messages to mirror your tone, style, and syntax.
  - Generates punchy corporate emails (`<125 words`) and concise LinkedIn connection notes (`<300 chars`) ideally for cold networking.
  - No generic template spam.
- **100% Local & Private**:
  - Everything runs locally on your machine with SQLite (`sidedoor_cache.db`).
  - API keys are stored only on your computer; zero cloud telemetry or third-party servers.
  - Hunter API credit protection: Caches domains and respects daily search limits to preserve free-tier quotas.

---

## Quickstart

### Option 1: Windows (1-Click Guided Setup — Recommended)
1. **Download / Clone** this repository to your computer:
   ```bash
   git clone https://github.com/jacobsnodgress5/sidedoor-ai.git
   ```
2. **Double-click `start.bat`** in File Explorer.

A terminal window will pop open and automatically guide you through everything:
- ✅ Detects Python (or guides you to install it)
- ✅ Creates an isolated virtual environment (`.venv`)
- ✅ Installs all dependencies and Playwright Chromium
- ✅ Prompts you for your free Gemini & Hunter.io API keys (with direct links)
- ✅ Opens LinkedIn in a browser so you can log in once to save your session
- ✅ Launches the dashboard and opens `http://localhost:8080` in your browser!

*(To run SideDoor AI in the future, just double-click `start.bat` again anytime — it will skip setup and boot directly into the dashboard.)*

---

### Option 2: Command Line (Windows, macOS, Linux)
If you prefer running via terminal:

1. **Clone the repository**:
   ```bash
   git clone https://github.com/jacobsnodgress5/sidedoor-ai.git
   cd sidedoor-ai
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

3. **Configure API Keys**:
   - Create a `.env` file in the root directory:
     ```ini
     GEMINI_API_KEY="your_gemini_api_key"
     HUNTER_API_KEY="your_hunter_api_key"
     ```
   *(You can also input your API keys directly into the web interface upon first launch).*

4. **One-Time LinkedIn Authentication (Required for Scraper)**:
   ```bash
   python scraper/login.py
   ```
   A browser window will open. Log into LinkedIn manually once. Once your feed loads, press **Enter** in your terminal. This saves your session cookies securely into `scraper/auth.json` so automated scraping works without being blocked.

5. **Launch SideDoor AI**:
   ```bash
   python app.py
   ```
   Open [http://localhost:8080](http://localhost:8080) in your browser.

---

## Web Dashboard

- **Review Deck**: Swipe through drafted outreach cards, edit messages inline, copy with 1 click, or mark as sent.
- **Company Radar**: View scored target companies, tech stacks, and track classifications.
- **Contacts Directory**: Filter and manage your sourced network by campaign, company, and outreach status.
- **Campaign Switcher**: Seamlessly toggle between multiple job search tracks with isolated data.

---

## 🏗️ Architecture

```
sidedoor-ai/
├── app.py                      # Application entry point (starts web server)
├── start.bat                   # 1-click Windows launcher
├── schema.sql                  # SQLite schema (multi-profile, companies, contacts)
├── requirements.txt            # Python dependencies (Playwright, Gemini, etc.)
├── scraper/                    # LinkedIn Job Scraper & Qualification Pipeline
│   ├── main.py                 # Pipeline runner & direct SideDoor ingestion trigger
│   ├── scraper.py              # Playwright LinkedIn job scraper
│   ├── filter.py               # Two-stage AI job qualification & candidate scoring
│   ├── login.py                # LinkedIn session / cookie manager
│   ├── notifier.py             # HTML email reports generator
│   ├── progress_overlay.py     # Desktop HUD progress overlay
│   ├── config.yaml             # Scraper configuration & target criteria
│   ├── config.example.yaml     # Template configuration
│   ├── run_daily.bat           # Scheduled daily run launcher
│   └── run_silent.vbs          # Headless background execution script
├── src/
│   ├── agents/
│   │   ├── copywriter.py       # Personalized outreach generator (Gemini 2.5 Flash)
│   │   ├── company_scorer.py   # 100-pt strategic company rubric
│   │   └── contact_sourcer.py  # Personnel search & scoring
│   ├── sourcers/
│   │   └── hunter_sourcer.py   # Hunter.io domain search & corporate email synthesizer
│   ├── db/
│   │   └── db.py               # SQLite interface & multi-profile management
│   ├── allocation_engine.py    # Daily prospecting & credit safety controller
│   └── web/
│       ├── server.py           # Local HTTP & REST API server
│       └── index.html          # Single-page dashboard (Tailwind CSS, Alpine/Vanilla JS)
```

---

## 🔒 Privacy & License

SideDoor AI is open-source software licensed under the MIT License. All data, contacts, resumes, and API tokens remain stored exclusively on your local device in SQLite.
