import React, { useMemo } from 'react';
import { ReactFlow, Background, Controls, Position, MarkerType } from '@xyflow/react';
import '@xyflow/react/dist/style.css';

const TYPE_STYLES = {
  SimulatedEvent: { bg: 'rgba(193, 87, 30, 0.15)', text: '#C1571E', border: '#C1571E' },
  Equipment: { bg: 'rgba(112, 107, 98, 0.15)', text: 'var(--text-primary)', border: 'var(--divider)' },
  BlastPlan: { bg: 'rgba(74, 122, 78, 0.15)', text: '#4A7A4E', border: '#4A7A4E' },
  OreZone: { bg: 'rgba(74, 122, 78, 0.15)', text: '#4A7A4E', border: '#4A7A4E' },
  RiskEvent: { bg: 'rgba(178, 59, 46, 0.15)', text: '#B23B2E', border: '#B23B2E' },
  WeatherEvent: { bg: 'rgba(193, 87, 30, 0.15)', text: '#C1571E', border: '#C1571E' },
  ProductionForecast: { bg: 'rgba(138, 133, 120, 0.15)', text: 'var(--text-muted)', border: 'var(--divider)' },
  MineSite: { bg: 'rgba(138, 133, 120, 0.15)', text: 'var(--text-primary)', border: 'var(--divider)' },
};
const DEFAULT_STYLE = { bg: 'rgba(138, 133, 120, 0.15)', text: 'var(--text-primary)', border: 'var(--divider)' };

const NODE_WIDTH = 160;
const NODE_HEIGHT = 40;
const COLUMN_GAP = 80;
const ROW_GAP = 18;

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
          background: isAffected ? 'rgba(193, 87, 30, 0.15)' : style.bg,
          color: isAffected ? '#C1571E' : style.text,
          border: `1px solid ${isAffected ? '#C1571E' : style.border}`,
          borderRadius: 20,
          padding: '6px 12px',
          fontSize: 11,
          fontFamily: 'Inter, sans-serif',
          fontWeight: 500,
          boxShadow: isAffected ? '0 0 12px rgba(193, 87, 30, 0.35)' : 'none',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          textAlign: 'center',
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
        style: { stroke: isAffected ? '#C1571E' : 'var(--text-muted)', strokeWidth: isAffected ? 2 : 1, opacity: 0.7 },
        labelStyle: { fontSize: 10, fill: 'var(--text-muted)', fontFamily: 'Inter, sans-serif', fontWeight: 500 },
        labelBgStyle: { fill: 'transparent' },
        markerEnd: { type: MarkerType.ArrowClosed, color: isAffected ? '#C1571E' : 'var(--text-muted)' },
      };
    });

    return { flowNodes, flowEdges };
  }, [nodes, edges, affectedNodeIds, affectedEdgeKeys, affectedPath]);

  if (nodes.length === 0) {
    return (
      <div
        style={{ height }}
        className={`flex items-center justify-center rounded-xl bg-[var(--bg-primary)] text-xs text-[var(--text-muted)] ${className}`}
      >
        No graph data for this scenario.
      </div>
    );
  }

  return (
    <div style={{ height }} className={`overflow-hidden rounded-xl bg-[var(--bg-primary)] border border-[var(--divider)] ${className}`}>
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
        <Background gap={20} size={1} color="var(--divider)" />
        <Controls showInteractive={false} position="bottom-right" />
      </ReactFlow>
    </div>
  );
}
