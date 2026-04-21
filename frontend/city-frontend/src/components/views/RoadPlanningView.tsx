import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Badge,
  Button,
  Card,
  Col,
  Empty,
  Row,
  Segmented,
  Space,
  Tag,
  Timeline,
  Typography
} from 'antd';
import {
  ApartmentOutlined,
  BranchesOutlined,
  ClusterOutlined,
  DownOutlined,
  EyeOutlined,
  MessageOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  RightOutlined,
  SettingOutlined
} from '@ant-design/icons';
import City3DView from '../City3DView';
import { AgentMemoryView } from '../AgentMemoryView';
import { LLMConfigPanel } from '../LLMConfigPanel';
import CityBirthConfigCard from '../citybirth/CityBirthConfigCard';
import CityBirthStatusCard from '../citybirth/CityBirthStatusCard';
import { ExpansionRecord, LLMDecisionRecord, Network, PlanningAgentStatus, TrafficLight, Vehicle, Zone, ZoningAgentStatus } from '../../types';
import { buildPhysicalRoads } from '../../utils/physicalRoads';
import { createScreenTransform, getNetworkBounds } from '../../utils/worldTransform';

interface RoadPlanningViewProps {
  network: Network | null;
  vehicles: Vehicle[];
  trafficLights: TrafficLight[];
  expansionHistory: ExpansionRecord[];
  planningAgent: PlanningAgentStatus | null;
  zoningAgent: ZoningAgentStatus | null;
  zones: Zone[];
  llmDecisions: LLMDecisionRecord[];
  isRunning: boolean;
  currentTime: number;
  statistics: any;
  llmConfig: any;
  onLLMConfigChange: (config: any) => void;
  birthConfig: any;
  onBirthConfigChange: (config: any) => void;
  onStart: () => void;
  onPause: () => void;
  onReset: () => void;
  agentMemories: any[];
  agentsWithMemory: any[];
}

const llmCategoryLabelMap: Record<string, string> = {
  road_expansion: '道路扩展',
  zone_batch_count: '区域批次',
  zone_location_type: '区域位置'
};

const llmStatusLabelMap: Record<string, string> = {
  success: '成功',
  fallback: '降级',
  parse_failed: '解析失败',
  empty_response: '空响应',
  error: '错误'
};

const zoneColorMap: Record<string, string> = {
  RESIDENTIAL: '#d9f0ff',
  COMMERCIAL: '#ffe9c7',
  INDUSTRIAL: '#d8dee8',
  HOSPITAL: '#ffd8dc',
  SCHOOL: '#daf5c6',
  PARK: '#c9f3d4',
  OFFICE: '#ebe0ff',
  MIXED_USE: '#ffdff1',
  GOVERNMENT: '#d3f1ef',
  SHOPPING: '#fff4be'
};

const shellCardStyle: React.CSSProperties = {
  borderRadius: 28,
  border: '1px solid rgba(15, 23, 42, 0.08)',
  background: 'rgba(255,255,255,0.8)',
  boxShadow: '0 24px 80px rgba(15, 23, 42, 0.08)',
  backdropFilter: 'blur(14px)'
};

const panelCardStyle: React.CSSProperties = {
  borderRadius: 22,
  border: '1px solid rgba(15, 23, 42, 0.08)',
  background: '#ffffff',
  boxShadow: '0 20px 60px rgba(15, 23, 42, 0.08)'
};

const getDirectionalSignalState = (
  light: TrafficLight,
  direction: 'ns' | 'ew'
): 'RED' | 'YELLOW' | 'GREEN' => {
  const directional = direction === 'ns' ? light.ns_state : light.ew_state;
  return directional || light.state || 'RED';
};

const getSignalColor = (state: 'RED' | 'YELLOW' | 'GREEN') => {
  if (state === 'GREEN') return '#16803c';
  if (state === 'YELLOW') return '#d97706';
  return '#dc2626';
};

