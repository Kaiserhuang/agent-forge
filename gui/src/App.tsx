import React, { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { Sidebar } from './components/Layout/Sidebar'
import { TopBar } from './components/Layout/TopBar'
import { ChatPage } from './components/Chat/ChatPage'
import { FlowEditorPage } from './components/FlowCanvas/FlowEditorPage'
import { AgentManagerPage } from './components/AgentManager/AgentManagerPage'
import { SkillManagerPage } from './components/SkillManager/SkillManagerPage'
import { SettingsPage } from './components/Layout/SettingsPage'
import { backendClient } from './services/backend'

const App: React.FC = () => {
  // 自动连接 WebSocket
  useEffect(() => {
    backendClient.connect()
  }, [])

  return (
    <div className="app-layout">
      <Sidebar />
      <div className="main-content">
        <TopBar />
        <div className="page-content">
          <Routes>
            <Route path="/" element={<Navigate to="/chat" replace />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/chat/:agentId" element={<ChatPage />} />
            <Route path="/flow-editor" element={<FlowEditorPage />} />
            <Route path="/agents" element={<AgentManagerPage />} />
            <Route path="/skills" element={<SkillManagerPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </div>
      </div>
    </div>
  )
}

export default App
