import os
import sys
import time
import urllib.parse
import yaml
from playwright.sync_api import sync_playwright

# Ensure UTF-8 stdout on Windows to prevent UnicodeEncodeError on emojis in titles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def parse_applicant_count(text):
    """
    Parses applicant count text. Examples:
    - "45 applicants" -> 45
    - "5 people clicked apply" / "1 person clicked apply" -> 5 / 1
    - "Over 200 applicants" / "Over 100 people clicked apply" -> 200 / 100
    - "Be among the first 10 applicants" -> 9
    - "Be among the first 25 applicants" -> 24
    - "Be an early applicant" -> 5
    - "1,500 applicants" -> 1500
    - "No applicants" -> 0
    Returns integer applicant count or 0 if not found.
    """
    if not text:
        return 0
    import re
    clean = text.lower().replace(",", "").strip()

    # Check for early applicant indicators without specific digits
    if "early applicant" in clean or "first applicant" in clean:
        return 5

    # 1. 'Be among the first X applicants'
    m_first = re.search(r'(?:first|among the first)\s*(\d+)\s*applicants?', clean)
    if m_first:
        return max(1, int(m_first.group(1)) - 1)

    # 2. 'Over X applicants' / 'More than X applicants' / 'Over X people clicked apply'
    m_over = re.search(r'(?:over|more than)\s*(\d+)\s*(?:people|person)?\s*(?:applied|applicants?|clicked\s+apply)', clean)
    if m_over:
        return int(m_over.group(1))

    # 3. 'X people/person clicked apply' / 'X applied' / 'X applicants'
    m_num = re.search(r'(\d+)\s*(?:\+|plus)?\s*(?:people|person)?\s*(?:clicked\s+apply|applied|applicants?)', clean)
    if m_num:
        return int(m_num.group(1))

    # 4. Fallback: digits followed anywhere by applicant/apply keywords
    m_fall = re.search(r'(\d+)\s*(?:people|person)?\s*(?:clicked\s+apply|applied|applicants?)', clean)
    if m_fall:
        return int(m_fall.group(1))

    return 0

