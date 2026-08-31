import { useMemo } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  Handle,
  MarkerType,
  Position,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

function CausalNode({ data }) {
  return (
    <div className="min-w-[148px] rounded-md border border-border bg-white px-4 py-3 shadow-subtle">
      <Handle type="target" position={Position.Left} className="!h-2 !w-2 !border-2 !border-white !bg-teal" />
      <div className="font-heading text-sm font-semibold text-navy">{data.label}</div>
      <Handle type="source" position={Position.Right} className="!h-2 !w-2 !border-2 !border-white !bg-orange" />
    </div>
  )
}

const nodeTypes = { causal: CausalNode }

const initialNodes = [
  { id: 'weather', type: 'causal', position: { x: 0, y: 120 }, data: { label: 'WeatherEvent' } },
  { id: 'blast', type: 'causal', position: { x: 240, y: 120 }, data: { label: 'BlastPlan' } },
  { id: 'ore', type: 'causal', position: { x: 480, y: 120 }, data: { label: 'OreZone' } },
  { id: 'risk', type: 'causal', position: { x: 720, y: 120 }, data: { label: 'RiskEvent' } },
]

const initialEdges = [
  {
    id: 'weather-blast',
    source: 'weather',
    target: 'blast',
    type: 'smoothstep',
    markerEnd: { type: MarkerType.ArrowClosed, color: '#2a7f8c' },
    style: { stroke: '#2a7f8c', strokeWidth: 2 },
  },
  {
    id: 'blast-ore',
    source: 'blast',
    target: 'ore',
    type: 'smoothstep',
    markerEnd: { type: MarkerType.ArrowClosed, color: '#2a7f8c' },
    style: { stroke: '#2a7f8c', strokeWidth: 2 },
  },
  {
    id: 'ore-risk',
    source: 'ore',
    target: 'risk',
    type: 'smoothstep',
    markerEnd: { type: MarkerType.ArrowClosed, color: '#e0793a' },
    style: { stroke: '#e0793a', strokeWidth: 2 },
  },
]

export default function GraphTest() {
  const nodeTypesMemo = useMemo(() => nodeTypes, [])

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="font-heading text-lg font-semibold text-navy">Causal Graph Sandbox</h2>
        <p className="mt-1 text-sm text-slate-500">
          Static React Flow test — WeatherEvent → BlastPlan → OreZone → RiskEvent
        </p>
      </div>

      <div className="h-[480px] overflow-hidden rounded-md border border-border bg-white shadow-subtle">
        <ReactFlow
          nodes={initialNodes}
          edges={initialEdges}
          nodeTypes={nodeTypesMemo}
          fitView
          fitViewOptions={{ padding: 0.3 }}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          panOnDrag
          zoomOnScroll
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#e2e7ee" gap={20} />
          <Controls className="!border-border !shadow-subtle [&>button]:!border-border [&>button]:!bg-white [&>button]:hover:!bg-bg" />
        </ReactFlow>
      </div>
    </div>
  )
}
