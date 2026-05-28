/**
 * 后端通信服务
 *
 * 提供:
 * - WebSocket 连接管理（自动重连）
 * - REST API 调用
 * - 消息类型定义
 */

import { useAppStore } from '../stores/appStore'

// ---- 消息类型 ----

export interface WSMessage {
  type: string
  payload: Record<string, unknown>
  timestamp?: string
}

export interface AgentResultDTO {
  agent_id: string
  output: string
  iterations: number
  total_tokens: number
  token_usage?: Record<string, number> | null
  steps: unknown[]
  elapsed_seconds: number
  success: boolean
  error?: string | null
}

export interface FlowResultDTO {
  flow_name: string
  node_results: Record<string, AgentResultDTO>
  blackboard: Record<string, unknown>
  output: unknown
  total_tokens: number
  elapsed_seconds: number
  success: boolean
  error?: string | null
}

export interface SkillInfo {
  name: string
  description: string
}

// ---- WebSocket 客户端 ----

class BackendClient {
  private ws: WebSocket | null = null
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private messageHandlers: Map<string, Set<(payload: Record<string, unknown>) => void>> = new Map()

  async connect(): Promise<void> {
    const store = useAppStore.getState()

    // 获取 WebSocket 地址
    let wsUrl = 'ws://127.0.0.1:8765/ws'
    if (window.electronAPI) {
      wsUrl = await window.electronAPI.getWsUrl()
    }

    this.disconnect()

    this.ws = new WebSocket(wsUrl)

    this.ws.onopen = () => {
      console.log('[WS] 已连接')
      store.setConnected(true)
    }

    this.ws.onclose = () => {
      console.log('[WS] 连接关闭')
      store.setConnected(false)
      this.scheduleReconnect()
    }

    this.ws.onerror = (err) => {
      console.error('[WS] 错误:', err)
    }

    this.ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data)
        this.dispatch(msg.type, msg.payload)
      } catch (e) {
        console.error('[WS] 解析失败:', e)
      }
    }
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.onclose = null // 防止触发重连
      this.ws.close()
      this.ws = null
    }
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
  }

  private scheduleReconnect(): void {
    // 5 秒后自动重连
    this.reconnectTimer = setTimeout(() => {
      console.log('[WS] 尝试重连...')
      this.connect()
    }, 5000)
  }

  send(type: string, payload: Record<string, unknown> = {}): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type, payload, timestamp: new Date().toISOString() }))
    } else {
      console.warn('[WS] 未连接，消息丢弃:', type)
    }
  }

  // ---- 消息订阅 ----

  on(type: string, handler: (payload: Record<string, unknown>) => void): () => void {
    if (!this.messageHandlers.has(type)) {
      this.messageHandlers.set(type, new Set())
    }
    this.messageHandlers.get(type)!.add(handler)
    return () => this.messageHandlers.get(type)?.delete(handler)
  }

  private dispatch(type: string, payload: Record<string, unknown>): void {
    const handlers = this.messageHandlers.get(type)
    if (handlers) {
      handlers.forEach((h) => h(payload))
    }
  }

  // ---- 业务方法 ----

  async runAgentTask(task: string): Promise<void> {
    // WebSocket 方式
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.send('run_flow', { task })
      return
    }

    // REST API 回退
    console.log('[WS] 未连接，使用 REST API')
    try {
      const res = await fetch('http://127.0.0.1:8765/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task }),
      })
      const data = await res.json()
      if (data.status === 'ok' && data.result) {
        this.dispatch('flow_complete', data.result)
      } else {
        this.dispatch('flow_error', { error: data.error || '未知错误' })
      }
    } catch (e) {
      this.dispatch('flow_error', { error: String(e) })
    }
  }

  async listSkills(): Promise<SkillInfo[]> {
    return new Promise((resolve) => {
      const unsub = this.on('list_skills', (payload) => {
        unsub()
        resolve((payload.skills as SkillInfo[]) || [])
      })
      this.send('list_skills')
      // 超时回退
      setTimeout(() => {
        unsub()
        resolve([])
      }, 5000)
    })
  }
}

// 单例
export const backendClient = new BackendClient()
