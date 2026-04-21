import React, { useEffect, useRef, useCallback } from 'react';

interface SimulationCanvasProps {
  network: any;
  vehicles: any[];
  pedestrians: any[];
  trafficLights: any[];
  selectedAgentId: string | null;
  onSelectAgent: (agentId: string | null, agentType?: string) => void;
  width?: number;
  height?: number;
}

const COLORS: Record<string, string> = {
  road: '#666666',
  laneDivider: '#FFFFFF',
  intersection: '#888888',
  node: '#333333',
  CAR: '#3498db',
  BUS: '#e74c3c',
  TRUCK: '#f39c12',
  EMERGENCY: '#9b59b6',
  pedestrian: '#e67e22',
  RED: '#e74c3c',
  YELLOW: '#f1c40f',
  GREEN: '#2ecc71',
  selected: '#ffd700',
};

export const SimulationCanvas: React.FC<SimulationCanvasProps> = ({
  network,
  vehicles,
  trafficLights,
  selectedAgentId,
  onSelectAgent,
  width = 800,
  height = 600,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const ctxRef = useRef<CanvasRenderingContext2D | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctxRef.current = ctx;
    canvas.width = width;
    canvas.height = height;
  }, [width, height]);

  const worldToScreen = useCallback((x: number, y: number) => {
    if (!network || network.nodes.length === 0) {
      return { x: width / 2, y: height / 2 };
    }
    const xs = network.nodes.map((n: any) => n.x);
    const ys = network.nodes.map((n: any) => n.y);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;
    const networkWidth = maxX - minX || 800;
    const networkHeight = maxY - minY || 800;
    const scaleX = (width * 0.85) / networkWidth;
    const scaleY = (height * 0.85) / networkHeight;
    const scale = Math.min(scaleX, scaleY);
    
    return {
      x: (x - centerX) * scale + width / 2,
      y: (y - centerY) * scale + height / 2,
    };
  }, [network, width, height]);

  useEffect(() => {
    const ctx = ctxRef.current;
    if (!ctx) return;

    ctx.fillStyle = '#f0f0f0';
    ctx.fillRect(0, 0, width, height);

    if (!network) return;

    // 绘制路段
    network.edges.forEach((edge: any) => {
      const fromNode = network.nodes.find((n: any) => n.id === edge.from_node);
      const toNode = network.nodes.find((n: any) => n.id === edge.to_node);
      if (!fromNode || !toNode) return;

      const from = worldToScreen(fromNode.x, fromNode.y);
      const to = worldToScreen(toNode.x, toNode.y);

      ctx.strokeStyle = COLORS.road;
      ctx.lineWidth = Math.max(2, edge.num_lanes * 4);
      ctx.lineCap = 'round';
      ctx.beginPath();
      ctx.moveTo(from.x, from.y);
      ctx.lineTo(to.x, to.y);
      ctx.stroke();
    });

    // 绘制节点
    network.nodes.forEach((node: any) => {
      const pos = worldToScreen(node.x, node.y);
      ctx.fillStyle = COLORS.intersection;
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, 8, 0, Math.PI * 2);
      ctx.fill();
    });

    // 绘制车辆
    vehicles.forEach((vehicle: any) => {
      const pos = worldToScreen(vehicle.x, vehicle.y);
      const color = COLORS[vehicle.vehicle_type] || COLORS.CAR;
      
      ctx.save();
      ctx.translate(pos.x, pos.y);
      ctx.rotate(vehicle.direction);
      
      ctx.fillStyle = color;
      ctx.fillRect(-8, -4, 16, 8);
      
      ctx.restore();
    });

    // 绘制信号灯
    trafficLights.forEach((light: any) => {
      const node = network.nodes.find((n: any) => n.id === light.node_id);
      if (!node) return;
      const pos = worldToScreen(node.x, node.y);
      
      ctx.fillStyle = COLORS[light.state] || COLORS.RED;
      ctx.beginPath();
      ctx.arc(pos.x + 15, pos.y - 15, 6, 0, Math.PI * 2);
      ctx.fill();
    });
  }, [network, vehicles, trafficLights, worldToScreen, width, height]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        width: '100%',
        height: '100%',
        border: '1px solid #ddd',
        borderRadius: 8,
        backgroundColor: '#f0f0f0',
      }}
    />
  );
};
