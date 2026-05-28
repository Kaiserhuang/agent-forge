/**
 * Electron Preload 脚本
 *
 * 通过 contextBridge 安全地暴露主进程 API 到渲染进程
 */

import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('electronAPI', {
  /** 获取后端 HTTP 地址 */
  getBackendUrl: (): Promise<string> => ipcRenderer.invoke('get-backend-url'),

  /** 获取 WebSocket 地址 */
  getWsUrl: (): Promise<string> => ipcRenderer.invoke('get-ws-url'),

  /** 监听后端日志 */
  onBackendLog: (callback: (msg: string) => void) => {
    ipcRenderer.on('backend-log', (_event, msg: string) => callback(msg))
  },
})
