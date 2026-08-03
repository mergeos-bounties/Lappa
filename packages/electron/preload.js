const { contextBridge } = require('electron');

// Expose minimal Electron API to the renderer
contextBridge.exposeInMainWorld('lappaDesktop', {
  platform: process.platform,
  version: process.versions.electron,
  isDesktop: true
});
