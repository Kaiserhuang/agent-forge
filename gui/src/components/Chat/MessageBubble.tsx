import React from 'react'
import type { ChatMessage } from '../../stores/appStore'

interface Props {
  message: ChatMessage
}

export const MessageBubble: React.FC<Props> = ({ message }) => {
  const isUser = message.role === 'user'
  const isSystem = message.role === 'system'

  // 简单 markdown-style 渲染
  const renderContent = (text: string) => {
    if (!text) return null
    // 代码块
    const parts = text.split(/(```[\s\S]*?```)/g)
    return parts.map((part, i) => {
      if (part.startsWith('```')) {
        const code = part.replace(/```(\w*)\n?/, '').replace(/```$/, '')
        const lang = part.match(/```(\w*)/)?.[1] || ''
        return (
          <pre
            key={i}
            style={{
              background: 'var(--bg-tertiary)',
              padding: 12,
              borderRadius: 6,
              overflow: 'auto',
              fontSize: 12,
              lineHeight: 1.5,
              margin: '4px 0',
            }}
          >
            {lang && <div style={{ color: 'var(--text-muted)', fontSize: 11, marginBottom: 4 }}>{lang}</div>}
            <code>{code}</code>
          </pre>
        )
      }
      // 换行转 <br/>
      return (
        <span key={i}>
          {part.split('\n').map((line, j) => (
            <React.Fragment key={j}>
              {j > 0 && <br />}
              {line}
            </React.Fragment>
          ))}
        </span>
      )
    })
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: isUser ? 'flex-end' : 'flex-start',
        maxWidth: '80%',
        alignSelf: isUser ? 'flex-end' : 'flex-start',
      }}
    >
      {/* 角色标签 */}
      <div
        style={{
          fontSize: 11,
          color: isSystem ? 'var(--warning)' : 'var(--text-muted)',
          marginBottom: 2,
          padding: '0 4px',
        }}
      >
        {isUser ? '你' : isSystem ? '系统' : 'Agent'}
      </div>

      {/* 气泡 */}
      <div
        style={{
          padding: '10px 14px',
          borderRadius: 12,
          background: isUser
            ? 'var(--accent)'
            : isSystem
            ? 'var(--bg-tertiary)'
            : 'var(--bg-secondary)',
          color: isUser ? 'white' : 'var(--text-primary)',
          border: isUser ? 'none' : '1px solid var(--border)',
          fontSize: 13,
          lineHeight: 1.6,
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
        }}
      >
        {renderContent(message.content)}
      </div>
    </div>
  )
}
