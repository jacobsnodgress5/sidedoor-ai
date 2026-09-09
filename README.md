# SideDoor AI
> **Skip the ATS line. Autonomous, Local-First AI Career Networking Agent**

SideDoor AI transforms cold job applications into a high-conversion networking system. It identifies high-fit companies, sources verified corporate contacts via Hunter.io, and drafts personalized, outreach messages written in your  voice.

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

### Option 1: Windows (One-Click)
Double-click `start.bat`. It will detect your Python/Anaconda installation, initialize your local environment, and open `http://localhost:8080` in your browser.

### Option 2: Command Line (Windows, macOS, Linux)
1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/sidedoor-ai.git
   cd sidedoor-ai
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure API Keys**:
   - Copy `.env.example` to `.env` or simply configure your keys in the web UI upon launch: (you must manually find and copy API keys from these sites, may include creating a profile. Takes less than 5 minutes.
     - **Gemini API Key** (Free): [Google AI Studio](https://aistudio.google.com/app/apikey)
     - **Hunter.io API Key** (Free 25 searches/month): [Hunter.io API](https://hunter.io/api)

4. **Launch the Web Dashboard**:
   ```bash
   python app.py
   ```
   Open your browser to [http://localhost:8080](http://localhost:8080).

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
├── requirements.txt            # Python dependencies
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
