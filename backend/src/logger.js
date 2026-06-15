const winston = require('winston');
const path = require('path');
const fs = require('fs');

const logsDir = path.join(__dirname, '../../logs');
if (!fs.existsSync(logsDir)) fs.mkdirSync(logsDir, { recursive: true });

const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.json()
  ),
  transports: [
    // Console: human-readable
    new winston.transports.Console({
      format: winston.format.combine(
        winston.format.colorize(),
        winston.format.timestamp({ format: 'HH:mm:ss' }),
        winston.format.printf(({ timestamp, level, message, ...meta }) => {
          const metaStr = Object.keys(meta).length ? ' ' + JSON.stringify(meta) : '';
          return `[${timestamp}] ${level}: ${message}${metaStr}`;
        })
      ),
    }),
    // scrape.log — acquisition results
    new winston.transports.File({
      filename: path.join(logsDir, 'scrape.log'),
      level: 'info',
    }),
    // error.log — HTTP errors, degraded companies, email failures
    new winston.transports.File({
      filename: path.join(logsDir, 'error.log'),
      level: 'error',
    }),
    // nlp.log — embedding + skill extraction events
    new winston.transports.File({
      filename: path.join(logsDir, 'nlp.log'),
      level: 'info',
      format: winston.format.combine(
        winston.format.timestamp(),
        winston.format.json(),
        // Only write NLP-tagged entries to this file
        winston.format((info) => (info.logType === 'nlp' ? info : false))()
      ),
    }),
  ],
});

module.exports = logger;
