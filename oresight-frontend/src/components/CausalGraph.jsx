import React, { useMemo } from 'react';
import { ReactFlow, Background, Controls, Position, MarkerType } from '@xyflow/react';
import '@xyflow/react/dist/style.css';

// Color palette keyed by the backend's node `type` values (see
// oresight-backend/app/agents/simulator.py + planner.py's GraphNode/GraphEdge
// shapes, and app/schemas/causal_graph.py's real Pydantic contract).
const TYPE_STYLES = {
  SimulatedEvent: { bg: '#e0793a', border: '#c9662c' }, // orange
  Equipment: { bg: '#2a7f8c', border: '#226771' }, // teal
  BlastPlan: { bg: '#16233a', border: '#0e1726' }, // navy2
  OreZone: { bg: '#22c55e', border: '#16a34a' }, // success
  RiskEvent: { bg: '#e0793a', border: '#c9662c' }, // orange (roadmap)
  WeatherEvent: { bg: '#f59e0b', border: '#d97706' }, // warning
  ProductionForecast: { bg: '#5a6577', border: '#454e5d' }, // text-secondary
  MineSite: { bg: '#8896a8', border: '#6b7889' }, // text-muted
};
const DEFAULT_STYLE = { bg: '#8896a8', border: '#6b7889' };

const NODE_WIDTH = 168;
const NODE_HEIGHT = 44;
const COLUMN_GAP = 90;
const ROW_GAP = 20;

/**
 * Assigns each node a {depth, row} position via BFS from the graph's root
 * (affectedPath[0] if given, else the first node with no incoming edge,
 * else the first node in the list) so causally-later nodes lay out to the
 * right — @xyflow/react has no built-in auto-layout, so this is a small
 * bespoke layered layout rather than pulling in a full layout dependency
 * for what's usually a handful of nodes.
 */
function layoutNodes(nodes, edges, rootId) {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const outgoing = new Map(nodes.map((n) => [n.id, []]));
  edges.forEach((e) => {
    if (outgoing.has(e.source)) outgoing.get(e.source).push(e.target);
  });

  const root =
    (rootId && byId.has(rootId) && rootId) ||
    nodes.find((n) => !edges.some((e) => e.target === n.id))?.id ||
    nodes[0]?.id;

  const depth = new Map();
  if (root) {
    depth.set(root, 0);
    const queue = [root];
    while (queue.length) {
      const current = queue.shift();
      for (const next of outgoing.get(current) || []) {
        if (!depth.has(next)) {
          depth.set(next, depth.get(current) + 1);
          queue.push(next);
        }
      }
    }
  }
  // Any node unreachable from the root (disconnected graph fragment)
  // still needs a column so it isn't dropped from the view.
  let maxDepth = Math.max(0, ...depth.values());
  nodes.forEach((n) => {
    if (!depth.has(n.id)) depth.set(n.id, ++maxDepth);
  });

  const byDepth = new Map();
  nodes.forEach((n) => {
    const d = depth.get(n.id);
    if (!byDepth.has(d)) byDepth.set(d, []);
    byDepth.get(d).push(n.id);
  });

  const positions = new Map();
  byDepth.forEach((idsAtDepth, d) => {
    const columnHeight = idsAtDepth.length * (NODE_HEIGHT + ROW_GAP) - ROW_GAP;
    idsAtDepth.forEach((id, i) => {
      positions.set(id, {
        x: d * (NODE_WIDTH + COLUMN_GAP),
        y: i * (NODE_HEIGHT + ROW_GAP) - columnHeight / 2,
      });
    });
  });

  return positions;
}

export default function CausalGraph({ graph, affectedPath = [], height = 320, className = '' }) {
  const nodes = useMemo(() => graph?.nodes || [], [graph]);
  const edges = useMemo(() => graph?.edges || [], [graph]);

  const affectedNodeIds = useMemo(() => new Set(affectedPath), [affectedPath]);
  const affectedEdgeKeys = useMemo(() => {
    const keys = new Set();
    for (let i = 0; i < affectedPath.length - 1; i++) {
      keys.add(`${affectedPath[i]}->${affectedPath[i + 1]}`);
    }
    return keys;
  }, [affectedPath]);

  const { flowNodes, flowEdges } = useMemo(() => {
    const positions = layoutNodes(nodes, edges, affectedPath[0]);

    const flowNodes = nodes.map((n) => {
      const style = TYPE_STYLES[n.type] || DEFAULT_STYLE;
      const isAffected = affectedNodeIds.has(n.id);
      const pos = positions.get(n.id) || { x: 0, y: 0 };
      return {
        id: n.id,
        position: pos,
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
        data: { label: n.label, type: n.type },
        style: {
          width: NODE_WIDTH,
          background: style.bg,
          color: '#ffffff',
          border: `2px solid ${isAffected ? '#e0793a' : style.border}`,
          borderRadius: 8,
          padding: '8px 10px',
          fontSize: 11,
          fontWeight: 600,
          boxShadow: isAffected ? '0 0 0 3px rgba(224, 121, 58, 0.25)' : '0 1px 2px rgba(0,0,0,0.08)',
        },
      };
    });

    const flowEdges = edges.map((e, i) => {
      const key = `${e.source}->${e.target}`;
      const isAffected = affectedEdgeKeys.has(key);
      return {
        id: `${key}-${i}`,
        source: e.source,
        target: e.target,
        label: e.relationship,
        animated: isAffected,
        style: { stroke: isAffected ? '#e0793a' : '#8896a8', strokeWidth: isAffected ? 2 : 1.5 },
        labelStyle: { fontSize: 10, fill: '#5a6577', fontWeight: 600 },
        labelBgStyle: { fill: 'transparent' },
        markerEnd: { type: MarkerType.ArrowClosed, color: isAffected ? '#e0793a' : '#8896a8' },
      };
    });

    return { flowNodes, flowEdges };
  }, [nodes, edges, affectedNodeIds, affectedEdgeKeys, affectedPath]);

  if (nodes.length === 0) {
    return (
      <div
        style={{ height }}
        className={`flex items-center justify-center rounded-lg border border-dashed border-border text-xs text-text-muted ${className}`}
      >
        No graph data for this scenario.
      </div>
    );
  }

  return (
    <div style={{ height }} className={`overflow-hidden rounded-lg border border-border ${className}`}>
      <ReactFlow
        nodes={flowNodes}
        edges={flowEdges}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        panOnScroll
        zoomOnScroll={false}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={16} size={1} color="var(--border)" />
        <Controls showInteractive={false} position="bottom-right" />
      </ReactFlow>
    </div>
  );
}
