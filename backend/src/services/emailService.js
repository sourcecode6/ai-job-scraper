const nodemailer = require('nodemailer');
const settings = require('../config/settings');
const logger = require('../logger');

let transporter = null;

function getTransporter() {
  if (!transporter) {
    transporter = nodemailer.createTransport({
      service: 'gmail',
      auth: {
        user: settings.email.user,
        pass: settings.email.pass,
      },
    });
  }
  return transporter;
}

function formatPostedDate(postedDate) {
  if (!postedDate) return '';
  const parsed = Date.parse(postedDate);
  if (isNaN(parsed)) {
    // If it's a relative string like "Posted Today", return it directly
    return postedDate;
  }
  return new Date(postedDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

/**
 * Sends a job match digest email.
 * @param {string} toEmail - Recipient email address
 * @param {Array} matches - Array of matched job objects
 * @returns {boolean} true if sent successfully
 */
async function sendJobDigest(toEmail, matches) {
  if (!settings.email.user || !settings.email.pass) {
    logger.error('Email credentials not configured in .env');
    return false;
  }

  const date = new Date().toLocaleDateString('en-US', {
    year: 'numeric', month: 'long', day: 'numeric',
  });
  const subject = `🎯 ${matches.length} New Job Match${matches.length > 1 ? 'es' : ''} — ${date}`;

  const html = buildEmailHtml(matches, date);
  const text = buildEmailText(matches, date);

  try {
    await getTransporter().sendMail({
      from: `"AI Job Scraper" <${settings.email.user}>`,
      to: toEmail,
      subject,
      html,
      text,
    });
    return true;
  } catch (err) {
    logger.error('Failed to send email digest', { to: toEmail, error: err.message });
    return false;
  }
}

function buildEmailHtml(matches, date) {
  const cards = matches.map((m) => {
    const score = m.matchScore || m.match_score || 0;
    const title = m.jobTitle || m.job_title || 'Unknown Title';
    const company = m.companyName || m.company_name || '';
    const location = m.location || 'Not specified';
    const applyUrl = m.applyUrl || m.apply_url || '#';
    const postedDate = m.postedDate || m.posted_date || '';
    const skillsRaw = m.skillsDisplay || m.skills_display || '[]';
    const skills = Array.isArray(skillsRaw) ? skillsRaw : JSON.parse(skillsRaw || '[]');
    const requiredYoe = m.requiredYoe !== undefined ? m.requiredYoe : (m.required_yoe !== undefined ? m.required_yoe : null);
    const userYoe = settings.userYoe;

    const scoreColor = score >= 80 ? '#22c55e' : score >= 65 ? '#f59e0b' : '#94a3b8';
    const skillTags = skills.slice(0, 8).map((s) =>
      `<span style="background:#1e293b;color:#94a3b8;padding:2px 8px;border-radius:12px;font-size:12px;margin:2px;display:inline-block;">${s}</span>`
    ).join('');

    let yoeWarningHtml = '';
    if (requiredYoe !== null) {
      if (requiredYoe > userYoe) {
        yoeWarningHtml = `
          <div style="background:#451a03;border:1px solid #d97706;color:#fcd34d;padding:6px 12px;border-radius:6px;font-size:12px;font-weight:600;margin-bottom:12px;display:inline-block;margin-top:2px;">
            ⚠️ Experience Mismatch: Requires ${requiredYoe} years, you have ${userYoe}
          </div>
        `;
      } else {
        yoeWarningHtml = `
          <div style="background:#064e3b;border:1px solid #059669;color:#a7f3d0;padding:6px 12px;border-radius:6px;font-size:12px;font-weight:600;margin-bottom:12px;display:inline-block;margin-top:2px;">
            ✅ Experience Match: Requires ${requiredYoe} years, you have ${userYoe}
          </div>
        `;
      }
    }

    return `
      <div style="background:#0f172a;border:1px solid #1e293b;border-radius:12px;padding:20px;margin-bottom:16px;">
        <div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:8px;">
          <div>
            <div style="font-size:17px;font-weight:600;color:#f1f5f9;">${title}</div>
            <div style="font-size:14px;color:#64748b;margin-top:2px;">
              @ ${company} &nbsp;•&nbsp; <span style="font-family:monospace;background:#1e293b;color:#94a3b8;padding:2px 6px;border-radius:4px;font-size:12px;font-weight:bold;">${m.jobId || m.job_id}</span>
            </div>
          </div>
          <div style="background:${scoreColor};color:#fff;padding:4px 12px;border-radius:20px;font-weight:700;font-size:14px;white-space:nowrap;">
            ${score}% Match
          </div>
        </div>
        <div style="font-size:13px;color:#94a3b8;margin-bottom:10px;">
          📍 ${location}${postedDate ? ' &nbsp;•&nbsp; 📅 ' + formatPostedDate(postedDate) : ''}
        </div>
        ${yoeWarningHtml}
        ${skillTags ? `<div style="margin-bottom:12px;">${skillTags}</div>` : ''}
        <a href="${applyUrl}" style="background:#6366f1;color:#fff;padding:8px 20px;border-radius:8px;text-decoration:none;font-size:13px;font-weight:600;display:inline-block;">
          Apply Now →
        </a>
      </div>
    `;
  }).join('');

  return `
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
    <body style="margin:0;padding:0;background:#020617;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
      <div style="max-width:600px;margin:0 auto;padding:32px 16px;">

        <!-- Header -->
        <div style="text-align:center;margin-bottom:32px;">
          <div style="font-size:32px;margin-bottom:8px;">🎯</div>
          <h1 style="color:#f1f5f9;font-size:24px;font-weight:700;margin:0 0 8px;">
            ${matches.length} New Job Match${matches.length > 1 ? 'es' : ''} Found
          </h1>
          <p style="color:#64748b;margin:0;font-size:14px;">${date}</p>
        </div>

        <!-- Job Cards -->
        ${cards}

        <!-- Footer -->
        <div style="border-top:1px solid #1e293b;margin-top:24px;padding-top:20px;text-align:center;">
          <p style="color:#475569;font-size:12px;margin:0;">
            Generated by your local AI Job Scraper &nbsp;•&nbsp; Next check in ~6 hours
          </p>
        </div>
      </div>
    </body>
    </html>
  `;
}

function buildEmailText(matches, date) {
  const lines = [`🎯 ${matches.length} New Job Matches — ${date}`, ''];
  const userYoe = settings.userYoe;
  for (const m of matches) {
    const score = m.matchScore || m.match_score || 0;
    const title = m.jobTitle || m.job_title || 'Unknown Title';
    const company = m.companyName || m.company_name || '';
    const location = m.location || 'Not specified';
    const applyUrl = m.applyUrl || m.apply_url || '';
    const requiredYoe = m.requiredYoe !== undefined ? m.requiredYoe : (m.required_yoe !== undefined ? m.required_yoe : null);

    let yoeWarningText = '';
    if (requiredYoe !== null) {
      if (requiredYoe > userYoe) {
        yoeWarningText = ` | ⚠️ Experience: Requires ${requiredYoe} years, you have ${userYoe}`;
      } else {
        yoeWarningText = ` | ✅ Experience: Requires ${requiredYoe} years, you have ${userYoe}`;
      }
    }

    lines.push(`${title} @ ${company} (Job ID: ${m.jobId || m.job_id})`);
    lines.push(`Match: ${score}% | Location: ${location}${yoeWarningText}`);
    lines.push(`Apply: ${applyUrl}`);
    lines.push('─'.repeat(50));
  }
  lines.push('', 'Generated by your local AI Job Scraper. Next check in ~6 hours.');
  return lines.join('\n');
}

module.exports = { sendJobDigest };