def scrape_jobs():
    config = load_config()
    auth_file = os.path.join(os.path.dirname(__file__), "auth.json")
    
    if not os.path.exists(auth_file):
        raise FileNotFoundError("auth.json not found! Please run login.py first to authenticate.")

    search_cfg = config.get("search", {})
    keywords = search_cfg.get("keywords", [])
    geo_id = search_cfg.get("geo_id", "102448103")
    distance = search_cfg.get("distance", 50)
    time_range = search_cfg.get("time_range", "r86400")
    experience_levels = search_cfg.get("experience_levels", [2, 3])
    max_pages = search_cfg.get("max_pages", 1)
    
    scraped_jobs = []

    # Import progress overlay helper safely
    try:
        from progress_overlay import update_overlay
    except ImportError:
        update_overlay = None

    total_keywords = max(1, len(keywords))

    with sync_playwright() as p:
        # Launch browser in headless mode so no test windows pop up on screen
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            storage_state=auth_file,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        
        page = context.new_page()
        page.set_default_timeout(20000)
        
        for kw_idx, kw in enumerate(keywords):
            encoded_query = urllib.parse.quote(kw)
            query_jobs_count = 0
            
            try:
                for page_num in range(max_pages):
                    # Calculate progress percentage (10% to 55% during scraping)
                    pct = 10.0 + ((kw_idx + (page_num / max_pages)) / total_keywords) * 45.0
                    kw_clean = kw.split(" ")[0].capitalize() + " " + kw.split(" ")[1] if len(kw.split(" ")) > 1 else kw
                    status_msg = f"Scraping: {kw_clean} (Page {page_num + 1}/{max_pages})"
                    metric_msg = f"Jobs Scraped: {len(scraped_jobs)}"
                    if update_overlay:
                        update_overlay(pct, status_msg, metric_msg)

                    # Construct URL
                    url = f"https://www.linkedin.com/jobs/search/?keywords={encoded_query}&geoId={geo_id}&distance={distance}"
                    if time_range:
                        url += f"&f_TPR={time_range}"
                    if experience_levels:
                        exp_str = ",".join(map(str, experience_levels))
                        url += f"&f_E={urllib.parse.quote(exp_str)}"
                    
                    if page_num > 0:
                        url += f"&start={page_num * 25}"
                    
                    print(f"\n[Scraper] Navigating to search URL (Page {page_num + 1}): {url}")
                    page.goto(url)
                    page.wait_for_load_state("domcontentloaded")
                    time.sleep(2) # Fast load settlement
                    
                    if page_num == 0:
                        screenshot_path = os.path.join(os.path.dirname(__file__), f"search_{kw.replace(' ', '_')}.png")
                        try:
                            page.screenshot(path=screenshot_path)
                            print(f"[Scraper] Saved search page screenshot to '{screenshot_path}'")
                        except Exception as ss_err:
                            print(f"[Warning] Failed to take page screenshot: {ss_err}")
                    
                    if "login" in page.url:
                        print("[WARNING] Redirected to login page. Session in auth.json might have expired. Please rerun login.py.")
                        break
                    
                    no_jobs_el = page.query_selector(".jobs-search-two-pane__no-results-banner, .jobs-search-two-pane__no-results-title")
                    if no_jobs_el:
                        print(f"[Scraper] No jobs found for query: '{kw}' on page {page_num + 1}")
                        break
                    
                    rail_selector = ".jobs-search-results-list"
                    rail = page.query_selector(rail_selector)
                    if rail:
                        print("[Scraper] Fast-scrolling job rail...")
                        for i in range(10):
                            page.evaluate(f"document.querySelector('{rail_selector}').scrollTop = {i * 400}")
                            time.sleep(0.15)
                        time.sleep(0.5)
                    
                    # Extract job card links on the active page
                    job_cards = page.query_selector_all(".job-card-container, a.job-card-list__title, .jobs-search-results__list-item")
                    print(f"[Scraper] Found {len(job_cards)} job cards on page {page_num + 1}.")
                    
                    page_job_links = []
                    for card in job_cards:
                        link_el = card.query_selector("a[href*='/jobs/view/'], a[href*='linkedin.com/jobs/view/'], a.job-card-list__title, a.job-card-container__link")
                        if link_el:
                            href = link_el.get_attribute("href")
                            if href:
                                if not href.startswith("http"):
                                    href = "https://www.linkedin.com" + href
                                parsed_href = urllib.parse.urlparse(href)
                                clean_href = f"https://{parsed_href.netloc}{parsed_href.path}"
                            else:
                                continue
                            
                            import re
                            job_id_match = re.search(r'/view/(\d+)', clean_href)
                            job_id = job_id_match.group(1) if job_id_match else None
                            
                            title_el = card.query_selector("a.job-card-list__title, .job-card-list__title, .job-card-container__link")
                            title = title_el.inner_text().strip() if title_el else "Unknown Title"
                            title = title.split("\n")[0].strip()
                            
                            company_el = card.query_selector(".job-card-container__company-name, .artdeco-entity-lockup__subtitle, .job-card-container__primary-description")
                            company = company_el.inner_text().strip() if company_el else "Unknown Company"
                            company = company.split("\n")[0].strip()
                            
                            location_el = card.query_selector(".job-card-container__metadata-item, .job-card-list__metadata-item, [class*='metadata-item']")
                            card_location = "Unknown Location"
                            if location_el:
                                card_location = location_el.inner_text().strip()
                            else:
                                desc_el = card.query_selector(".job-card-container__primary-description")
                                if desc_el and desc_el.inner_text().strip() != company:
                                    card_location = desc_el.inner_text().strip()
                            card_location = card_location.split("·")[-1].strip() if location_el else "Unknown Location"
                            card_location = card_location.split("·")[-1].strip()
                            
                            if company == "Unknown Company" or title == "Unknown Title" or card_location == "Unknown Location" or not company or not title or not card_location:
                                card_text = card.inner_text()
                                lines = [line.strip() for line in card_text.split("\n") if line.strip()]
                                lines = [l for l in lines if "verification" not in l.lower() and "verify" not in l.lower()]
                                if len(lines) >= 3:
                                    if title == "Unknown Title" or not title:
                                        title = lines[0]
                                    if company == "Unknown Company" or not company:
                                        company = lines[1]
                                    if card_location == "Unknown Location" or not card_location:
                                        card_location = lines[2]
                            
                            if job_id and clean_href not in [j['url'] for j in scraped_jobs]:
                                page_job_links.append({
                                    "id": job_id,
                                    "url": clean_href,
                                    "title": title,
                                    "company": company,
                                    "location": card_location
                                })
                    
                    print(f"[Scraper] Extracted {len(page_job_links)} unique job links from page {page_num + 1}.")
                    if len(page_job_links) == 0:
                        break
                    
                    title_exclusions = config.get("exclusions", {}).get("job_titles", [])

                    # Loop through each job on the active page to get full details (limit to first 20 for query safety)
                    for index, job in enumerate(page_job_links[:20]):
                        # Dynamic Pre-filter: Skip clicking card if title has explicit exclusions (Senior, Lead, VP, Director, etc.)
                        title_lower = job['title'].lower()
                        is_excluded_title = False
                        for pattern in title_exclusions:
                            if re.search(r'\b' + re.escape(pattern.lower()) + r'\b', title_lower):
                                print(f"  [{index+1}/{len(page_job_links[:20])}] [PRE-SKIPPED: Excluded Title '{pattern}'] {job['title']} at {job['company']}")
                                is_excluded_title = True
                                break
                        if is_excluded_title:
                            continue

                        print(f"  [{index+1}/{len(page_job_links[:20])}] Loading details for job: {job['title']} at {job['company']}")
                        
                        card_el = page.query_selector(f"a[href*='{job['id']}']")
                        if card_el:
                            try:
                                card_el.click()
                                try:
                                    page.wait_for_selector(".jobs-description-content__text, #job-details, .jobs-description", timeout=1200)
                                except Exception:
                                    time.sleep(0.4)
                            except Exception as click_err:
                                print(f"    Failed to click card: {click_err}. Trying direct navigation...")
                                page.goto(job['url'], timeout=10000)
                                try:
                                    page.wait_for_selector(".jobs-description-content__text, #job-details, .jobs-description", timeout=1500)
                                except Exception:
                                    time.sleep(0.6)
                        else:
                            page.goto(job['url'], timeout=10000)
                            try:
                                page.wait_for_selector(".jobs-description-content__text, #job-details, .jobs-description", timeout=1500)
                            except Exception:
                                time.sleep(0.6)
                        
                        # Extract description
                        desc_el = page.query_selector(".jobs-description-content__text, #job-details, .jobs-description")
                        description = desc_el.inner_text().strip() if desc_el else ""
                        
                        # Extract applicant count with robust multi-tag search + page-text fallback
                        applicant_text = ""
                        for tag in ["span", "p", "div", "li", "strong"]:
                            candidate_elements = page.query_selector_all(f"{tag}:has-text('clicked apply'), {tag}:has-text('applicant'), {tag}:has-text('applied')")
                            for el in candidate_elements:
                                try:
                                    txt = el.inner_text().strip()
                                    # Target short metadata badges/lines, not the whole description
                                    if 0 < len(txt) < 140:
                                        cnt = parse_applicant_count(txt)
                                        if cnt > 0 or "early applicant" in txt.lower():
                                            applicant_text = txt
                                            break
                                except Exception:
                                    continue
                            if applicant_text:
                                break

                        if not applicant_text:
                            # Fallback: inspect the first 2500 characters of the page text (headers, subtitles, badges)
                            try:
                                body_sample = page.inner_text("body")[:2500]
                                for line in body_sample.split("\n"):
                                    line_clean = line.strip()
                                    if any(k in line_clean.lower() for k in ["applicant", "applied", "clicked apply"]):
                                        cnt = parse_applicant_count(line_clean)
                                        if cnt > 0 or "early applicant" in line_clean.lower():
                                            applicant_text = line_clean
                                            break
                            except Exception:
                                pass

                        applicants_count = parse_applicant_count(applicant_text)
                        print(f"    Applicants: {applicants_count} (Raw: '{applicant_text}')")
                        
                        # Extract location
                        loc_el = page.query_selector(".jobs-unified-top-card__bullet, .job-details-jobs-unified-top-card__subtitle-list")
                        location = "Unknown Location"
                        if loc_el:
                            location = loc_el.inner_text().strip()
                            parts = [p.strip() for p in location.split("·") if p.strip()]
                            if len(parts) > 1:
                                location = parts[1]
                        
                        if location == "Unknown Location" or not location:
                            location = job.get("location", "Unknown Location")
                        
                        scraped_jobs.append({
                            "id": job["id"],
                            "url": job["url"],
                            "title": job["title"],
                            "company": job["company"],
                            "location": location,
                            "description": description,
                            "applicants": applicants_count,
                            "query": kw
                        })
                        query_jobs_count += 1
                        
            except Exception as e:
                print(f"[ERROR] Error processing query '{kw}': {e}")
                screenshot_path = os.path.join(os.path.dirname(__file__), f"error_{kw.replace(' ', '_')}.png")
                try:
                    page.screenshot(path=screenshot_path)
                    print(f"[Scraper] Saved diagnostic screenshot to '{screenshot_path}'")
                except Exception as ss_err:
                    print(f"[Scraper] Failed to take screenshot: {ss_err}")
                
        browser.close()
        
    print(f"\n[Scraper] Successfully scraped {len(scraped_jobs)} jobs total.")
    return scraped_jobs

if __name__ == "__main__":
    try:
        jobs = scrape_jobs()
        print(f"Sample Job: {jobs[0] if jobs else 'None'}")
    except Exception as e:
        print(f"Scraper execution failed: {e}")
