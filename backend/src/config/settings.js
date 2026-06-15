require('dotenv').config();

module.exports = {
  port: parseInt(process.env.PORT) || 3000,
  matchThreshold: parseFloat(process.env.MATCH_THRESHOLD) || 65.0,
  dataRetentionDays: parseInt(process.env.DATA_RETENTION_DAYS) || 3,
  scrapeIntervalHours: parseInt(process.env.SCRAPE_INTERVAL_HOURS) || 6,

  email: {
    user: process.env.EMAIL_USER || '',
    pass: process.env.EMAIL_PASS || '',
    notifyEmail: process.env.NOTIFY_EMAIL || process.env.EMAIL_USER || '',
  },
  userYoe: parseInt(process.env.USER_YOE) || 0,


  scraping: {
    globalRequestDelayMs: 3000,     // 1 req per 3s globally
    betweenCompaniesDelayMs: 10000, // 10s gap between companies
    crawlDelayDefaultMs: 5000,      // default if no Crawl-delay in robots.txt
    userAgent: 'AIJobScraperBot/1.0 (Personal use job tracker; not for commercial use)',
  },
};
