import React, { useState } from 'react'
import { useAppStore, type AgentConfig } from '../../stores/appStore'

const AVAILABLE_SKILLS = ['web_search', 'file_ops', 'code_exec', 'memory_ops']

export const AgentManagerPage: React.FC = () => {
  const { agents, addAgent, updateAgent, removeAgent } = useAppStore()
  const [editingId, setEditingId] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)

  // 新建表单
  const [form, setForm] = useState<AgentConfig>({
    id: '',
    name: '',
    systemPrompt: '你是一个有用的 AI 助手。',
    model: 'deepseek-chat',
    skills: [],
    temperature: 0.7,
  })

  const handleCreate = () => {
    if (!form.id.trim() || !form.name.trim()) return
    addAgent({ ...form, id: form.id.trim().toLowerCase().replace(/\s+/g, '_') })
    setForm({ id: '', name: '', systemPrompt: '你是一个有用的 AI 助手。', model: 'deepseek-chat', skills: [], temperature: 0.7 })
    setShowForm(false)
  }

  const toggleSkill = (skill: string) => {
    setForm((f) => ({
      ...f,
      skills: f.skills.includes(skill)
        ? f.skills.filter((s) => s !== skill)
        : [...f.skills, skill],
    }))
  }

  return (
    <div style={{ maxWidth: 800 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h2 style={{ fontSize: 18 }}>Agent 管理 ({agents.length})</h2>
        <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>
          {showForm ? '取消' : '+ 新建 Agent'}
        </button>
      </div>

      {/* 新建表单 */}
      {showForm && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-header">新建 Agent</div>
          <AgentFormFields form={form} setForm={setForm} toggleSkill={toggleSkill} />
          <button className="btn btn-primary" onClick={handleCreate} style={{ marginTop: 12 }}>
            创建
          </button>
        </div>
      )}

      {/* Agent 列表 */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {agents.map((agent) => (
          <AgentCard
            key={agent.id}
            agent={agent}
            onEdit={() => setEditingId(editingId === agent.id ? null : agent.id)}
            onDelete={() => removeAgent(agent.id)}
            isEditing={editingId === agent.id}
            onSave={(updated) => {
              updateAgent(agent.id, updated)
              setEditingId(null)
            }}
          />
        ))}
      </div>
    </div>
  )
}

// ---- Agent 卡片 ----

const AgentCard: React.FC<{
  agent: AgentConfig
  onEdit: () => void
  onDelete: () => void
  isEditing: boolean
  onSave: (updated: Partial<AgentConfig>) => void
}> = ({ agent, onEdit, onDelete, isEditing, onSave }) => {
  const [editForm, setEditForm] = useState<Partial<AgentConfig>>({})

  // 初始化编辑表单
  React.useEffect(() => {
    if (isEditing) {
      setEditForm({
        name: agent.name,
        systemPrompt: agent.systemPrompt,
        model: agent.model,
        skills: [...agent.skills],
        temperature: agent.temperature,
      })
    }
  }, [isEditing])

  const toggleEditSkill = (skill: string) => {
    setEditForm((f) => ({
      ...f,
      skills: (f.skills || []).includes(skill)
        ? (f.skills || []).filter((s) => s !== skill)
        : [...(f.skills || []), skill],
    }))
  }

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
            {agent.name}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>
            ID: {agent.id} · 模型: {agent.model} · 温度: {agent.temperature}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>
            技能: {agent.skills.length > 0 ? agent.skills.join(', ') : '无'}
          </div>
          <div
            style={{
              fontSize: 12,
              color: 'var(--text-muted)',
              background: 'var(--bg-tertiary)',
              padding: '6px 10px',
              borderRadius: 6,
              marginTop: 4,
              maxHeight: 40,
              overflow: 'hidden',
            }}
          >
            {agent.systemPrompt.slice(0, 100)}{agent.systemPrompt.length > 100 ? '...' : ''}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button className="btn" onClick={onEdit} style={{ fontSize: 12, padding: '4px 10px' }}>
            {isEditing ? '取消' : '编辑'}
          </button>
          <button
            className="btn"
            onClick={onDelete}
            style={{ fontSize: 12, padding: '4px 10px', color: 'var(--error)' }}
          >
            删除
          </button>
        </div>
      </div>

      {/* 编辑表单 */}
      {isEditing && (
        <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border)' }}>
          <div style={{ marginBottom: 8 }}>
            <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 2 }}>名称</label>
            <input value={editForm.name || ''} onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))} style={{ width: '100%' }} />
          </div>
          <div style={{ marginBottom: 8 }}>
            <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 2 }}>System Prompt</label>
            <textarea value={editForm.systemPrompt || ''} onChange={(e) => setEditForm((f) => ({ ...f, systemPrompt: e.target.value }))} rows={3} style={{ width: '100%' }} />
          </div>
          <div style={{ marginBottom: 8 }}>
            <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 2 }}>技能</label>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {AVAILABLE_SKILLS.map((skill) => (
                <label key={skill} style={{ display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer', fontSize: 12 }}>
                  <input
                    type="checkbox"
                    checked={(editForm.skills || []).includes(skill)}
                    onChange={() => toggleEditSkill(skill)}
                  />
                  {skill}
                </label>
              ))}
            </div>
          </div>
          <button className="btn btn-primary" onClick={() => onSave(editForm)}>
            保存修改
          </button>
        </div>
      )}
    </div>
  )
}

// ---- 表单字段（复用） ----

const AgentFormFields: React.FC<{
  form: AgentConfig
  setForm: React.Dispatch<React.SetStateAction<AgentConfig>>
  toggleSkill: (skill: string) => void
}> = ({ form, setForm, toggleSkill }) => (
  <>
    <div style={{ marginBottom: 8 }}>
      <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 2 }}>ID</label>
      <input value={form.id} onChange={(e) => setForm((f) => ({ ...f, id: e.target.value }))} placeholder="my_agent" style={{ width: '100%' }} />
    </div>
    <div style={{ marginBottom: 8 }}>
      <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 2 }}>名称</label>
      <input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="我的 Agent" style={{ width: '100%' }} />
    </div>
    <div style={{ marginBottom: 8 }}>
      <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 2 }}>System Prompt</label>
      <textarea value={form.systemPrompt} onChange={(e) => setForm((f) => ({ ...f, systemPrompt: e.target.value }))} rows={3} style={{ width: '100%' }} />
    </div>
    <div style={{ marginBottom: 8 }}>
      <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 2 }}>模型</label>
      <select value={form.model} onChange={(e) => setForm((f) => ({ ...f, model: e.target.value }))} style={{ width: '100%' }}>
        <option value="deepseek-chat">DeepSeek Chat</option>
        <option value="deepseek-reasoner">DeepSeek Reasoner</option>
      </select>
    </div>
    <div style={{ marginBottom: 8 }}>
      <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 2 }}>温度</label>
      <input type="range" min="0" max="2" step="0.1" value={form.temperature} onChange={(e) => setForm((f) => ({ ...f, temperature: parseFloat(e.target.value) }))} style={{ width: '100%' }} />
      <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{form.temperature}</span>
    </div>
    <div style={{ marginBottom: 8 }}>
      <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 2 }}>技能</label>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {AVAILABLE_SKILLS.map((skill) => (
          <label key={skill} style={{ display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer', fontSize: 12 }}>
            <input type="checkbox" checked={form.skills.includes(skill)} onChange={() => toggleSkill(skill)} />
            {skill}
          </label>
        ))}
      </div>
    </div>
  </>
)
