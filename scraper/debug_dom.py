import os
from playwright.sync_api import sync_playwright

def debug_card_dom():
    auth_file = "auth.json"
    if not os.path.exists(auth_file):
        print("auth.json not found!")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=auth_file)
        page = context.new_page()
        
        # Navigate to a job search page
        url = "https://www.linkedin.com/jobs/search/?keywords=data+analyst&geoId=102448103&distance=50&f_TPR=r86400&f_E=2%2C3"
        print(f"Navigating to: {url}")
        page.goto(url)
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(5000)
        
        # Find first job card
        card = page.query_selector(".job-card-container, a.job-card-list__title, .jobs-search-results__list-item")
        if card:
            print("\n--- FIRST CARD OUTER HTML ---")
            print(card.evaluate("el => el.outerHTML"))
            print("------------------------------")
        else:
            print("No job card found on page!")
            
        browser.close()

if __name__ == "__main__":
    debug_card_dom()
