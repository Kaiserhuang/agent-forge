import React, { useState, useEffect } from 'react'
import { useAppStore } from '../../stores/appStore'

const LS_KEY = 'agentforge_settings'

function loadSettings(): Record<string, string> {
  try {
    return JSON.parse(localStorage.getItem(LS_KEY) || '{}')
  } catch { return {} }
}

function saveSettings(data: Record<string, string>) {
  const cur = loadSettings()
  localStorage.setItem(LS_KEY, JSON.stringify({ ...cur, ...data }))
}

export const SettingsPage: React.FC = () => {
  const { backendUrl, setBackendUrl, llmConfig, setLlmConfig } = useAppStore()
  const savedSettings = loadSettings()
  const [apiKey, setApiKey] = useState(savedSettings.apiKey || llmConfig.apiKey || '')
  const [model, setModel] = useState(savedSettings.model || llmConfig.model || 'deepseek-chat')
  const [saved, setSaved] = useState(false)
  const [keySent, setKeySent] = useState(false)

  // 启动时自动从 localStorage 恢复并发送到后端
  useEffect(() => {
    const stored = loadSettings()
    if (stored.apiKey) {
      setLlmConfig({ apiKey: stored.apiKey, model: stored.model || 'deepseek-chat' })
      fetch('http://127.0.0.1:8765/api/update-key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: stored.apiKey, model: stored.model || 'deepseek-chat' }),
      }).catch(() => {})
    }
  }, [])

  const handleSave = () => {
    saveSettings({ apiKey, model })
    setLlmConfig({ apiKey, model })
    fetch('http://127.0.0.1:8765/api/update-key', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: apiKey, model }),
    })
      .then(r => r.json())
      .then(() => setKeySent(true))
      .catch(() => {})
      .finally(() => setTimeout(() => setKeySent(false), 3000))
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <div style={{ maxWidth: 600 }}>
      <h2 style={{ marginBottom: 20, fontSize: 18 }}>全局设置</h2>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-header">DeepSeek API 配置</div>

        <div style={{ marginBottom: 12 }}>
          <label style={{ display: 'block', marginBottom: 4, color: 'var(--text-secondary)', fontSize: 12 }}>
            API Key
          </label>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="sk-..."
            style={{ width: '100%' }}
          />
        </div>

        <div style={{ marginBottom: 12 }}>
          <label style={{ display: 'block', marginBottom: 4, color: 'var(--text-secondary)', fontSize: 12 }}>
            模型
          </label>
          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            style={{ width: '100%' }}
          >
            <option value="deepseek-chat">DeepSeek Chat</option>
            <option value="deepseek-reasoner">DeepSeek Reasoner</option>
          </select>
        </div>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <button className="btn btn-primary" onClick={handleSave}>
            {saved ? '✓ 已保存' : '保存配置'}
          </button>
          {keySent && <span style={{ fontSize: 12, color: 'var(--success)' }}>已发送到后端</span>}
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-header">后端连接</div>
        <div style={{ marginBottom: 12 }}>
          <label style={{ display: 'block', marginBottom: 4, color: 'var(--text-secondary)', fontSize: 12 }}>
            后端地址
          </label>
          <input
            type="text"
            value={backendUrl}
            onChange={(e) => setBackendUrl(e.target.value)}
            style={{ width: '100%' }}
          />
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          WebSocket: ws://127.0.0.1:8765/ws
        </div>
      </div>
    </div>
  )
}
