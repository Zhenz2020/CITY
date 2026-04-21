import { useState, useEffect, useCallback, useRef } from 'react';
import { Network, Vehicle, TrafficLight, ExpansionRecord, PlanningAgentStatus, ZoningAgentStatus, Zone, AgentMemory, LLMDecisionRecord } from '../types';
import { io, Socket } from 'socket.io-client';

interface PlanningState {
  network: Network;
  vehicles: Vehicle[];
  traffic_lights: TrafficLight[];
  zones: Zone[];
  planning_agent: PlanningAgentStatus | null;
  zoning_agent: ZoningAgentStatus | null;
  expansion_history: ExpansionRecord[];
  llm_decisions: LLMDecisionRecord[];
  statistics: any;
  time: number;
  is_running: boolean;
  agent_memories: AgentMemory[];
  agents_with_memory: any[];
}

interface PlanningStatePayload extends Partial<PlanningState> {
  agents?: {
    vehicles?: Vehicle[];
  };
}

const BACKEND_BASE_URL = 'http://localhost:5000';

export const usePlanningSocket = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [network, setNetwork] = useState<Network | null>(null);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [trafficLights, setTrafficLights] = useState<TrafficLight[]>([]);
  const [zones, setZones] = useState<Zone[]>([]);
  const [planningAgent, setPlanningAgent] = useState<PlanningAgentStatus | null>(null);
  const [zoningAgent, setZoningAgent] = useState<ZoningAgentStatus | null>(null);
  const [expansionHistory, setExpansionHistory] = useState<ExpansionRecord[]>([]);
  const [llmDecisions, setLlmDecisions] = useState<LLMDecisionRecord[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [statistics, setStatistics] = useState(null);
  const [agentMemories, setAgentMemories] = useState<AgentMemory[]>([]);
  const [agentsWithMemory, setAgentsWithMemory] = useState<any[]>([]);
  const socketRef = useRef<Socket | null>(null);

  const hasRenderableNetwork = useCallback((value: any): value is Network => {
    return Boolean(
      value &&
      Array.isArray(value.nodes) &&
      Array.isArray(value.edges) &&
      (value.nodes.length > 0 || value.edges.length > 0)
    );
  }, []);

  const normalizeExpansionRecord = useCallback((raw: any): ExpansionRecord => ({
    timestamp: Number(raw?.timestamp ?? raw?.time ?? 0),
    action: String(raw?.action ?? raw?.type ?? raw?.method ?? 'unknown'),
    details: raw?.details ?? raw,
    type: raw?.type,
    node_id: raw?.node_id,
    edge_id: raw?.edge_id,
    reverse_edge_id: raw?.reverse_edge_id,
    from_node: raw?.from_node,
    to_node: raw?.to_node,
    old_num_lanes: raw?.old_num_lanes,
    new_num_lanes: raw?.new_num_lanes
  }), []);

  const normalizePlanningState = useCallback((raw: PlanningStatePayload): PlanningState => ({
    network: raw.network || { nodes: [], edges: [] },
    vehicles: raw.vehicles || raw.agents?.vehicles || [],
    traffic_lights: raw.traffic_lights || [],
    zones: raw.zones || [],
    planning_agent: raw.planning_agent || null,
    zoning_agent: raw.zoning_agent || null,
    expansion_history: Array.isArray(raw.expansion_history)
      ? raw.expansion_history.map(normalizeExpansionRecord)
      : [],
    llm_decisions: Array.isArray((raw as any).llm_decisions) ? (raw as any).llm_decisions : [],
    statistics: raw.statistics || null,
    time: raw.time || 0,
    is_running: Boolean(raw.is_running),
    agent_memories: raw.agent_memories || [],
    agents_with_memory: raw.agents_with_memory || []
  }), [normalizeExpansionRecord]);

  const applyPlanningState = useCallback((data: PlanningState) => {
    setNetwork(prev => (hasRenderableNetwork(data.network) ? data.network : prev));
    setVehicles(data.vehicles);
    setTrafficLights(data.traffic_lights);
    setZones(data.zones);
    setPlanningAgent(data.planning_agent);
    setZoningAgent(data.zoning_agent);
    setExpansionHistory(data.expansion_history);
    setLlmDecisions(data.llm_decisions || []);
    setIsRunning(data.is_running);
    setCurrentTime(data.time);
    setStatistics(data.statistics);
    setAgentMemories(data.agent_memories || []);
    setAgentsWithMemory(data.agents_with_memory || []);
  }, [hasRenderableNetwork]);

  const fetchPlanningState = useCallback(async () => {
    try {
      const response = await fetch(`${BACKEND_BASE_URL}/api/planning/state`);
      if (!response.ok) {
        return;
      }
      const raw = await response.json();
      applyPlanningState(normalizePlanningState(raw));
    } catch (error) {
      console.error('Failed to fetch planning state:', error);
    }
  }, [applyPlanningState, normalizePlanningState]);

  useEffect(() => {
    const socket = io(BACKEND_BASE_URL, {
      reconnection: true,
      reconnectionAttempts: 5,
    });
    socketRef.current = socket;

    socket.on('connect', () => {
      console.log('Connected to planning backend');
      setIsConnected(true);
      socket.emit('planning_connect');
      socket.emit('get_planning_network');
      void fetchPlanningState();
    });

    socket.on('disconnect', () => {
      console.log('Disconnected from planning backend');
      setIsConnected(false);
    });

    socket.on('planning_network_data', (data: Network) => {
      if (hasRenderableNetwork(data)) {
        setNetwork(data);
      }
    });

    socket.on('planning_update', (data: PlanningStatePayload) => {
      applyPlanningState(normalizePlanningState(data));
    });

    return () => {
      socket.disconnect();
    };
  }, [applyPlanningState, fetchPlanningState, hasRenderableNetwork, normalizePlanningState]);

  const requestNetwork = useCallback(() => {
    socketRef.current?.emit('get_planning_network');
    void fetchPlanningState();
  }, [fetchPlanningState]);

  const startSimulation = useCallback(async (config?: any) => {
    await fetch(`${BACKEND_BASE_URL}/api/planning/control`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'start', agent_configs: config })
    });
    socketRef.current?.emit('get_planning_network');
    void fetchPlanningState();
  }, [fetchPlanningState]);

  const pauseSimulation = useCallback(async () => {
    await fetch(`${BACKEND_BASE_URL}/api/planning/control`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'pause' })
    });
    void fetchPlanningState();
  }, [fetchPlanningState]);

  const resetSimulation = useCallback(async (config?: any) => {
    await fetch(`${BACKEND_BASE_URL}/api/planning/control`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'reset', agent_configs: config })
    });
    setExpansionHistory([]);
    socketRef.current?.emit('get_planning_network');
    void fetchPlanningState();
  }, [fetchPlanningState]);

  return {
    isConnected,
    network,
    vehicles,
    trafficLights,
    zones,
    planningAgent,
    zoningAgent,
    expansionHistory,
    llmDecisions,
    isRunning,
    currentTime,
    statistics,
    agentMemories,
    agentsWithMemory,
    requestNetwork,
    startSimulation,
    pauseSimulation,
    resetSimulation,
  };
};
