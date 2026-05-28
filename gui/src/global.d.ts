/** Electron preload 暴露的 API 类型 */
interface ElectronAPI {
  getBackendUrl: () => Promise<string>
  getWsUrl: () => Promise<string>
  onBackendLog: (callback: (msg: string) => void) => void
}

interface Window {
  electronAPI?: ElectronAPI
}
