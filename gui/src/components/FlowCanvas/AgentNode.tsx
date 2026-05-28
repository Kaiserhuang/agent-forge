import React, { memo } from 'react'
import { Handle, Position, type NodeProps } from 'reactflow'

type AgentNodeData = {
  label?: string
  agentId?: string
  input?: string
  skills?: string[]
  useBlackboard?: boolean
}

export const AgentNode: React.FC<NodeProps<AgentNodeData>> = memo(({ data, selected }) => {
  const hasSkills = data.skills && data.skills.length > 0

  return (
    <div
      style={{
        background: selected ? 'var(--bg-hover)' : 'var(--bg-secondary)',
        border: `1px solid ${selected ? 'var(--accent)' : 'var(--border)'}`,
        borderRadius: 10,
        padding: 0,
        minWidth: 180,
        boxShadow: selected ? '0 0 0 2px var(--accent-subtle)' : 'var(--shadow)',
        transition: 'all 0.15s',
      }}
    >
      {/* 输入连接点 */}
      <Handle
        type="target"
        position={Position.Left}
        style={{
          background: 'var(--accent)',
          width: 10,
          height: 10,
          border: '2px solid var(--bg-secondary)',
        }}
      />

      {/* 头部 */}
      <div
        style={{
          padding: '10px 14px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}
      >
        <div
          style={{
            width: 10,
            height: 10,
            borderRadius: '50%',
            background: data.useBlackboard ? 'var(--warning)' : 'var(--accent)',
            flexShrink: 0,
          }}
          title={data.useBlackboard ? '黑板模式' : '管道模式'}
        />
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
            {data.label || data.agentId || 'Agent'}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            {data.agentId || '未指定'}
          </div>
        </div>
      </div>

      {/* 详情 */}
      <div style={{ padding: '8px 14px' }}>
        {hasSkills && (
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>
            技能: {data.skills!.join(', ')}
          </div>
        )}
        <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'monospace', wordBreak: 'break-all' }}>
          {data.input && data.input.length > 40
            ? data.input.slice(0, 40) + '...'
            : data.input || '{user_input}'}
        </div>
      </div>

      {/* 输出连接点 */}
      <Handle
        type="source"
        position={Position.Right}
        style={{
          background: 'var(--accent)',
          width: 10,
          height: 10,
          border: '2px solid var(--bg-secondary)',
        }}
      />
    </div>
  )
})

AgentNode.displayName = 'AgentNode'