const PlanningCanvas: React.FC<{
  network: Network | null;
  vehicles: Vehicle[];
  trafficLights: TrafficLight[];
  zones: Zone[];
  expansionHistory: ExpansionRecord[];
}> = ({ network, vehicles, trafficLights, zones, expansionHistory }) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const dragRef = useRef<{
    isDragging: boolean;
    pointerId: number | null;
    lastX: number;
    lastY: number;
  }>({
    isDragging: false,
    pointerId: null,
    lastX: 0,
    lastY: 0
  });
  const bounds = useMemo(() => getNetworkBounds(network, { zones, padding: 20 }), [network, zones]);
  const [viewState, setViewState] = useState({ zoom: 1, panX: 0, panY: 0 });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.clientWidth || 960;
    const height = canvas.clientHeight || 720;
    canvas.width = width;
    canvas.height = height;

    ctx.clearRect(0, 0, width, height);

    const background = ctx.createLinearGradient(0, 0, width, height);
    background.addColorStop(0, '#f8fbff');
    background.addColorStop(0.45, '#f7fbf7');
    background.addColorStop(1, '#fbfbfd');
    ctx.fillStyle = background;
    ctx.fillRect(0, 0, width, height);

    if (!network) {
      ctx.fillStyle = '#64748b';
      ctx.font = '16px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('等待路网数据...', width / 2, height / 2);
      return;
    }

    const transform = createScreenTransform(bounds, width, height, 52, Number.POSITIVE_INFINITY);
    const worldToScreen = (x: number, y: number) => ({
      x: x * transform.scale * viewState.zoom + transform.offsetX + viewState.panX,
      y: height - (y * transform.scale * viewState.zoom + transform.offsetY + viewState.panY)
    });

    const expandedNodeIds = new Set(
      expansionHistory.filter(record => record.type === 'add_node' && record.node_id).map(record => record.node_id as string)
    );
    const nodeById = new Map(network.nodes.map(node => [node.id, node]));
    const zoneLabels: Array<{ x: number; y: number; text: string }> = [];
    const physicalNeighborsByNode = new Map<string, Array<{ neighborId: string; axis: 'ns' | 'ew' }>>();
    const physicalRoads = buildPhysicalRoads(network);
    const nodeRadiusHint = new Map<string, number>();

    network.edges.forEach(edge => {
      const fromNode = nodeById.get(edge.from_node);
      const toNode = nodeById.get(edge.to_node);
      if (!fromNode || !toNode) return;
      const axis: 'ns' | 'ew' = Math.abs(toNode.x - fromNode.x) >= Math.abs(toNode.y - fromNode.y) ? 'ew' : 'ns';
      const fromList = physicalNeighborsByNode.get(edge.from_node) || [];
      if (!fromList.some(item => item.neighborId === edge.to_node)) {
        fromList.push({ neighborId: edge.to_node, axis });
        physicalNeighborsByNode.set(edge.from_node, fromList);
      }
      const toList = physicalNeighborsByNode.get(edge.to_node) || [];
      if (!toList.some(item => item.neighborId === edge.from_node)) {
        toList.push({ neighborId: edge.from_node, axis });
        physicalNeighborsByNode.set(edge.to_node, toList);
      }
    });

    physicalRoads.forEach(road => {
      const roadWidth = Math.max(1.6, road.totalLanes * 1.35);
      const hintRadius = Math.max(roadWidth * 0.5, 2.4);
      nodeRadiusHint.set(road.fromNodeId, Math.max(nodeRadiusHint.get(road.fromNodeId) || 0, hintRadius));
      nodeRadiusHint.set(road.toNodeId, Math.max(nodeRadiusHint.get(road.toNodeId) || 0, hintRadius));
    });

    ctx.strokeStyle = 'rgba(148, 163, 184, 0.18)';
    ctx.lineWidth = 1;
    for (let x = 0; x < width; x += 48) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }
    for (let y = 0; y < height; y += 48) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    zones.forEach(zone => {
      const zoneWidth = Math.max(12, zone.width * transform.scale * viewState.zoom);
      const zoneHeight = Math.max(12, zone.height * transform.scale * viewState.zoom);
      const center = worldToScreen(zone.center_x, zone.center_y);
      ctx.fillStyle = zoneColorMap[zone.zone_type] || '#dbeaf1';
      ctx.globalAlpha = 0.88;
      ctx.fillRect(center.x - zoneWidth / 2, center.y - zoneHeight / 2, zoneWidth, zoneHeight);
      ctx.globalAlpha = 1;
      ctx.strokeStyle = 'rgba(148, 163, 184, 0.26)';
      ctx.strokeRect(center.x - zoneWidth / 2, center.y - zoneHeight / 2, zoneWidth, zoneHeight);
      if (zone.name) {
        zoneLabels.push({ x: center.x, y: center.y, text: zone.name });
      }
    });

    physicalRoads.forEach(road => {
      const fromNode = nodeById.get(road.fromNodeId);
      const toNode = nodeById.get(road.toNodeId);
      if (!fromNode || !toNode) return;

      const p1 = worldToScreen(fromNode.x, fromNode.y);
      const p2 = worldToScreen(toNode.x, toNode.y);
      const dx = p2.x - p1.x;
      const dy = p2.y - p1.y;
      const length = Math.hypot(dx, dy);
      if (length < 0.001) return;

      const roadWidth = Math.max(1.6, road.totalLanes * 1.35);
      const startInset = Math.min(length * 0.3, nodeRadiusHint.get(road.fromNodeId) || roadWidth * 0.5);
      const endInset = Math.min(length * 0.3, nodeRadiusHint.get(road.toNodeId) || roadWidth * 0.5);
      const ux = dx / length;
      const uy = dy / length;
      const start = { x: p1.x + ux * startInset, y: p1.y + uy * startInset };
      const end = { x: p2.x - ux * endInset, y: p2.y - uy * endInset };
      ctx.strokeStyle = '#8b97a8';
      ctx.lineWidth = roadWidth;
      ctx.lineCap = 'round';
      ctx.beginPath();
      ctx.moveTo(start.x, start.y);
      ctx.lineTo(end.x, end.y);
      ctx.stroke();

      if (road.reverseLanes > 0) {
        ctx.strokeStyle = '#f8fafc';
        ctx.lineWidth = Math.max(1.5, roadWidth * 0.12);
        ctx.beginPath();
        ctx.moveTo(start.x, start.y);
        ctx.lineTo(end.x, end.y);
        ctx.stroke();
      }

      if (road.reverseLanes === 0 && road.totalLanes > 1) {
        const px = -uy;
        const py = ux;
        for (let dividerIndex = 1; dividerIndex < road.totalLanes; dividerIndex += 1) {
          const laneOffset = (dividerIndex - road.totalLanes / 2) * (roadWidth / road.totalLanes);
          ctx.strokeStyle = 'rgba(245,243,215,0.92)';
          ctx.lineWidth = Math.max(1, roadWidth * 0.04);
          ctx.beginPath();
          ctx.moveTo(start.x + px * laneOffset, start.y + py * laneOffset);
          ctx.lineTo(end.x + px * laneOffset, end.y + py * laneOffset);
          ctx.stroke();
        }
      }
    });

    network.nodes.forEach(node => {
      const p = worldToScreen(node.x, node.y);
      const isExpanded = expandedNodeIds.has(node.id);
      ctx.fillStyle = isExpanded ? '#0f62fe' : '#ffffff';
      ctx.strokeStyle = isExpanded ? '#0f62fe' : '#94a3b8';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(p.x, p.y, isExpanded ? 5.5 : 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    });

    vehicles.forEach(vehicle => {
      const p = worldToScreen(vehicle.x, vehicle.y);
      ctx.fillStyle = '#0f62fe';
      ctx.beginPath();
      ctx.arc(p.x, p.y, 3.5, 0, Math.PI * 2);
      ctx.fill();
    });

    trafficLights.forEach(light => {
      const node = nodeById.get(light.node_id);
      if (!node) return;
      const neighbors = physicalNeighborsByNode.get(light.node_id) || [];

      neighbors.forEach(({ neighborId, axis }) => {
        const neighbor = nodeById.get(neighborId);
        if (!neighbor) return;
        const nodeScreen = worldToScreen(node.x, node.y);
        const neighborScreen = worldToScreen(neighbor.x, neighbor.y);
        const dx = neighborScreen.x - nodeScreen.x;
        const dy = neighborScreen.y - nodeScreen.y;
        const length = Math.hypot(dx, dy);
        if (length < 8) return;

        const midX = nodeScreen.x + dx * 0.5;
        const midY = nodeScreen.y + dy * 0.5;
        const ux = dx / length;
        const uy = dy / length;
        const state = getDirectionalSignalState(light, axis);
        const color = getSignalColor(state);
        const bodyLength = 10;
        const headLength = 5;

        ctx.lineWidth = 2;
        ctx.strokeStyle = color;
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.moveTo(midX - ux * bodyLength * 0.5, midY - uy * bodyLength * 0.5);
        ctx.lineTo(midX + ux * bodyLength * 0.5, midY + uy * bodyLength * 0.5);
        ctx.stroke();

        const tipX = midX + ux * (bodyLength * 0.5 + headLength * 0.35);
        const tipY = midY + uy * (bodyLength * 0.5 + headLength * 0.35);
        const px = -uy;
        const py = ux;
        ctx.beginPath();
        ctx.moveTo(tipX, tipY);
        ctx.lineTo(tipX - ux * headLength - px * 3.4, tipY - uy * headLength - py * 3.4);
        ctx.lineTo(tipX - ux * headLength + px * 3.4, tipY - uy * headLength + py * 3.4);
        ctx.closePath();
        ctx.fill();
      });
    });

    ctx.font = '12px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    zoneLabels.forEach(label => {
      ctx.fillStyle = '#111111';
      ctx.fillText(label.text, label.x, label.y);
    });
  }, [bounds, expansionHistory, network, trafficLights, vehicles, viewState, zones]);

  const resetView = () => {
    setViewState({ zoom: 1, panX: 0, panY: 0 });
  };

  const handleWheel = useCallback((event: WheelEvent) => {
    event.preventDefault();
    event.stopPropagation();
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const cursorX = event.clientX - rect.left;
    const cursorY = event.clientY - rect.top;
    const canvasY = rect.height - cursorY;
    const zoomFactor = event.deltaY < 0 ? 1.12 : 0.9;

    setViewState(prev => {
      const nextZoom = Math.min(6, Math.max(0.45, prev.zoom * zoomFactor));
      if (Math.abs(nextZoom - prev.zoom) < 0.0001) {
        return prev;
      }
      const zoomRatio = nextZoom / prev.zoom;
      return {
        zoom: nextZoom,
        panX: cursorX - (cursorX - prev.panX) * zoomRatio,
        panY: canvasY - (canvasY - prev.panY) * zoomRatio
      };
    });
  }, []);

  // 使用原生事件监听以确保 preventDefault 有效（阻止页面缩放）
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    canvas.addEventListener('wheel', handleWheel, { passive: false });
    return () => {
      canvas.removeEventListener('wheel', handleWheel);
    };
  }, [handleWheel]);

  const handlePointerDown: React.PointerEventHandler<HTMLCanvasElement> = event => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    dragRef.current = {
      isDragging: true,
      pointerId: event.pointerId,
      lastX: event.clientX,
      lastY: event.clientY
    };
    canvas.setPointerCapture(event.pointerId);
  };

  const handlePointerMove: React.PointerEventHandler<HTMLCanvasElement> = event => {
    if (!dragRef.current.isDragging || dragRef.current.pointerId !== event.pointerId) {
      return;
    }
    const dx = event.clientX - dragRef.current.lastX;
    const dy = event.clientY - dragRef.current.lastY;
    dragRef.current.lastX = event.clientX;
    dragRef.current.lastY = event.clientY;
    setViewState(prev => ({
      ...prev,
      panX: prev.panX + dx,
      panY: prev.panY - dy
    }));
  };

  const handlePointerUp: React.PointerEventHandler<HTMLCanvasElement> = event => {
    const canvas = canvasRef.current;
    if (canvas && dragRef.current.pointerId === event.pointerId) {
      try {
        canvas.releasePointerCapture(event.pointerId);
      } catch {}
    }
    dragRef.current.isDragging = false;
    dragRef.current.pointerId = null;
  };

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <div
        style={{
          position: 'absolute',
          top: 12,
          right: 12,
          zIndex: 2,
          display: 'flex',
          gap: 8,
          alignItems: 'center',
          padding: '6px 10px',
          borderRadius: 999,
          background: 'rgba(255,255,255,0.82)',
          border: '1px solid rgba(15,23,42,0.08)',
          color: '#475569',
          fontSize: 12
        }}
      >
        <span>{viewState.zoom.toFixed(2)}x</span>
        <Button size="small" onClick={resetView}>
          重置视图
        </Button>
      </div>
      <canvas
        ref={canvasRef}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerLeave={handlePointerUp}
        onDoubleClick={resetView}
        style={{
          width: '100%',
          height: '100%',
          display: 'block',
          borderRadius: 24,
          background: 'linear-gradient(180deg, #f8fbff 0%, #f7fbf7 100%)',
          cursor: dragRef.current.isDragging ? 'grabbing' : 'grab',
          touchAction: 'none'
        }}
      />
    </div>
  );
};

