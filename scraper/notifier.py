import os
import smtplib
import yaml
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def build_html_report(best_fit_jobs, worse_fit_jobs, excluded_count=0):
    """
    Builds a clean, styled HTML email report.
    """
    today_str = datetime.now().strftime("%B %d, %Y")
    
    # CSS Styles for premium look
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                color: #333333;
                background-color: #f4f6f8;
                margin: 0;
                padding: 20px;
            }}
            .container {{
                max-width: 650px;
                margin: 0 auto;
                background: #ffffff;
                border-radius: 8px;
                padding: 30px;
                box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05);
            }}
            .header {{
                border-bottom: 2px solid #e1e4e6;
                padding-bottom: 15px;
                margin-bottom: 25px;
            }}
            .header h1 {{
                font-size: 22px;
                color: #0a66c2; /* LinkedIn Blue */
                margin: 0 0 5px 0;
            }}
            .header p {{
                font-size: 14px;
                color: #666666;
                margin: 0;
            }}
            .section {{
                margin-bottom: 30px;
            }}
            .section-title {{
                font-size: 18px;
                font-weight: bold;
                padding-bottom: 8px;
                border-bottom: 2px solid;
                margin-bottom: 15px;
            }}
            .best-fit-title {{
                color: #2e7d32; /* Green */
                border-color: #a5d6a7;
            }}
            .worse-fit-title {{
                color: #ef6c00; /* Orange */
                border-color: #ffcc80;
            }}
            .job-card {{
                background-color: #fafbfc;
                border: 1px solid #e1e4e6;
                border-radius: 6px;
                padding: 15px;
                margin-bottom: 15px;
                transition: transform 0.2s;
            }}
            .job-title {{
                font-size: 16px;
                font-weight: bold;
                margin: 0 0 5px 0;
            }}
            .job-title a {{
                color: #0a66c2;
                text-decoration: none;
            }}
            .job-title a:hover {{
                text-decoration: underline;
            }}
            .job-meta {{
                font-size: 13px;
                color: #555555;
                margin: 0 0 8px 0;
            }}
            .job-reason {{
                font-size: 12px;
                font-style: italic;
                color: #777777;
                background-color: #f0f2f5;
                padding: 6px 10px;
                border-radius: 4px;
                margin: 0;
            }}
            .no-jobs {{
                font-size: 14px;
                color: #888888;
                font-style: italic;
                padding: 10px;
            }}
            .footer {{
                font-size: 11px;
                color: #999999;
                text-align: center;
                border-top: 1px solid #e1e4e6;
                padding-top: 15px;
                margin-top: 30px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>LinkedIn Daily Curated Jobs</h1>
                <p>Report generated on {today_str}</p>
            </div>
    """

    # BEST FIT SECTION
    html += """
            <div class="section">
                <div class="section-title best-fit-title">✓ Best Fit Jobs</div>
    """
    if best_fit_jobs:
        for job in best_fit_jobs:
            html += f"""
                <div class="job-card">
                    <div class="job-title">
                        <a href="{job['url']}" target="_blank">{job['title']}</a>
                    </div>
                    <div class="job-meta">
                        <strong>{job['company']}</strong> &middot; {job['location']} &middot; 
                        <span style="color: #666;">{job['applicants']} applicants</span> (Query: '{job['query']}')
                    </div>
                    <p class="job-reason"><strong>Match Details:</strong> {job.get('reason', '')}</p>
                </div>
            """
    else:
        html += '<p class="no-jobs">No "Best Fit" jobs found in this run.</p>'
    html += "</div>"

    # WORSE FIT SECTION
    html += """
            <div class="section">
                <div class="section-title worse-fit-title">⚠ Worse Fit / Stretch Jobs</div>
    """
    if worse_fit_jobs:
        for job in worse_fit_jobs:
            html += f"""
                <div class="job-card">
                    <div class="job-title">
                        <a href="{job['url']}" target="_blank">{job['title']}</a>
                    </div>
                    <div class="job-meta">
                        <strong>{job['company']}</strong> &middot; {job['location']} &middot; 
                        <span style="color: #666;">{job['applicants']} applicants</span> (Query: '{job['query']}')
                    </div>
                    <p class="job-reason"><strong>Match Details:</strong> {job.get('reason', '')}</p>
                </div>
            """
    else:
        html += '<p class="no-jobs">No "Worse Fit / Stretch" jobs found in this run.</p>'
    html += "</div>"
    
    if excluded_count > 0:
        html += f"""
            <div style="text-align: center; margin-top: 25px; margin-bottom: 5px;">
                <a href="excluded_report.html" style="display: inline-block; padding: 10px 20px; background-color: #fff5f5; border: 1px solid #ffcdd2; border-radius: 6px; color: #c62828; text-decoration: none; font-weight: bold; font-size: 14px; transition: background-color 0.2s;">
                    View Excluded Jobs ({excluded_count}) &rarr;
                </a>
            </div>
        """

    # FOOTER
    html += """
            <div class="footer">
                This is an automated report. Customize your profile and target keywords in config.yaml.<br>
                UCLA Mathematics & Data Science Job Scraper &copy; 2026.
            </div>
        </div>
    </body>
    </html>
    """
    
    return html

def show_windows_notification(title, message):
    import subprocess
    # Clean message to avoid breaking PowerShell syntax
    clean_title = title.replace("'", "''")
    clean_message = message.replace("'", "''")
    
    ps_script = f"""
    [void][System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms');
    $notification = New-Object System.Windows.Forms.NotifyIcon;
    $notification.Icon = [System.Drawing.SystemIcons]::Information;
    $notification.BalloonTipIcon = 'Info';
    $notification.BalloonTipTitle = '{clean_title}';
    $notification.BalloonTipText = '{clean_message}';
    $notification.Visible = $True;
    $notification.ShowBalloonTip(7000);
    Start-Sleep -Seconds 2;
    $notification.Dispose();
    """
    try:
        subprocess.run(["powershell", "-WindowStyle", "Hidden", "-Command", ps_script], capture_output=True)
    except Exception as e:
        print(f"[Warning] Failed to show desktop notification: {e}")

def open_report_in_browser(report_path):
    import subprocess
    import webbrowser
    # Try calling start chrome to force it to open in Google Chrome
    try:
        print(f"[Notifier] Attempting to open in Chrome...")
        subprocess.Popen(f'start chrome "{report_path}"', shell=True)
        print(f"[Notifier] Opened report in Google Chrome.")
    except Exception as e:
        print(f"[Warning] Failed to force open in Chrome: {e}. Falling back to default browser...")
        try:
            webbrowser.open(f"file:///{report_path.replace(chr(92), '/')}")
            print(f"[Notifier] Automatically opened report in default browser.")
        except Exception as fallback_err:
            print(f"[ERROR] Failed to open browser: {fallback_err}")

def build_excluded_report(excluded_jobs):
    """
    Builds a clean, styled HTML report for excluded jobs.
    """
    today_str = datetime.now().strftime("%B %d, %Y")
    
    html = f"""<!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>LinkedIn Excluded Jobs - {today_str}</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                line-height: 1.5;
                background-color: #f6f8fa;
                color: #24292e;
                margin: 0;
                padding: 20px;
            }}
            .container {{
                max-width: 800px;
                margin: 0 auto;
                background-color: #ffffff;
                border: 1px solid #e1e4e6;
                border-radius: 6px;
                padding: 30px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.12);
            }}
            .back-link {{
                display: inline-block;
                margin-bottom: 20px;
                color: #0a66c2;
                text-decoration: none;
                font-weight: 500;
            }}
            .back-link:hover {{
                text-decoration: underline;
            }}
            .header {{
                border-bottom: 2px solid #e1e4e6;
                padding-bottom: 15px;
                margin-bottom: 25px;
            }}
            .header h1 {{
                font-size: 24px;
                margin: 0 0 5px 0;
                color: #d32f2f; /* Red */
            }}
            .header p {{
                font-size: 14px;
                color: #586069;
                margin: 0;
            }}
            .job-card {{
                background-color: #fafbfc;
                border: 1px solid #e1e4e6;
                border-radius: 6px;
                padding: 15px;
                margin-bottom: 15px;
            }}
            .job-title {{
                font-size: 16px;
                font-weight: bold;
                margin: 0 0 5px 0;
            }}
            .job-title a {{
                color: #24292e;
                text-decoration: none;
            }}
            .job-title a:hover {{
                color: #0a66c2;
                text-decoration: underline;
            }}
            .job-meta {{
                font-size: 13px;
                color: #555555;
                margin: 0 0 8px 0;
            }}
            .exclusion-reason {{
                font-size: 12px;
                font-style: italic;
                color: #721c24;
                background-color: #f8d7da;
                border: 1px solid #f5c6cb;
                padding: 6px 10px;
                border-radius: 4px;
                margin: 0;
            }}
            .no-jobs {{
                font-size: 14px;
                color: #888888;
                font-style: italic;
                padding: 10px;
            }}
            .footer {{
                font-size: 11px;
                color: #999999;
                text-align: center;
                border-top: 1px solid #e1e4e6;
                padding-top: 15px;
                margin-top: 30px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <a href="last_report.html" class="back-link">&larr; Back to Curated Dashboard</a>
            <div class="header">
                <h1>Excluded Jobs List</h1>
                <p>Report generated on {today_str} &middot; Total Excluded: {len(excluded_jobs)}</p>
            </div>
            
            <div class="section">
    """
    
    if excluded_jobs:
        for job in excluded_jobs:
            html += f"""
                <div class="job-card">
                    <div class="job-title">
                        <a href="{job.get('url', '#')}" target="_blank">{job.get('title', 'Unknown Title')}</a>
                    </div>
                    <div class="job-meta">
                        <strong>{job.get('company', 'Unknown Company')}</strong> &middot; {job.get('location', 'Unknown Location')} &middot; 
                        <span style="color: #666;">{job.get('applicants', 0)} applicants</span> (Query: '{job.get('query', '')}')
                    </div>
                    <p class="exclusion-reason"><strong>Exclusion Reason:</strong> {job.get('reason', '')}</p>
                </div>
            """
    else:
        html += '<p class="no-jobs">No excluded jobs in this run.</p>'
        
    html += """
            </div>
            <div class="footer">
                This is an automated local audit report. &copy; 2026.
            </div>
        </div>
    </body>
    </html>
    """
    return html

def send_email(best_fit_jobs, worse_fit_jobs, excluded_jobs=None):
    if excluded_jobs is None:
        excluded_jobs = []
        
    config = load_config()
    email_cfg = config.get("email", {})
    
    html_content = build_html_report(best_fit_jobs, worse_fit_jobs, len(excluded_jobs))
    
    # Save the local HTML file report
    backup_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "last_report.html"))
    with open(backup_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"[Notifier] Saved HTML report to '{backup_file}'")
    
    # Save the excluded HTML file report
    if excluded_jobs:
        excluded_html = build_excluded_report(excluded_jobs)
        excluded_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "excluded_report.html"))
        with open(excluded_file, "w", encoding="utf-8") as f:
            f.write(excluded_html)
        print(f"[Notifier] Saved excluded jobs report to '{excluded_file}'")
    
    # Check if email is enabled, otherwise use local desktop notifications
    email_enabled = email_cfg.get("enabled", False)
    if not email_enabled:
        print("[Notifier] Email is disabled in config.yaml. Showing local completion notification...")
        
        # Display desktop notification
        title = "LinkedIn Job Scraper Complete"
        msg = f"Found {len(best_fit_jobs)} Best Fit and {len(worse_fit_jobs)} Stretch jobs today! Caching into SideDoor..."
        show_windows_notification(title, msg)
        return True

    # Email Logic
    sender = email_cfg.get("sender", "jacobsnodgress5@gmail.com")
    receiver = email_cfg.get("receiver", "jacobsnodgress5@gmail.com")
    smtp_server = email_cfg.get("smtp_server", "smtp.gmail.com")
    smtp_port = email_cfg.get("smtp_port", 587)
    
    # Try reading the password from config.yaml first
    password = email_cfg.get("password")
    
    # Fallback to environment variable if empty
    pwd_env_var = email_cfg.get("password_env_var", "LINKEDIN_EMAIL_PASSWORD")
    if not password:
        password = os.environ.get(pwd_env_var)
        
    if not password:
        print(f"[WARNING] Email password env variable '{pwd_env_var}' not set. Cannot send email.")
        print("Please configure this environment variable or set it in config.yaml to enable email delivery.")
        # Fall back to local notification so the user doesn't miss the results
        print("[Notifier] Falling back to local Windows desktop notification...")
        show_windows_notification("LinkedIn Scraper (Fallback)", f"Found {len(best_fit_jobs)} Best Fit jobs! (Email password missing). Opening report...")
        open_report_in_browser(backup_file)
        return False
        
    msg = MIMEMultipart("alternative")
    today_str = datetime.now().strftime("%Y-%m-%d")
    msg["Subject"] = f"LinkedIn Daily Job Report ({len(best_fit_jobs)} Best, {len(worse_fit_jobs)} Stretch) - {today_str}"
    msg["From"] = sender
    msg["To"] = receiver
    
    # Attach HTML body
    msg.attach(MIMEText(html_content, "html"))
    
    try:
        print(f"[Notifier] Connecting to SMTP server {smtp_server}:{smtp_port}...")
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, receiver, msg.as_string())
        server.quit()
        print(f"[Notifier] Success! Email report sent to {receiver}.")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to send email via SMTP: {e}")
        return False

if __name__ == "__main__":
    # Offline test of email formatting
    test_best = [
        {"title": "Junior Data Scientist", "company": "SpaceX", "location": "Hawthorne, CA", "applicants": 12, "url": "https://linkedin.com", "query": "data scientist", "reason": "Matches Python/SQL stack perfectly and is local to LA."},
    ]
    test_stretch = [
        {"title": "Machine Learning Engineer I", "company": "Disney", "location": "Glendale, CA", "applicants": 38, "url": "https://linkedin.com", "query": "machine learning engineer", "reason": "Requires GCP and Spark (missing) but contains main PyTorch/Python model elements."}
    ]
    # Set mock password for local backup test
    os.environ["LINKEDIN_EMAIL_PASSWORD"] = "" 
    send_email(test_best, test_stretch)
