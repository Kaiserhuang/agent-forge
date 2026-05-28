import React, { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { useAppStore } from '../../stores/appStore'

const pageTitles: Record<string, string> = {
  '/chat': '对话',
  '/flow-editor': '流程编排',
  '/agents': 'Agent 管理',
  '/settings': '设置',
}

export const TopBar: React.FC = () => {
  const location = useLocation()
  const connected = useAppStore((s) => s.connected)
  const title = pageTitles[location.pathname] || 'AgentForge'

  return (
    <div className="topbar">
      <div className="topbar-title">{title}</div>
      <div className="topbar-status">
        <div className={`status-dot${connected ? ' connected' : ''}`} />
        {connected ? '已连接' : '未连接'}
      </div>
    </div>
  )
}
