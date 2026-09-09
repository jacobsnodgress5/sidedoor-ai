import os
import sys
import sqlite3
from tabulate import tabulate
#overall this file displays the database using python script

#gets the file path of the project
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
# Prefer sidedoor_cache.db, fallback to netweave_cache.db for existing data
_default_db = os.path.join(PROJECT_ROOT, "sidedoor_cache.db")
if not os.path.exists(_default_db) and os.path.exists(os.path.join(PROJECT_ROOT, "netweave_cache.db")):
    _default_db = os.path.join(PROJECT_ROOT, "netweave_cache.db")
DB_PATH = os.environ.get("DB_PATH", _default_db)

#function to view the database
def view_database():
    #print error if the db file path is off
    if not os.path.exists(DB_PATH):
        print(f"[Error] Database file not found at: {DB_PATH}")
        return

    #seems to be sql functions for using sqlite3 on the path, rows and whatever a cursor is
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    #print horizontal line at title for how this file works, visualizing the database
    print("\n" + "=" * 80)
    print("SIDEDOOR AI: LOCAL DATABASE INSPECTOR")
    print(f"Database File: {DB_PATH}")
    print("=" * 80)

    # 0. View Profiles Table
    try:
        profiles = cursor.execute(
            "SELECT id, profile_name, full_name, is_active, alma_mater, is_configured FROM profiles ORDER BY id ASC"
        ).fetchall()
        print(f"\n[0] PROFILES / CAMPAIGNS ({len(profiles)} records):")
        if profiles:
            headers = ["ID", "Campaign Name", "User Name", "Active", "Alma Mater", "Configured"]
            rows = [
                [
                    p["id"],
                    p["profile_name"],
                    p["full_name"],
                    "★ YES" if p["is_active"] else "No",
                    p["alma_mater"] or "N/A",
                    "Yes" if p["is_configured"] else "Pending"
                ]
                for p in profiles
            ]
            print(tabulate(rows, headers=headers, tablefmt="grid"))
        else:
            print("  (Table is currently empty)")
    except Exception:
        pass

    # 1. View Companies Table, seems like cursor is for executing sql commands
    companies = cursor.execute(
        "SELECT domain, company_name, priority_tier, tech_stack, created_at FROM companies ORDER BY priority_tier ASC, created_at DESC"
    ).fetchall()

    print(f"\n[1] COMPANIES TABLE ({len(companies)} records):")
    if companies:
        headers = ["Domain", "Company Name", "Tier", "Tech Stack", "Created At"]
        rows = [
            [
                c["domain"],
                c["company_name"],
                f"Tier {c['priority_tier']} ({'Best Fit' if c['priority_tier'] == 1 else 'Other'})",
                c["tech_stack"] or "N/A",
                c["created_at"]
            ]
            for c in companies
        ]
        print(tabulate(rows, headers=headers, tablefmt="grid"))
    else:
        print("  (Table is currently empty)")

    # 2. View Contacts Table
    contacts = cursor.execute(
        "SELECT linkedin_url, company_domain, full_name, title, classification, relevance_score, outreach_status FROM contacts ORDER BY created_at DESC"
    ).fetchall()

    print(f"\n[2] CONTACTS TABLE ({len(contacts)} records):")
    if contacts:
        headers = ["Name", "Title", "Company Domain", "Class", "Score", "Status"]
        rows = [
            [
                ct["full_name"],
                ct["title"],
                ct["company_domain"],
                ct["classification"] or "N/A",
                ct["relevance_score"] or "N/A",
                ct["outreach_status"]
            ]
            for ct in contacts
        ]
        print(tabulate(rows, headers=headers, tablefmt="grid"))
    else:
        print("  (Table is currently empty)")

    print("\n" + "=" * 80 + "\n")
    conn.close()

if __name__ == "__main__":
    view_database()
