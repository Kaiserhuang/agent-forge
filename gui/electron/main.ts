/**
 * Electron 主进程
 *
 * 职责:
 * 1. 创建浏览器窗口
 * 2. 启动 Python 后端子进程
 * 3. 窗口关闭时自动清理后端进程
 */

import { app, BrowserWindow, ipcMain } from 'electron'
import { ChildProcess, spawn } from 'child_process'
import path from 'path'

let mainWindow: BrowserWindow | null = null
let pythonProcess: ChildProcess | null = null

// Python 后端端口
const BACKEND_PORT = 8765
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`

function startPythonBackend(): void {
  const isDev = !app.isPackaged

  // 查找 Python 后端路径
  const backendDir = isDev
    ? path.join(__dirname, '..', '..', 'backend')
    : path.join(process.resourcesPath, 'backend')

  const scriptPath = path.join(backendDir, 'app.py')

  pythonProcess = spawn('python', [scriptPath, '--port', String(BACKEND_PORT)], {
    cwd: backendDir,
    stdio: ['pipe', 'pipe', 'pipe'],
    env: { ...process.env, PYTHONUNBUFFERED: '1' },
  })

  pythonProcess.stdout?.on('data', (data: Buffer) => {
    const text = data.toString()
    console.log(`[Python] ${text}`)
    // 发送日志到渲染进程
    mainWindow?.webContents.send('backend-log', text)
  })

  pythonProcess.stderr?.on('data', (data: Buffer) => {
    console.error(`[Python ERR] ${data.toString()}`)
  })

  pythonProcess.on('close', (code) => {
    console.log(`[Python] 进程退出, code=${code}`)
    pythonProcess = null
  })

  pythonProcess.on('error', (err) => {
    console.error(`[Python] 启动失败:`, err.message)
  })

  console.log(`[Electron] Python 后端已启动 (pid=${pythonProcess.pid})`)
}

function stopPythonBackend(): void {
  if (pythonProcess) {
    console.log('[Electron] 正在关闭 Python 后端...')
    pythonProcess.kill('SIGTERM')
    // 等 2 秒后强制关闭
    setTimeout(() => {
      if (pythonProcess) {
        pythonProcess.kill('SIGKILL')
        pythonProcess = null
      }
    }, 2000)
  }
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    title: 'AgentForge',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  // 开发模式加载 Vite 开发服务器
  if (process.env.VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL)
    mainWindow.webContents.openDevTools()
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'))
  }

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

// ---- IPC 处理 ----

ipcMain.handle('get-backend-url', () => {
  return BACKEND_URL
})

ipcMain.handle('get-ws-url', () => {
  return `ws://127.0.0.1:${BACKEND_PORT}/ws`
})

// ---- 应用生命周期 ----

app.whenReady().then(() => {
  // 先启动 Python 后端
  startPythonBackend()

  // 稍等后端启动再创建窗口
  setTimeout(() => {
    createWindow()
  }, 1500)

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('window-all-closed', () => {
  stopPythonBackend()
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('before-quit', () => {
  stopPythonBackend()
})
