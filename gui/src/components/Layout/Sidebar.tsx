import React from 'react'
import { NavLink } from 'react-router-dom'

interface NavItem {
  path: string
  label: string
  icon: string
}

const navItems: NavItem[] = [
  { path: '/chat', label: '对话', icon: '💬' },
  { path: '/flow-editor', label: '流程编排', icon: '🔀' },
  { path: '/agents', label: 'Agent 管理', icon: '🤖' },
  { path: '/skills', label: '技能管理', icon: '🧩' },
  { path: '/settings', label: '设置', icon: '⚙' },
]

export const Sidebar: React.FC = () => {
  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <div className="logo">AF</div>
        AgentForge
      </div>
      <nav className="sidebar-nav">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `nav-item${isActive ? ' active' : ''}`
            }
          >
            <span>{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="sidebar-footer">
        v0.1.0 · {navigator.platform.includes('Win') ? 'Windows' : 'Desktop'}
      </div>
    </div>
  )
}
