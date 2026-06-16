import os
import smtplib
import re
import json
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def load_env():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.abspath(os.path.join(current_dir, '..', '.env'))
    if os.path.exists(env_path):
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        parts = line.split('=', 1)
                        if len(parts) == 2:
                            os.environ[parts[0].strip()] = parts[1].strip()
        except Exception as e:
            print(f"Error loading .env file in emails: {e}")

# Load environment on import
load_env()

def format_posted_date(posted_date):
    if not posted_date:
        return ''
    try:
        # Try ISO format
        s = posted_date.rstrip('Z')
        dt = datetime.fromisoformat(s)
        return dt.strftime('%b %d, %Y')
    except Exception:
        # Fallback to string as-is
        return posted_date

def send_job_digest(to_email, matches, user_yoe):
    email_user = os.environ.get('EMAIL_USER')
    email_pass = os.environ.get('EMAIL_PASS')

    if not email_user or not email_pass:
        print("Error: EMAIL_USER or EMAIL_PASS not configured in .env")
        return False

    date_str = datetime.now().strftime('%B %d, %Y')
    subject = f"🎯 {len(matches)} New Job Match{'es' if len(matches) > 1 else ''} — {date_str}"

    html = build_email_html(matches, date_str, user_yoe)
    text = build_email_text(matches, date_str, user_yoe)

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"AI Job Scraper <{email_user}>"
        msg['To'] = to_email

        msg.attach(MIMEText(text, 'plain', 'utf-8'))
        msg.attach(MIMEText(html, 'html', 'utf-8'))

        # Connect to Gmail SMTP
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(email_user, email_pass)
        server.sendmail(email_user, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Failed to send email digest to {to_email}: {e}")
        return False

def build_email_html(matches, date_str, user_yoe):
    cards = []
    for m in matches:
        score = m.get('match_score') or m.get('matchScore') or 0
        title = m.get('job_title') or m.get('jobTitle') or 'Unknown Title'
        company = m.get('company_name') or m.get('companyName') or ''
        location = m.get('location') or 'Not specified'
        apply_url = m.get('apply_url') or m.get('applyUrl') or '#'
        posted_date = m.get('posted_date') or m.get('postedDate') or ''
        
        skills_raw = m.get('skills_display') or m.get('skillsDisplay') or '[]'
        if isinstance(skills_raw, list):
            skills = skills_raw
        else:
            try:
                skills = json.loads(skills_raw) if skills_raw else []
            except Exception:
                skills = []

        required_yoe = m.get('required_yoe')
        if required_yoe is None:
            required_yoe = m.get('requiredYoe')

        score_color = '#22c55e' if score >= 80 else '#f59e0b' if score >= 65 else '#94a3b8'
        
        skill_tags = "".join([
            f'<span style="background:#1e293b;color:#94a3b8;padding:2px 8px;border-radius:12px;font-size:12px;margin:2px;display:inline-block;">{s}</span>'
            for s in skills[:8]
        ])

        yoe_warning_html = ''
        if required_yoe is not None:
            try:
                req_yoe_val = int(required_yoe)
                if req_yoe_val > user_yoe:
                    yoe_warning_html = f"""
                    <div style="background:#451a03;border:1px solid #d97706;color:#fcd34d;padding:6px 12px;border-radius:6px;font-size:12px;font-weight:600;margin-bottom:12px;display:inline-block;margin-top:2px;">
                      ⚠️ Experience Mismatch: Requires {req_yoe_val} years, you have {user_yoe}
                    </div>
                    """
                else:
                    yoe_warning_html = f"""
                    <div style="background:#064e3b;border:1px solid #059669;color:#a7f3d0;padding:6px 12px;border-radius:6px;font-size:12px;font-weight:600;margin-bottom:12px;display:inline-block;margin-top:2px;">
                      ✅ Experience Match: Requires {req_yoe_val} years, you have {user_yoe}
                    </div>
                    """
            except Exception:
                pass

        posted_str = format_posted_date(posted_date)
        date_badge_html = f' &nbsp;•&nbsp; 📅 {posted_str}' if posted_str else ''

        job_id_val = m.get('job_id') or m.get('jobId') or ''
        job_id_html = f' &nbsp;•&nbsp; <span style="font-family:monospace;background:#1e293b;color:#94a3b8;padding:2px 6px;border-radius:4px;font-size:12px;font-weight:bold;">{job_id_val}</span>' if job_id_val else ''

        card = f"""
      <div style="background:#0f172a;border:1px solid #1e293b;border-radius:12px;padding:20px;margin-bottom:16px;">
        <div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:8px;">
          <div>
            <div style="font-size:17px;font-weight:600;color:#f1f5f9;">{title}</div>
            <div style="font-size:14px;color:#64748b;margin-top:2px;">
              @ {company}{job_id_html}
            </div>
          </div>
          <div style="background:{score_color};color:#fff;padding:4px 12px;border-radius:20px;font-weight:700;font-size:14px;white-space:nowrap;">
            {score}% Match
          </div>
        </div>
        <div style="font-size:13px;color:#94a3b8;margin-bottom:10px;">
          📍 {location}{date_badge_html}
        </div>
        {yoe_warning_html}
        {f'<div style="margin-bottom:12px;">{skill_tags}</div>' if skill_tags else ''}
        <a href="{apply_url}" style="background:#6366f1;color:#fff;padding:8px 20px;border-radius:8px;text-decoration:none;font-size:13px;font-weight:600;display:inline-block;">
          Apply Now →
        </a>
      </div>
        """
        cards.append(card)

    cards_html = "\n".join(cards)
    
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#020617;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <div style="max-width:600px;margin:0 auto;padding:32px 16px;">

    <!-- Header -->
    <div style="text-align:center;margin-bottom:32px;">
      <div style="font-size:32px;margin-bottom:8px;">🎯</div>
      <h1 style="color:#f1f5f9;font-size:24px;font-weight:700;margin:0 0 8px;">
        {len(matches)} New Job Match{"es" if len(matches) > 1 else ""} Found
      </h1>
      <p style="color:#64748b;margin:0;font-size:14px;">{date_str}</p>
    </div>

    <!-- Job Cards -->
    {cards_html}

    <!-- Footer -->
    <div style="border-top:1px solid #1e293b;margin-top:24px;padding-top:20px;text-align:center;">
      <p style="color:#475569;font-size:12px;margin:0;">
        Generated by your local AI Job Scraper &nbsp;•&nbsp; Next check in ~6 hours
      </p>
    </div>
  </div>
</body>
</html>
"""

def build_email_text(matches, date_str, user_yoe):
    lines = [f"🎯 {len(matches)} New Job Matches — {date_str}", ""]
    for m in matches:
        score = m.get('match_score') or m.get('matchScore') or 0
        title = m.get('job_title') or m.get('jobTitle') or 'Unknown Title'
        company = m.get('company_name') or m.get('companyName') or ''
        location = m.get('location') or 'Not specified'
        apply_url = m.get('apply_url') or m.get('applyUrl') or ''
        required_yoe = m.get('required_yoe')
        if required_yoe is None:
            required_yoe = m.get('requiredYoe')
            
        yoe_warning_text = ''
        if required_yoe is not None:
            try:
                req_yoe_val = int(required_yoe)
                if req_yoe_val > user_yoe:
                    yoe_warning_text = f" | ⚠️ Experience: Requires {req_yoe_val} years, you have {user_yoe}"
                else:
                    yoe_warning_text = f" | ✅ Experience: Requires {req_yoe_val} years, you have {user_yoe}"
            except Exception:
                pass

        job_id_val = m.get('job_id') or m.get('jobId') or ''
        lines.append(f"{title} @ {company} (Job ID: {job_id_val})")
        lines.append(f"Match: {score}% | Location: {location}{yoe_warning_text}")
        lines.append(f"Apply: {apply_url}")
        lines.append("─" * 50)
        
    lines.append("")
    lines.append("Generated by your local AI Job Scraper. Next check in ~6 hours.")
    return "\n".join(lines)
