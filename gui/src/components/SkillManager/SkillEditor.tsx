import React, { useState } from 'react'

interface SkillCode {
  name: string
  code: string
  yaml: string
}

interface Props {
  skill: SkillCode
  onClose: () => void
  onSave: (code: string) => void
}

export const SkillEditor: React.FC<Props> = ({ skill, onClose, onSave }) => {
  const [code, setCode] = useState(skill.code || '')
  const [tab, setTab] = useState<'code' | 'yaml'>('code')
  const [dirty, setDirty] = useState(false)

  const handleEdit = (newCode: string) => {
    setCode(newCode)
    setDirty(newCode !== skill.code)
  }

  return (
    <div className="card" style={{ marginBottom: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div className="card-header" style={{ margin: 0 }}>
          编辑技能: {skill.name}
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          {dirty && (
            <button className="btn btn-primary" onClick={() => { onSave(code); setDirty(false) }}>
              保存并重载
            </button>
          )}
          <button className="btn" onClick={onClose}>
            关闭
          </button>
        </div>
      </div>

      {/* 标签切换 */}
      <div style={{ display: 'flex', gap: 0, marginBottom: 8, borderBottom: '1px solid var(--border)' }}>
        <button
          onClick={() => setTab('code')}
          style={{
            padding: '6px 16px',
            border: 'none',
            background: tab === 'code' ? 'var(--accent-subtle)' : 'transparent',
            color: tab === 'code' ? 'var(--accent)' : 'var(--text-secondary)',
            borderRadius: '6px 6px 0 0',
            fontSize: 12,
          }}
        >
          impl.py (实现代码)
        </button>
        <button
          onClick={() => setTab('yaml')}
          style={{
            padding: '6px 16px',
            border: 'none',
            background: tab === 'yaml' ? 'var(--accent-subtle)' : 'transparent',
            color: tab === 'yaml' ? 'var(--accent)' : 'var(--text-secondary)',
            borderRadius: '6px 6px 0 0',
            fontSize: 12,
          }}
        >
          skill.yaml (元数据)
        </button>
      </div>

      {/* 编辑器 */}
      {tab === 'code' ? (
        <textarea
          value={code}
          onChange={(e) => handleEdit(e.target.value)}
          style={{
            width: '100%',
            minHeight: 350,
            fontFamily: "'Cascadia Code', 'Fira Code', monospace",
            fontSize: 12,
            lineHeight: 1.6,
            tabSize: 4,
            background: '#1a1d27',
            border: '1px solid var(--border)',
            color: '#e4e6f0',
            padding: 12,
            borderRadius: 6,
            resize: 'vertical',
          }}
          spellCheck={false}
        />
      ) : (
        <pre
          style={{
            width: '100%',
            minHeight: 200,
            fontFamily: "'Cascadia Code', 'Fira Code', monospace",
            fontSize: 12,
            lineHeight: 1.6,
            background: '#1a1d27',
            border: '1px solid var(--border)',
            color: '#9498b0',
            padding: 12,
            borderRadius: 6,
            overflow: 'auto',
            whiteSpace: 'pre-wrap',
          }}
        >
          {skill.yaml || '# 无 YAML 元数据'}
        </pre>
      )}

      {/* 快捷键提示 */}
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>
        {dirty && '⚠ 有未保存的修改 · '}保存后会自动重载技能，无需重启服务
      </div>
    </div>
  )
}
