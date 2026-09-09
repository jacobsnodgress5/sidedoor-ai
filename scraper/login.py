import os
import sys
import json
from playwright.sync_api import sync_playwright

def save_cookie_auth_state(li_at_value, auth_file):
    # Construct Playwright compatible storage state
    state = {
        "cookies": [
            {
                "name": "li_at",
                "value": li_at_value,
                "domain": ".www.linkedin.com",
                "path": "/",
                "expires": 2524608000.0,
                "httpOnly": True,
                "secure": True,
                "sameSite": "None"
            }
        ],
        "origins": []
    }
    
    with open(auth_file, "w") as f:
        json.dump(state, f, indent=2)
    print(f"\n[SUCCESS] Session successfully saved to '{os.path.abspath(auth_file)}'.")

def run_login():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    auth_file = os.path.join(script_dir, "auth.json")
    
    print("=" * 60)
    print("LINKEDIN SCRA-FILTER ONE-TIME LOGIN HELPER")
    print("=" * 60)
    print("Please choose an authentication method:")
    print("1) Open headed browser (might not work if running in a background service)")
    print("2) Copy-paste session cookie (manual fallback - 100% reliable)")
    print("-" * 60)
    
    choice = input("Enter choice (1 or 2): ").strip()
    
    if choice == "2":
        print("\nManual Cookie Instructions:")
        print("1. Open LinkedIn in your regular browser (Chrome, Edge, Firefox).")
        print("2. Make sure you are logged in.")
        print("3. Open Developer Tools (Press F12, or right-click -> Inspect).")
        print("4. Go to the 'Application' tab (Chrome/Edge) or 'Storage' (Firefox).")
        print("5. Expand 'Cookies' in the left menu and select 'https://www.linkedin.com'.")
        print("6. Look for the cookie named 'li_at' and copy its Value.")
        print("-" * 60)
        li_at = input("Paste the 'li_at' cookie value here: ").strip()
        if not li_at:
            print("[ERROR] Cookie value cannot be empty.")
            return
        save_cookie_auth_state(li_at, auth_file)
    else:
        print("\nOpening headed browser window...")
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = context.new_page()
                page.goto("https://www.linkedin.com/login")
                
                input("\nPress ENTER here once you are logged in and see your homepage feed...")
                
                context.storage_state(path=auth_file)
                print(f"\n[SUCCESS] Session successfully saved to '{os.path.abspath(auth_file)}'.")
                browser.close()
        except Exception as e:
            print(f"\n[ERROR] Browser login failed: {e}")
            print("Please retry using Option 2 (Manual Cookie) instead.")

if __name__ == "__main__":
    try:
        run_login()
    except Exception as e:
        print(f"\n[ERROR] An error occurred: {e}", file=sys.stderr)
        input("\nPress ENTER to exit...")

