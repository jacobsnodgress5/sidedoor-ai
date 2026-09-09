import os
import sys
import json
import sqlite3
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Dict, Any, Optional, List

# Ensure project root in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.db.db import (
    init_db,
    get_all_companies,
    get_all_contacts,
    get_contact,
    upsert_contact,
    update_contact_status,
    get_active_profile,
    get_profile_by_id,
    get_all_profiles,
    switch_active_profile,
    save_profile,
    delete_profile,
    get_local_profile,
    save_local_profile
)
from src.allocation_engine import run_daily_allocation

PORT = 8080
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

class SideDoorDashboardHandler(SimpleHTTPRequestHandler):
    """Local HTTP and REST API server handler for SideDoor AI Dashboard."""
    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        # Serve API endpoints
        if path == "/api/stats":
            active = get_active_profile()
            prof_id = active["id"] if active else 1
            self.send_json_response(self.get_stats(prof_id))
        elif path == "/api/companies":
            self.send_json_response(get_all_companies())
        elif path == "/api/contacts":
            active = get_active_profile()
            prof_id = active["id"] if active else 1
            status_filter = urllib.parse.parse_qs(parsed_url.query).get("status", [None])[0]
            self.send_json_response(get_all_contacts(status_filter, profile_id=prof_id))
        elif path == "/api/profiles":
            profs = get_all_profiles()
            active = get_active_profile()
            self.send_json_response({
                "profiles": profs,
                "active_id": active["id"] if active else 1
            })
        elif path == "/api/profile":
            query_id = urllib.parse.parse_qs(parsed_url.query).get("id", [None])[0]
            if query_id and query_id.isdigit():
                prof = get_profile_by_id(int(query_id))
            else:
                prof = get_active_profile()

            if not prof:
                self.send_json_response({"configured": False, "profile": {}})
            else:
                masked_prof = dict(prof)
                g_key = masked_prof.get("gemini_api_key") or ""
                h_key = masked_prof.get("hunter_api_key") or ""
                masked_prof["gemini_api_key_masked"] = (g_key[:6] + "..." + g_key[-4:]) if len(g_key) > 10 else ("***" if g_key else "")
                masked_prof["hunter_api_key_masked"] = (h_key[:4] + "..." + h_key[-4:]) if len(h_key) > 8 else ("***" if h_key else "")
                masked_prof["has_gemini_key"] = bool(g_key)
                masked_prof["has_hunter_key"] = bool(h_key)
                masked_prof["gemini_api_key"] = ""
                masked_prof["hunter_api_key"] = ""
                self.send_json_response({
                    "configured": bool(prof.get("is_configured", 0) and prof.get("full_name")),
                    "profile": masked_prof
                })
        elif path == "/" or path == "/index.html":
            self.serve_dashboard_html()
        else:
            super().do_GET()

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        
        try:
            data = json.loads(body)
        except Exception:
            data = {}

        if path == "/api/run-allocation":
            daily_cap = data.get("daily_cap", 20)
            active_prof = get_active_profile()
            prof_id = active_prof["id"] if active_prof else 1
            try:
                res = run_daily_allocation(daily_cap=daily_cap, profile_id=prof_id)
                self.send_json_response({"success": True, "result": res})
            except Exception as e:
                self.send_json_response({"success": False, "error": str(e)}, status_code=500)

        elif path == "/api/contacts/update":
            linkedin_url = data.get("linkedin_url")
            if not linkedin_url:
                self.send_json_response({"error": "Missing linkedin_url"}, status_code=400)
                return
            
            active_prof = get_active_profile()
            prof_id = active_prof["id"] if active_prof else 1
            contact = get_contact(linkedin_url)
            if not contact:
                self.send_json_response({"error": "Contact not found"}, status_code=404)
                return

            upsert_contact(
                linkedin_url=linkedin_url,
                company_domain=contact["company_domain"],
                full_name=data.get("full_name", contact["full_name"]),
                title=data.get("title", contact["title"]),
                email=data.get("email", contact["email"]),
                classification=data.get("classification", contact["classification"]),
                relevance_score=contact["relevance_score"],
                ai_hook=data.get("ai_hook", contact["ai_hook"]),
                draft_email=data.get("draft_email", contact["draft_email"]),
                draft_linkedin=data.get("draft_linkedin", contact["draft_linkedin"]),
                outreach_status=data.get("outreach_status", contact["outreach_status"]),
                sent_at=data.get("sent_at", contact.get("sent_at")),
                profile_id=prof_id
            )
            self.send_json_response({"success": True})

        elif path == "/api/contacts/set-status":
            linkedin_url = data.get("linkedin_url")
            status = data.get("status", "SENT")
            update_contact_status(linkedin_url, status)
            self.send_json_response({"success": True})

        elif path == "/api/profile":
            try:
                prof_id = data.get("id")
                if prof_id is not None and str(prof_id).isdigit():
                    prof_id = int(prof_id)
                else:
                    prof_id = None
                updated = save_profile(data, profile_id=prof_id)
                if data.get("gemini_api_key"):
                    os.environ["GEMINI_API_KEY"] = data["gemini_api_key"].strip()
                if data.get("hunter_api_key"):
                    os.environ["HUNTER_API_KEY"] = data["hunter_api_key"].strip()
                self.send_json_response({"success": True, "profile": updated})
            except Exception as e:
                self.send_json_response({"success": False, "error": str(e)}, status_code=500)

        elif path == "/api/profiles/switch":
            prof_id = data.get("profile_id")
            if not prof_id:
                self.send_json_response({"error": "Missing profile_id"}, status_code=400)
                return
            switched = switch_active_profile(int(prof_id))
            if switched and switched.get("gemini_api_key"):
                os.environ["GEMINI_API_KEY"] = switched["gemini_api_key"].strip()
            if switched and switched.get("hunter_api_key"):
                os.environ["HUNTER_API_KEY"] = switched["hunter_api_key"].strip()
            self.send_json_response({"success": True, "active_profile": switched})

        elif path == "/api/profiles/delete":
            prof_id = data.get("profile_id")
            if not prof_id:
                self.send_json_response({"error": "Missing profile_id"}, status_code=400)
                return
            success = delete_profile(int(prof_id))
            active = get_active_profile()
            self.send_json_response({"success": success, "active_profile": active})

        elif path == "/api/profile/parse-resume":
            raw_text = (data.get("text") or data.get("resume_text") or "").strip()
            if not raw_text:
                self.send_json_response({"error": "No resume text provided"}, status_code=400)
                return

            try:
                from src.config import get_gemini_client, DEFAULT_MODEL
                from google.genai import types

                client = get_gemini_client()
                prompt = f"""
                You are an expert technical talent assistant. Analyze the resume or LinkedIn text below and extract profile info for a job seeker.

                Text:
                \"\"\"{raw_text[:4000]}\"\"\"

                Return ONLY valid JSON matching this schema:
                {{
                    "full_name": "Full name",
                    "email": "Email address if found, else empty",
                    "linkedin_url": "LinkedIn profile URL if found, else empty",
                    "alma_mater": "University or College name",
                    "degree_major": "Degree and major, e.g. B.S. in Computer Science",
                    "grad_year": "Graduation year e.g. 2026",
                    "bio_summary": "2-sentence concise summary of background and strengths",
                    "skills": "Top 6-8 technical skills comma separated",
                    "target_roles": "3-4 target job titles comma separated",
                    "target_locations": "Current or preferred cities/states comma separated, e.g. San Francisco, CA; Remote"
                }}
                """
                resp = client.models.generate_content(
                    model=DEFAULT_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.1
                    )
                )
                parsed = json.loads(resp.text)
                self.send_json_response({"success": True, "extracted": parsed})
            except Exception as e:
                self.send_json_response({"success": False, "error": str(e)}, status_code=500)
        else:
            self.send_response(404)
            self.end_headers()

    def send_json_response(self, data: Any, status_code: int = 200):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode("utf-8"))

    def get_stats(self, profile_id: Optional[int] = None) -> Dict:
        companies = get_all_companies()
        contacts = get_all_contacts(profile_id=profile_id)
        drafted = [c for c in contacts if c.get("outreach_status") == "DRAFTED"]
        sent = [c for c in contacts if c.get("outreach_status") == "SENT"]
        return {
            "total_companies": len(companies),
            "tier_1_companies": len([c for c in companies if c.get("priority_tier") == 1]),
            "total_contacts": len(contacts),
            "drafted_count": len(drafted),
            "sent_count": len(sent)
        }

    def serve_dashboard_html(self):
        html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
        if os.path.exists(html_path):
            with open(html_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

def is_port_in_use(port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0

def start_server(port: int = PORT, max_attempts: int = 10):
    init_db()
    current_port = port
    while is_port_in_use(current_port) and current_port < port + max_attempts:
        print(f"[SideDoor Server] Port {current_port} is already in use by another process. Trying {current_port + 1}...")
        current_port += 1

    server_address = ("", current_port)
    httpd = HTTPServer(server_address, SideDoorDashboardHandler)

    try:
        with open(".active_port", "w", encoding="utf-8") as f:
            f.write(str(current_port))
    except Exception:
        pass

    print(f"\n" + "=" * 70)
    print(f"SIDEDOOR AI DASHBOARD RUNNING")
    print(f"Open in your browser: http://localhost:{current_port}")
    print("=" * 70 + "\n")
    httpd.serve_forever()

if __name__ == "__main__":
    start_server()
