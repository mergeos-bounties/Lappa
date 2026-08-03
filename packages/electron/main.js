const { app, BrowserWindow, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');

let mainWindow = null;
let serverProcess = null;
const SERVER_PORT = 8199;
const SERVER_URL = `http://127.0.0.1:${SERVER_PORT}`;
const SERVER_STARTUP_TIMEOUT = 15000;

function getServerCommand() {
  // Try lappa CLI first, then python -m fallback
  const lappaPath = path.join(__dirname, '..', 'server', 'src');
  if (process.platform === 'win32') {
    return {
      cmd: 'python',
      args: ['-m', 'uvicorn', 'lappa.api:app', '--host', '127.0.0.1', '--port', String(SERVER_PORT), '--log-level', 'warning'],
      env: { ...process.env, PYTHONPATH: lappaPath }
    };
  }
  return {
    cmd: 'python3',
    args: ['-m', 'uvicorn', 'lappa.api:app', '--host', '127.0.0.1', '--port', String(SERVER_PORT), '--log-level', 'warning'],
    env: { ...process.env, PYTHONPATH: lappaPath }
  };
}

function startServer() {
  return new Promise((resolve, reject) => {
    const { cmd, args, env } = getServerCommand();
    console.log(`Starting Lappa server: ${cmd} ${args.join(' ')}`);

    serverProcess = spawn(cmd, args, {
      env,
      cwd: path.join(__dirname, '..', '..'),
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true
    });

    let startupOutput = '';
    serverProcess.stdout.on('data', (data) => { startupOutput += data; });
    serverProcess.stderr.on('data', (data) => { startupOutput += data; });

    serverProcess.on('error', (err) => {
      reject(new Error(`Failed to start server: ${err.message}`));
    });

    serverProcess.on('exit', (code) => {
      if (code !== 0 && code !== null) {
        reject(new Error(`Server exited with code ${code}: ${startupOutput.slice(-500)}`));
      }
    });

    // Poll until server is ready
    const startTime = Date.now();
    const poll = setInterval(() => {
      http.get(`${SERVER_URL}/health`, (res) => {
        if (res.statusCode === 200) {
          clearInterval(poll);
          resolve();
        }
      }).on('error', () => {
        if (Date.now() - startTime > SERVER_STARTUP_TIMEOUT) {
          clearInterval(poll);
          reject(new Error('Server startup timeout'));
        }
      });
    }, 500);
  });
}

function stopServer() {
  if (serverProcess) {
    serverProcess.kill();
    serverProcess = null;
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 900,
    minHeight: 600,
    title: 'Lappa IDE',
    icon: path.join(__dirname, 'assets', 'lappa-icon.png'),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    },
    backgroundColor: '#0b1220',
    show: false
  });

  // Show when ready to avoid white flash
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  mainWindow.loadURL(SERVER_URL);

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(async () => {
  try {
    await startServer();
    console.log('Server ready');
    createWindow();
  } catch (err) {
    console.error('Failed to start:', err.message);
    dialog.showErrorBox(
      'Lappa IDE — Server Error',
      `Could not start the Lappa server.\n\n${err.message}\n\nEnsure Python 3.11+ and lappa dependencies are installed:\npip install -e packages/server[api,gui]`
    );
    app.quit();
  }
});

app.on('window-all-closed', () => {
  stopServer();
  app.quit();
});

app.on('before-quit', () => {
  stopServer();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