export const RoadPlanningView: React.FC<RoadPlanningViewProps> = ({
  network,
  vehicles,
  trafficLights,
  expansionHistory,
  planningAgent,
  zoningAgent,
  zones,
  llmDecisions,
  isRunning,
  currentTime,
  statistics,
  llmConfig,
  onLLMConfigChange,
  birthConfig,
  onBirthConfigChange,
  onStart,
  onPause,
  onReset,
  agentMemories,
  agentsWithMemory
}) => {
  const [viewMode, setViewMode] = useState<'2d' | '3d'>('2d');
  const [showConfig, setShowConfig] = useState(true);
  const [llmDecisionFilter, setLlmDecisionFilter] = useState<'all' | 'road_expansion' | 'zone_batch_count' | 'zone_location_type'>('all');
  const [expandedDecisionIds, setExpandedDecisionIds] = useState<Set<string>>(new Set());

  const toggleDecisionExpand = (id: string) => {
    setExpandedDecisionIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const filteredLlmDecisions = useMemo(() => {
    if (llmDecisionFilter === 'all') {
      return llmDecisions;
    }
    return llmDecisions.filter(item => item.category === llmDecisionFilter);
  }, [llmDecisionFilter, llmDecisions]);

  return (
    <div
      style={{
        minHeight: 'calc(100vh - 96px)',
        padding: 8,
        borderRadius: 28,
        background:
          'radial-gradient(circle at top left, rgba(15,98,254,0.10), transparent 28%), radial-gradient(circle at top right, rgba(22,128,60,0.10), transparent 28%), linear-gradient(180deg, #f3f7ff 0%, #f7faf7 42%, #fbfbfd 100%)'
      }}
    >
      <div
        style={{
          marginBottom: 18,
          padding: '24px 24px 20px',
          borderRadius: 28,
          background: 'rgba(255,255,255,0.8)',
          border: '1px solid rgba(15, 23, 42, 0.08)',
          boxShadow: '0 24px 80px rgba(15, 23, 42, 0.08)',
          backdropFilter: 'blur(14px)'
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 24, alignItems: 'center', flexWrap: 'wrap' }}>
          <div>
            <Space size={12} align="center">
              <div
                style={{
                  width: 46,
                  height: 46,
                  borderRadius: 16,
                  display: 'grid',
                  placeItems: 'center',
                  background: 'rgba(15,98,254,0.10)',
                  border: '1px solid rgba(15,98,254,0.16)'
                }}
              >
                <ClusterOutlined style={{ color: '#0f62fe', fontSize: 18 }} />
              </div>
              <div>
                <Typography.Title level={3} style={{ margin: 0, color: '#0f172a' }}>
                  City Birth Studio
                </Typography.Title>
                <Typography.Text style={{ color: '#475569' }}>
                  观看城市从初始路网逐渐生长，支持 2D 平面视图和沉浸式 3D 漫游体验
                </Typography.Text>
              </div>
            </Space>
          </div>

          <Space size={12} wrap>
            <Tag color={isRunning ? 'cyan' : 'default'} style={{ padding: '6px 12px', borderRadius: 999 }}>
              {isRunning ? '运行中' : '已停止'}
            </Tag>
            <Button type={isRunning ? 'default' : 'primary'} icon={<PlayCircleOutlined />} onClick={onStart} disabled={isRunning}>
              开始
            </Button>
            <Button icon={<PauseCircleOutlined />} onClick={onPause} disabled={!isRunning}>
              暂停
            </Button>
            <Button icon={<ReloadOutlined />} onClick={onReset}>
              重置
            </Button>
          </Space>
        </div>
      </div>

      <Space direction="vertical" style={{ width: '100%' }} size={18}>
        <Card
          style={shellCardStyle}
          bodyStyle={{ padding: 18 }}
          title={
            <Space size={10}>
              <BranchesOutlined style={{ color: '#0f62fe' }} />
              <span style={{ color: '#0f172a' }}>配置与控制</span>
            </Space>
          }
          headStyle={{ borderBottom: '1px solid rgba(15, 23, 42, 0.08)' }}
          extra={
            <Space size={10} wrap>
              <Button icon={<SettingOutlined />} onClick={() => setShowConfig(prev => !prev)}>
                {showConfig ? '隐藏配置' : '显示配置'}
              </Button>
              <Segmented
                value={viewMode}
                onChange={value => setViewMode(value as '2d' | '3d')}
                options={[
                  {
                    label: (
                      <Space size={6}>
                        <EyeOutlined />
                        <span>2D</span>
                      </Space>
                    ),
                    value: '2d'
                  },
                  {
                    label: (
                      <Space size={6}>
                        <ApartmentOutlined />
                        <span>3D</span>
                      </Space>
                    ),
                    value: '3d'
                  }
                ]}
              />
            </Space>
          }
        >
          {showConfig && (
            <Row gutter={[16, 16]}>
              <Col xs={24} xl={14}>
                <CityBirthConfigCard
                  birthConfig={birthConfig}
                  onBirthConfigChange={onBirthConfigChange}
                  isRunning={isRunning}
                />
              </Col>
              <Col xs={24} xl={10}>
                <LLMConfigPanel config={llmConfig} onChange={onLLMConfigChange} />
              </Col>
            </Row>
          )}
        </Card>

        <Card
          style={shellCardStyle}
          bodyStyle={{ padding: 18 }}
          title={
            <Space size={10}>
              <span style={{ color: '#0f172a' }}>{viewMode === '2d' ? '2D 城市视图' : '3D 城市视图'}</span>
              <Badge status={isRunning ? 'processing' : 'default'} text={isRunning ? '实时渲染' : '暂停'} />
            </Space>
          }
          headStyle={{ borderBottom: '1px solid rgba(15, 23, 42, 0.08)' }}
        >
          <div style={{ height: `calc(100vh - ${showConfig ? 360 : 280}px)`, minHeight: 520 }}>
            {viewMode === '2d' ? (
              <PlanningCanvas
                network={network}
                vehicles={vehicles}
                trafficLights={trafficLights}
                zones={zones}
                expansionHistory={expansionHistory}
              />
            ) : (
              <City3DView
                network={network}
                zones={zones}
                vehicles={vehicles}
                trafficLights={trafficLights}
                expansionHistory={expansionHistory}
              />
            )}
          </div>
        </Card>

        <Row gutter={[20, 20]}>
          <Col xs={24} xl={8}>
            <CityBirthStatusCard
              currentTime={currentTime}
              vehicles={vehicles}
              network={network}
              zones={zones}
              expansionHistory={expansionHistory}
              statistics={statistics}
              planningAgent={planningAgent}
              zoningAgent={zoningAgent}
            />
          </Col>

          <Col xs={24} xl={8}>
            <Card
              size="small"
              style={panelCardStyle}
              headStyle={{ color: '#111827', borderBottom: '1px solid rgba(15, 23, 42, 0.08)' }}
              bodyStyle={{ padding: 18 }}
              title={
                <Space size={10}>
                  <BranchesOutlined style={{ color: '#16803c' }} />
                  <span>路网扩展记录</span>
                </Space>
              }
            >
              {expansionHistory.length > 0 ? (
                <Timeline
                  items={expansionHistory
                    .slice()
                    .reverse()
                    .slice(0, 8)
                    .map(record => ({
                      color: record.type === 'add_edge' ? 'green' : record.type === 'add_node' ? 'blue' : 'gray',
                      children: (
                        <div>
                          <Typography.Text style={{ color: '#334155' }}>
                            {record.action || record.type || 'network_update'}
                          </Typography.Text>
                          <div style={{ color: '#64748b', fontSize: 12, marginTop: 4 }}>
                            {typeof record.timestamp === 'number' ? `t=${record.timestamp.toFixed(1)}s` : ''}
                          </div>
                        </div>
                      )
                    }))}
                />
              ) : (
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无路网扩展记录" />
              )}
            </Card>
          </Col>

          <Col xs={24} xl={8}>
            <Card
              size="small"
              style={panelCardStyle}
              headStyle={{ color: '#111827', borderBottom: '1px solid rgba(15, 23, 42, 0.08)' }}
              bodyStyle={{ padding: 18 }}
              title={
                <Space size={10}>
                  <ClusterOutlined style={{ color: '#0f62fe' }} />
                  <span>功能区域</span>
                </Space>
              }
            >
              {zones.length > 0 ? (
                <Space direction="vertical" style={{ width: '100%' }} size={10}>
                  {zones.slice(0, 10).map(zone => (
                    <div
                      key={zone.zone_id}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '10px 12px',
                        borderRadius: 14,
                        background: '#f8fafc',
                        border: '1px solid rgba(15, 23, 42, 0.06)'
                      }}
                    >
                      <div>
                        <Typography.Text style={{ color: '#334155', display: 'block' }}>
                          {zone.name || zone.zone_id}
                        </Typography.Text>
                        <Typography.Text style={{ color: '#64748b', fontSize: 12 }}>
                          {zone.zone_type}
                        </Typography.Text>
                      </div>
                      <div
                        style={{
                          width: 14,
                          height: 14,
                          borderRadius: 999,
                          background: zoneColorMap[zone.zone_type] || '#dbeaf1',
                          border: '1px solid rgba(15, 23, 42, 0.08)'
                        }}
                      />
                    </div>
                  ))}
                </Space>
              ) : (
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无功能区域数据" />
              )}
            </Card>
          </Col>
        </Row>

        <Card
          size="small"
          style={panelCardStyle}
          headStyle={{ color: '#111827', borderBottom: '1px solid rgba(15, 23, 42, 0.08)' }}
          bodyStyle={{ padding: 18 }}
          title={
            <Space size={10}>
              <MessageOutlined style={{ color: '#0f62fe' }} />
              <span>LLM 决策记录</span>
            </Space>
          }
          extra={
            <Segmented
              size="small"
              value={llmDecisionFilter}
              onChange={value => setLlmDecisionFilter(value as 'all' | 'road_expansion' | 'zone_batch_count' | 'zone_location_type')}
              options={[
                { label: '全部', value: 'all' },
                { label: '道路扩展', value: 'road_expansion' },
                { label: '区域批次', value: 'zone_batch_count' },
                { label: '区域位置', value: 'zone_location_type' }
              ]}
            />
          }
        >
          {filteredLlmDecisions.length > 0 ? (
            <Space direction="vertical" style={{ width: '100%' }} size={12}>
              {filteredLlmDecisions.slice(0, 15).map(item => {
                const isExpanded = expandedDecisionIds.has(item.id);
                return (
                  <div
                    key={item.id}
                    style={{
                      borderRadius: 16,
                      background: '#f8fafc',
                      border: '1px solid rgba(15, 23, 42, 0.08)',
                      overflow: 'hidden'
                    }}
                  >
                    {/* 头部 - 始终显示 */}
                    <div
                      onClick={() => toggleDecisionExpand(item.id)}
                      style={{
                        padding: '12px 14px',
                        cursor: 'pointer',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        gap: 12,
                        flexWrap: 'wrap',
                        background: isExpanded ? 'rgba(15, 98, 254, 0.04)' : 'transparent',
                        transition: 'background 0.2s'
                      }}
                    >
                      <Space size={[8, 8]} wrap>
                        <Tag color={item.agent_type === 'planning' ? 'blue' : 'green'}>
                          {item.agent_type === 'planning' ? '路网规划' : '城市规划'}
                        </Tag>
                        <Tag color="geekblue">{llmCategoryLabelMap[item.category] || item.category}</Tag>
                        <Tag color={item.status === 'success' ? 'success' : item.status === 'fallback' ? 'warning' : 'default'}>
                          {llmStatusLabelMap[item.status] || item.status}
                        </Tag>
                        {typeof item.adopted === 'boolean' && (
                          <Tag color={item.adopted ? 'success' : 'default'}>
                            {item.adopted ? '已采纳' : '未采纳'}
                          </Tag>
                        )}
                      </Space>
                      <Space size={12}>
                        <Typography.Text style={{ color: '#64748b', fontSize: 12 }}>
                          t={Number(item.timestamp || 0).toFixed(1)}s
                        </Typography.Text>
                        {isExpanded ? (
                          <DownOutlined style={{ color: '#64748b', fontSize: 12 }} />
                        ) : (
                          <RightOutlined style={{ color: '#64748b', fontSize: 12 }} />
                        )}
                      </Space>
                    </div>

                    {/* 摘要 - 始终显示 */}
                    <div
                      style={{
                        padding: '0 14px 12px',
                        cursor: 'pointer'
                      }}
                      onClick={() => toggleDecisionExpand(item.id)}
                    >
                      <Typography.Text strong style={{ color: '#0f172a' }}>
                        {item.summary || 'LLM 决策'}
                      </Typography.Text>
                    </div>

                    {/* 展开内容 */}
                    {isExpanded && (
                      <div style={{ padding: '0 14px 14px' }}>
                        <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
                          <Button
                            size="small"
                            onClick={() => toggleDecisionExpand(item.id)}
                            style={{ borderRadius: 8 }}
                          >
                            收起详情
                          </Button>
                        </div>

                        {item.parsed_decision && Object.keys(item.parsed_decision).length > 0 && (
                          <div style={{ marginBottom: 12 }}>
                            <Typography.Text style={{ color: '#334155', fontSize: 12, display: 'block', marginBottom: 6, fontWeight: 500 }}>
                              决策内容
                            </Typography.Text>
                            <pre style={{ margin: 0, padding: 10, background: '#ffffff', borderRadius: 8, whiteSpace: 'pre-wrap', wordBreak: 'break-word', color: '#1e293b', fontSize: 12, fontFamily: 'Consolas, Monaco, monospace', border: '1px solid rgba(15, 23, 42, 0.06)' }}>
                              {JSON.stringify(item.parsed_decision, null, 2)}
                            </pre>
                          </div>
                        )}

                        <div style={{ marginBottom: 12 }}>
                          <Typography.Text style={{ color: '#334155', fontSize: 12, display: 'block', marginBottom: 6, fontWeight: 500 }}>
                            Prompt
                          </Typography.Text>
                          <pre style={{ margin: 0, padding: 10, background: '#ffffff', borderRadius: 8, whiteSpace: 'pre-wrap', wordBreak: 'break-word', color: '#475569', fontSize: 12, fontFamily: 'Consolas, Monaco, monospace', maxHeight: 200, overflow: 'auto', border: '1px solid rgba(15, 23, 42, 0.06)' }}>
                            {item.prompt || '无'}
                          </pre>
                        </div>

                        <div>
                          <Typography.Text style={{ color: '#334155', fontSize: 12, display: 'block', marginBottom: 6, fontWeight: 500 }}>
                            原始响应
                          </Typography.Text>
                          <pre style={{ margin: 0, padding: 10, background: '#ffffff', borderRadius: 8, whiteSpace: 'pre-wrap', wordBreak: 'break-word', color: '#475569', fontSize: 12, fontFamily: 'Consolas, Monaco, monospace', maxHeight: 200, overflow: 'auto', border: '1px solid rgba(15, 23, 42, 0.06)' }}>
                            {item.response || '无'}
                          </pre>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </Space>
          ) : (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无 LLM 决策记录" />
          )}
        </Card>

        <Card
          size="small"
          style={panelCardStyle}
          headStyle={{ color: '#111827', borderBottom: '1px solid rgba(15, 23, 42, 0.08)' }}
          bodyStyle={{ padding: 18 }}
          title={
            <Space size={10}>
              <ClusterOutlined style={{ color: '#0f62fe' }} />
              <span>智能体记忆</span>
            </Space>
          }
        >
          <AgentMemoryView agentMemories={agentMemories} agentsWithMemory={agentsWithMemory} />
        </Card>
      </Space>
    </div>
  );
};

export default RoadPlanningView;
