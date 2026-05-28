import React, { useState, useEffect } from 'react'
import { backendClient } from '../../services/backend'
import { SkillEditor } from './SkillEditor'

interface SkillInfo {
  name: string
  description: string
}

interface SkillCode {
  name: string
  code: string
  yaml: string
}

export const SkillManagerPage: React.FC = () => {
  const [skills, setSkills] = useState<SkillInfo[]>([])
  const [userSkills, setUserSkills] = useState<SkillInfo[]>([])
  const [editingSkill, setEditingSkill] = useState<SkillCode | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName] = useState('')
  const [newDesc, setNewDesc] = useState('')
  const [message, setMessage] = useState('')

  // 加载技能列表
  const loadSkills = async () => {
    // REST API 获取
    try {
      const res = await fetch(`${getBackendUrl()}/api/skills/`)
      const data = await res.json()
      setSkills(data.skills || [])
    } catch (e) {
      // WS 方式
      backendClient.send('list_skills')
    }
  }

  const loadUserSkills = async () => {
    backendClient.send('skill_list_user')
  }

  useEffect(() => {
    loadSkills()
    loadUserSkills()

    const unsub = backendClient.on('list_skills', (payload) => {
      setSkills((payload.skills as SkillInfo[]) || [])
    })
    const unsub2 = backendClient.on('skill_list_user', (payload) => {
      setUserSkills((payload.skills as SkillInfo[]) || [])
    })
    const unsub3 = backendClient.on('skill_get_code', (payload) => {
      setEditingSkill(payload as unknown as SkillCode)
    })
    const unsub4 = backendClient.on('skill_save_code', (payload) => {
      setMessage('技能已保存并重载')
      setTimeout(() => setMessage(''), 2000)
      loadSkills()
      loadUserSkills()
    })
    const unsub5 = backendClient.on('skill_create', (payload) => {
      setMessage(`技能已创建: ${(payload as any).path}`)
      setShowCreate(false)
      setTimeout(() => setMessage(''), 2000)
      loadSkills()
      loadUserSkills()
    })

    return () => { unsub(); unsub2(); unsub3(); unsub4(); unsub5() }
  }, [])

  const openEditor = (name: string) => {
    backendClient.send('skill_get_code', { name })
  }

  const handleCreate = () => {
    if (!newName.trim()) return
    backendClient.send('skill_create', {
      name: newName.trim().toLowerCase().replace(/\s+/g, '_'),
      description: newDesc.trim(),
    })
  }

  const handleDelete = (name: string) => {
    if (confirm(`确定删除技能「${name}」？`)) {
      backendClient.send('skill_delete', { name })
      setTimeout(() => {
        loadSkills()
        loadUserSkills()
      }, 500)
    }
  }

  return (
    <div style={{ maxWidth: 900 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h2 style={{ fontSize: 18 }}>技能管理</h2>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn" onClick={() => { loadSkills(); loadUserSkills() }}>
            刷新
          </button>
          <button className="btn btn-primary" onClick={() => setShowCreate(!showCreate)}>
            {showCreate ? '取消' : '+ 新建技能'}
          </button>
        </div>
      </div>

      {message && (
        <div style={{ padding: '8px 14px', background: 'var(--accent-subtle)', borderRadius: 6, color: 'var(--accent)', marginBottom: 16, fontSize: 13 }}>
          {message}
        </div>
      )}

      {/* 新建表单 */}
      {showCreate && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-header">新建技能</div>
          <div style={{ marginBottom: 8 }}>
            <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
              技能名称（也是文件名）
            </label>
            <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="my_custom_skill" style={{ width: '100%' }} />
          </div>
          <div style={{ marginBottom: 8 }}>
            <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
              描述
            </label>
            <input value={newDesc} onChange={(e) => setNewDesc(e.target.value)} placeholder="技能功能描述" style={{ width: '100%' }} />
          </div>
          <button className="btn btn-primary" onClick={handleCreate}>
            创建（自动生成骨架代码）
          </button>
        </div>
      )}

      {/* 技能编辑器 */}
      {editingSkill && (
        <SkillEditor
          skill={editingSkill}
          onClose={() => setEditingSkill(null)}
          onSave={(code) => {
            backendClient.send('skill_save_code', { name: editingSkill.name, code })
          }}
        />
      )}

      {/* 技能列表 */}
      <div style={{ marginBottom: 24 }}>
        <h3 style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 10 }}>
          内置技能 ({skills.length - userSkills.length})
        </h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {skills
            .filter((s) => !userSkills.find((u) => u.name === s.name))
            .map((skill) => (
              <SkillCard key={skill.name} skill={skill} type="builtin" onEdit={openEditor} />
            ))}
        </div>
      </div>

      <div>
        <h3 style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 10 }}>
          用户自定义 ({userSkills.length})
        </h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {userSkills.length === 0 ? (
            <div className="empty-state" style={{ padding: 30 }}>
              <span>📦</span>
              <div style={{ fontSize: 13 }}>还没有自定义技能</div>
              <div style={{ fontSize: 12 }}>点击「+ 新建技能」创建你的第一个技能</div>
            </div>
          ) : (
            userSkills.map((skill) => (
              <SkillCard
                key={skill.name}
                skill={skill}
                type="user"
                onEdit={openEditor}
                onDelete={handleDelete}
              />
            ))
          )}
        </div>
      </div>
    </div>
  )
}

// ---- 技能卡片 ----

const SkillCard: React.FC<{
  skill: SkillInfo
  type: 'builtin' | 'user'
  onEdit: (name: string) => void
  onDelete?: (name: string) => void
}> = ({ skill, type, onEdit, onDelete }) => (
  <div className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
    <div>
      <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>
        {skill.name}
        <span style={{
          fontSize: 10,
          marginLeft: 8,
          padding: '1px 6px',
          borderRadius: 4,
          background: type === 'builtin' ? 'var(--bg-tertiary)' : 'var(--accent-subtle)',
          color: type === 'builtin' ? 'var(--text-muted)' : 'var(--accent)',
        }}>
          {type === 'builtin' ? '内置' : '用户'}
        </span>
      </div>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
        {skill.description}
      </div>
    </div>
    <div style={{ display: 'flex', gap: 6 }}>
      <button className="btn" style={{ fontSize: 12, padding: '4px 10px' }} onClick={() => onEdit(skill.name)}>
        查看
      </button>
      {type === 'user' && onDelete && (
        <button className="btn" style={{ fontSize: 12, padding: '4px 10px', color: 'var(--error)' }} onClick={() => onDelete(skill.name)}>
          删除
        </button>
      )}
    </div>
  </div>
)

// 辅助
function getBackendUrl(): string {
  return 'http://127.0.0.1:8765'
}
