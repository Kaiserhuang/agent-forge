import React, { useEffect, useRef } from 'react'
import { useAppStore } from '../../stores/appStore'
import { backendClient } from '../../services/backend'
import { MessageBubble } from './MessageBubble'

export const ChatPage: React.FC = () => {
  const {
    messages,
    isRunning,
    addMessage,
    appendToLastAssistant,
    setRunning,
    agents,
    selectedAgentId,
  } = useAppStore()

  const [input, setInput] = React.useState('')
  const listRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const currentAgent = agents.find((a) => a.id === selectedAgentId)

  // 自动滚动到底部
  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [messages])

  // 监听 WebSocket 消息
  useEffect(() => {
    const unsub1 = backendClient.on('agent_message', (payload) => {
      const content = (payload.content as string) || ''
      const isDelta = payload.delta as boolean
      if (isDelta) {
        appendToLastAssistant(content)
      }
    })

    const unsub2 = backendClient.on('flow_complete', (payload) => {
      if (payload.output) {
        const output = payload.output as string
        if (output) {
          addMessage({
            id: `r-${Date.now()}`,
            role: 'assistant',
            content: output,
            timestamp: Date.now(),
          })
        }
      }
      setRunning(false)
    })

    const unsub3 = backendClient.on('flow_error', (payload) => {
      addMessage({
        id: `e-${Date.now()}`,
        role: 'assistant',
        content: `❌ 错误: ${(payload.error as string) || '未知错误'}`,
        timestamp: Date.now(),
      })
      setRunning(false)
    })

    return () => {
      unsub1()
      unsub2()
      unsub3()
    }
  }, [])

  const handleSend = async () => {
    const text = input.trim()
    if (!text || isRunning) return

    setInput('')

    addMessage({
      id: `u-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: Date.now(),
    })

    // 占位 assistant 消息（流式追加用）
    addMessage({
      id: `a-${Date.now()}`,
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
    })

    setRunning(true)
    backendClient.runAgentTask(text)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: 0, margin: -20 }}>
      {/* Agent 选择器 */}
      <div style={{ padding: '12px 20px', borderBottom: '1px solid var(--border)', display: 'flex', gap: 8, alignItems: 'center' }}>
        <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>当前 Agent:</span>
        <select
          value={selectedAgentId || ''}
          onChange={(e) => useAppStore.getState().selectAgent(e.target.value)}
          style={{ flex: 1, maxWidth: 200 }}
        >
          {agents.map((a) => (
            <option key={a.id} value={a.id}>{a.name}</option>
          ))}
        </select>
        {currentAgent && (
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            技能: {currentAgent.skills.join(', ') || '无'}
          </span>
        )}
      </div>

      {/* 消息列表 */}
      <div
        ref={listRef}
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '16px 20px',
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
        }}
      >
        {messages.length === 0 ? (
          <div className="empty-state">
            <span>👋</span>
            <div>向 Agent 提问开始对话</div>
            <div style={{ fontSize: 12 }}>支持 web_search / file_ops 技能</div>
          </div>
        ) : (
          messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))
        )}
        {isRunning && (
          <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: '4px 12px' }}>
            Agent 正在思考...
          </div>
        )}
      </div>

      {/* 输入框 */}
      <div style={{ padding: '12px 20px', borderTop: '1px solid var(--border)', background: 'var(--bg-secondary)' }}>
        <div style={{ display: 'flex', gap: 8 }}>
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isRunning ? '等待回复...' : '输入你的问题，Enter 发送，Shift+Enter 换行'}
            rows={2}
            style={{ flex: 1, minHeight: 40, maxHeight: 120 }}
            disabled={isRunning}
          />
          <button
            className="btn btn-primary"
            onClick={handleSend}
            disabled={isRunning || !input.trim()}
            style={{ alignSelf: 'flex-end', height: 40 }}
          >
            {isRunning ? '...' : '发送'}
          </button>
        </div>
      </div>
    </div>
  )
}
