import React, { useCallback, useState } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type Connection,
  type NodeTypes,
  MarkerType,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { AgentNode } from './AgentNode'
import { useAppStore } from '../../stores/appStore'

const nodeTypes: NodeTypes = {
  agentNode: AgentNode,
}

const defaultNodes: Node[] = [
  {
    id: 'research',
    type: 'agentNode',
    position: { x: 50, y: 100 },
    data: {
      label: '调研 Agent',
      agentId: 'researcher',
      input: '调研主题: {topic}',
      skills: ['web_search'],
      useBlackboard: false,
    },
  },
  {
    id: 'write',
    type: 'agentNode',
    position: { x: 400, y: 100 },
    data: {
      label: '写作 Agent',
      agentId: 'writer',
      input: '根据调研写报告:\n{research.output}',
      skills: ['file_ops'],
      useBlackboard: false,
    },
  },
  {
    id: 'review',
    type: 'agentNode',
    position: { x: 750, y: 100 },
    data: {
      label: '审阅 Agent',
      agentId: 'reviewer',
      input: '审阅报告:\n{write.output}',
      skills: [],
      useBlackboard: true,
    },
  },
]

const defaultEdges: Edge[] = [
  {
    id: 'e-research-write',
    source: 'research',
    target: 'write',
    animated: true,
    markerEnd: { type: MarkerType.ArrowClosed, color: '#6c5ce7' },
    style: { stroke: '#6c5ce7' },
  },
  {
    id: 'e-write-review',
    source: 'write',
    target: 'review',
    animated: true,
    markerEnd: { type: MarkerType.ArrowClosed, color: '#6c5ce7' },
    style: { stroke: '#6c5ce7' },
  },
]

export const FlowEditorPage: React.FC = () => {
  const [nodes, setNodes, onNodesChange] = useNodesState(defaultNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(defaultEdges)
  const [selectedNode, setSelectedNode] = useState<Node | null>(null)

  const onConnect = useCallback(
    (params: Connection) => {
      setEdges((eds) =>
        addEdge(
          {
            ...params,
            animated: true,
            markerEnd: { type: MarkerType.ArrowClosed, color: '#6c5ce7' },
            style: { stroke: '#6c5ce7' },
          },
          eds,
        ),
      )
    },
    [setEdges],
  )

  const onNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      setSelectedNode(node)
    },
    [],
  )

  const onPaneClick = useCallback(() => {
    setSelectedNode(null)
  }, [])

  const handleExportYaml = () => {
    const flowDef = {
      name: '自定义流程',
      description: '在 GUI 中编排的流程',
      nodes: nodes.map((n) => ({
        id: n.id,
        agent: n.data.agentId,
        input: n.data.input,
        use_blackboard: n.data.useBlackboard || false,
      })),
      edges: edges.map((e) => ({
        source: e.source,
        target: e.target,
      })),
      output_mode: 'last',
    }
    const yaml = `# ${flowDef.name}\n${JSON.stringify(flowDef, null, 2)}`
    navigator.clipboard.writeText(yaml)
    alert('Flow 定义已复制到剪贴板（JSON 格式，后续改为 YAML 输出）')
  }

  return (
    <div style={{ display: 'flex', height: '100%', padding: 0, margin: -20 }}>
      {/* 画布 */}
      <div style={{ flex: 1, position: 'relative' }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={onNodeClick}
          onPaneClick={onPaneClick}
          nodeTypes={nodeTypes}
          fitView
          style={{ background: 'var(--bg-primary)' }}
        >
          <Background color="var(--border)" gap={20} />
          <Controls style={{ background: 'var(--bg-tertiary)', borderRadius: 8, border: '1px solid var(--border)' }} />
          <MiniMap
            style={{
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border)',
              borderRadius: 8,
            }}
            nodeColor={() => '#6c5ce7'}
            maskColor="rgba(15, 17, 23, 0.7)"
          />
        </ReactFlow>

        {/* 工具栏 */}
        <div style={{ position: 'absolute', top: 12, left: 12, display: 'flex', gap: 8, zIndex: 10 }}>
          <button className="btn btn-primary" onClick={() => {
            const id = `node-${Date.now()}`
            setNodes((nds) => [
              ...nds,
              {
                id,
                type: 'agentNode',
                position: { x: 100 + Math.random() * 200, y: 100 + Math.random() * 200 },
                data: { label: '新 Agent', agentId: 'default', input: '{user_input}', skills: [] },
              },
            ])
          }}>
            + 添加节点
          </button>
          <button className="btn" onClick={handleExportYaml}>
            导出
          </button>
        </div>
      </div>

      {/* 属性面板 */}
      {selectedNode && (
        <div
          style={{
            width: 300,
            minWidth: 300,
            background: 'var(--bg-secondary)',
            borderLeft: '1px solid var(--border)',
            padding: 16,
            overflowY: 'auto',
          }}
        >
          <h3 style={{ fontSize: 14, marginBottom: 16, color: 'var(--text-primary)' }}>
            节点配置: {selectedNode.data?.label || selectedNode.id}
          </h3>

          <div style={{ marginBottom: 12 }}>
            <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
              标识
            </label>
            <input
              value={selectedNode.id}
              onChange={(e) => {
                setNodes((nds) =>
                  nds.map((n) =>
                    n.id === selectedNode.id ? { ...n, id: e.target.value } : n,
                  ),
                )
              }}
              style={{ width: '100%' }}
            />
          </div>

          <div style={{ marginBottom: 12 }}>
            <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
              Agent
            </label>
            <input
              value={selectedNode.data.agentId || ''}
              onChange={(e) => {
                setNodes((nds) =>
                  nds.map((n) =>
                    n.id === selectedNode.id
                      ? { ...n, data: { ...n.data, agentId: e.target.value } }
                      : n,
                  ),
                )
              }}
              style={{ width: '100%' }}
            />
          </div>

          <div style={{ marginBottom: 12 }}>
            <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
              输入模板
            </label>
            <textarea
              value={selectedNode.data.input || ''}
              onChange={(e) => {
                setNodes((nds) =>
                  nds.map((n) =>
                    n.id === selectedNode.id
                      ? { ...n, data: { ...n.data, input: e.target.value } }
                      : n,
                  ),
                )
              }}
              rows={3}
              style={{ width: '100%', fontFamily: 'monospace', fontSize: 12 }}
            />
          </div>

          <div style={{ marginBottom: 12 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={selectedNode.data.useBlackboard || false}
                onChange={(e) => {
                  setNodes((nds) =>
                    nds.map((n) =>
                      n.id === selectedNode.id
                        ? { ...n, data: { ...n.data, useBlackboard: e.target.checked } }
                        : n,
                    ),
                  )
                }}
              />
              <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                黑板模式（共享上下文）
              </span>
            </label>
          </div>

          <button
            className="btn"
            style={{ color: 'var(--error)', width: '100%', justifyContent: 'center' }}
            onClick={() => {
              setNodes((nds) => nds.filter((n) => n.id !== selectedNode.id))
              setEdges((eds) => eds.filter((e) => e.source !== selectedNode.id && e.target !== selectedNode.id))
              setSelectedNode(null)
            }}
          >
            删除节点
          </button>
        </div>
      )}
    </div>
  )
}
