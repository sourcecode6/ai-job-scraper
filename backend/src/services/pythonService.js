const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const logger = require('../logger');

let pythonProcess = null;

function startPythonService() {
  const nlpDir = path.join(__dirname, '../../nlp_service');
  const venvPython = process.platform === 'win32'
    ? path.join(nlpDir, 'venv_nlp/Scripts/python.exe')
    : path.join(nlpDir, 'venv_nlp/bin/python');

  if (!fs.existsSync(venvPython)) {
    logger.warn('Python virtual environment not found. Embedding generation will fall back to local JS transformers.', { path: venvPython });
    return;
  }

  logger.info('Starting local Python FastAPI embedding service...');

  // Spawn uvicorn server in the nlp_service directory
  pythonProcess = spawn(
    venvPython,
    ['-m', 'uvicorn', 'app:app', '--host', '127.0.0.1', '--port', '8000'],
    { cwd: nlpDir }
  );

  pythonProcess.stdout.on('data', (data) => {
    const output = data.toString().trim();
    if (output.includes('Uvicorn running on')) {
      logger.info('✅ Local Python FastAPI embedding service started successfully.');
    }
  });

  pythonProcess.stderr.on('data', (data) => {
    const errOutput = data.toString().trim();
    if (errOutput.includes('Error') || errOutput.includes('Exception')) {
      logger.error('Python service error', { output: errOutput });
    }
  });

  pythonProcess.on('close', (code) => {
    if (code !== 0 && code !== null) {
      logger.error(`Python service stopped with exit code ${code}`);
    } else {
      logger.info('Python service stopped.');
    }
  });

  // Ensure python process is killed on node exit
  process.on('exit', () => {
    stopPythonService();
  });

  process.on('SIGINT', () => {
    stopPythonService();
    process.exit(0);
  });

  process.on('SIGTERM', () => {
    stopPythonService();
    process.exit(0);
  });
}

function stopPythonService() {
  if (pythonProcess) {
    logger.info('Stopping local Python FastAPI service...');
    pythonProcess.kill('SIGTERM');
    pythonProcess = null;
  }
}

module.exports = { startPythonService, stopPythonService };
