/**
 * 全局状态管理 (Zustand)
 */

import { create } from 'zustand'

// ---- 类型 ----

export interface AgentConfig {
  id: string
  name: string
  systemPrompt: string
  model: string
  skills: string[]
  temperature: number
}

export interface LLMConfig {
  apiKey: string
  model: string
  baseUrl: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: number
  agentId?: string
}

export interface FlowNodeConfig {
  id: string
  agentId: string
  input: string
  useBlackboard: boolean
  position: { x: number; y: number }
}

// ---- Store ----

interface AppState {
  // 连接状态
  connected: boolean
  backendUrl: string

  // LLM 配置
  llmConfig: LLMConfig

  // Agent 列表
  agents: AgentConfig[]
  selectedAgentId: string | null

  // 聊天
  messages: ChatMessage[]
  isRunning: boolean

  // Flow 编辑器
  flowNodes: FlowNodeConfig[]

  // Actions
  setConnected: (v: boolean) => void
  setBackendUrl: (url: string) => void
  setLlmConfig: (config: Partial<LLMConfig>) => void
  addAgent: (agent: AgentConfig) => void
  updateAgent: (id: string, config: Partial<AgentConfig>) => void
  removeAgent: (id: string) => void
  selectAgent: (id: string | null) => void
  addMessage: (msg: ChatMessage) => void
  appendToLastAssistant: (text: string) => void
  clearMessages: () => void
  setRunning: (v: boolean) => void
  setFlowNodes: (nodes: FlowNodeConfig[]) => void
  addFlowNode: (node: FlowNodeConfig) => void
  updateFlowNode: (id: string, config: Partial<FlowNodeConfig>) => void
  removeFlowNode: (id: string) => void
}

export const useAppStore = create<AppState>((set, get) => ({
  // 初始状态
  connected: false,
  backendUrl: 'http://127.0.0.1:8765',

  llmConfig: {
    apiKey: '',
    model: 'deepseek-chat',
    baseUrl: 'https://api.deepseek.com/v1',
  },

  agents: [
    {
      id: 'default',
      name: '默认助手',
      systemPrompt: '你是一个有用的 AI 助手。',
      model: 'deepseek-chat',
      skills: ['web_search', 'file_ops'],
      temperature: 0.7,
    },
  ],
  selectedAgentId: 'default',

  messages: [],
  isRunning: false,

  flowNodes: [],

  // Actions
  setConnected: (v) => set({ connected: v }),

  setBackendUrl: (url) => set({ backendUrl: url }),

  setLlmConfig: (config) =>
    set((s) => ({ llmConfig: { ...s.llmConfig, ...config } })),

  addAgent: (agent) =>
    set((s) => ({ agents: [...s.agents, agent] })),

  updateAgent: (id, config) =>
    set((s) => ({
      agents: s.agents.map((a) => (a.id === id ? { ...a, ...config } : a)),
    })),

  removeAgent: (id) =>
    set((s) => ({
      agents: s.agents.filter((a) => a.id !== id),
      selectedAgentId: s.selectedAgentId === id ? null : s.selectedAgentId,
    })),

  selectAgent: (id) => set({ selectedAgentId: id }),

  addMessage: (msg) =>
    set((s) => ({ messages: [...s.messages, msg] })),

  appendToLastAssistant: (text) =>
    set((s) => {
      const msgs = [...s.messages]
      const lastIdx = msgs.length - 1
      if (lastIdx >= 0 && msgs[lastIdx].role === 'assistant') {
        msgs[lastIdx] = { ...msgs[lastIdx], content: msgs[lastIdx].content + text }
      }
      return { messages: msgs }
    }),

  clearMessages: () => set({ messages: [] }),

  setRunning: (v) => set({ isRunning: v }),

  setFlowNodes: (nodes) => set({ flowNodes: nodes }),

  addFlowNode: (node) =>
    set((s) => ({ flowNodes: [...s.flowNodes, node] })),

  updateFlowNode: (id, config) =>
    set((s) => ({
      flowNodes: s.flowNodes.map((n) => (n.id === id ? { ...n, ...config } : n)),
    })),

  removeFlowNode: (id) =>
    set((s) => ({
      flowNodes: s.flowNodes.filter((n) => n.id !== id),
    })),
}))
