import { useState, useEffect, useCallback, useRef } from 'react';
import { Network, Vehicle, Pedestrian, TrafficLight, AgentDecision, SimulationStatistics } from '../types';
import { io, Socket } from 'socket.io-client';

interface SimulationState {
  agents: {
    vehicles: Vehicle[];
    pedestrians: Pedestrian[];
  };
  traffic_lights: TrafficLight[];
  traffic_light_agents: any[];
  statistics: SimulationStatistics | null;
  time: number;
  is_running: boolean;
}

const BACKEND_BASE_URL = 'http://localhost:5000';

export const useSocket = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [network, setNetwork] = useState<Network | null>(null);
  const [simulationState, setSimulationState] = useState<SimulationState | null>(null);
  const [decisions, setDecisions] = useState<AgentDecision[]>([]);
  const socketRef = useRef<Socket | null>(null);

  const fetchNetwork = useCallback(async () => {
    try {
      const response = await fetch(`${BACKEND_BASE_URL}/api/network`);
      if (!response.ok) {
        return;
      }
      const data: Network = await response.json();
      setNetwork(data);
    } catch (error) {
      console.error('Failed to fetch network data:', error);
    }
  }, []);

  const fetchSimulationState = useCallback(async () => {
    try {
      const response = await fetch(`${BACKEND_BASE_URL}/api/state`);
      if (!response.ok) {
        return;
      }
      const data: SimulationState = await response.json();
      setSimulationState(data);
    } catch (error) {
      console.error('Failed to fetch simulation state:', error);
    }
  }, []);

  useEffect(() => {
    const socket = io(BACKEND_BASE_URL, {
      reconnection: true,
      reconnectionAttempts: 5,
    });
    socketRef.current = socket;

    socket.on('connect', () => {
      console.log('Connected to backend');
      setIsConnected(true);
      socket.emit('get_network');
      void fetchNetwork();
      void fetchSimulationState();
    });

    socket.on('disconnect', () => {
      console.log('Disconnected from backend');
      setIsConnected(false);
    });

    socket.on('network_data', (data: Network) => {
      console.log('Received network data:', data);
      setNetwork(data);
    });

    socket.on('simulation_update', (data: SimulationState) => {
      setSimulationState(data);
    });

    socket.on('agent_decision', (data: AgentDecision) => {
      setDecisions(prev => [...prev, data]);
    });

    return () => {
      socket.disconnect();
    };
  }, [fetchNetwork, fetchSimulationState]);

  const startSimulation = useCallback(async () => {
    await fetch(`${BACKEND_BASE_URL}/api/control`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'start' })
    });
    void fetchSimulationState();
    void fetchNetwork();
  }, [fetchNetwork, fetchSimulationState]);

  const pauseSimulation = useCallback(async () => {
    await fetch(`${BACKEND_BASE_URL}/api/control`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'pause' })
    });
    void fetchSimulationState();
  }, [fetchSimulationState]);

  const resetSimulation = useCallback(async () => {
    await fetch(`${BACKEND_BASE_URL}/api/control`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'reset' })
    });
    setDecisions([]);
    void fetchSimulationState();
    void fetchNetwork();
  }, [fetchNetwork, fetchSimulationState]);

  const spawnVehicle = useCallback(() => {
    socketRef.current?.emit('spawn_vehicle');
  }, []);

  const getAgentDecision = useCallback(async (agentId: string) => {
    try {
      const response = await fetch(`${BACKEND_BASE_URL}/api/agent/${agentId}/decision`, {
        method: 'POST'
      });
      if (!response.ok) {
        return;
      }
      const data = await response.json();
      setDecisions(prev => [
        ...prev,
        {
          agent_id: data.agent_id,
          agent_type: 'vehicle',
          timestamp: data.timestamp ?? Date.now() / 1000,
          decision: data.decision,
          context: data.perception
        }
      ]);
    } catch (error) {
      console.error('Failed to fetch agent decision:', error);
    }
  }, []);

  const getTrafficLightDecision = useCallback(async (agentId: string) => {
    try {
      await fetch(`${BACKEND_BASE_URL}/api/traffic-light/${agentId}/status`);
    } catch (error) {
      console.error('Failed to fetch traffic light status:', error);
    }
  }, []);

  const requestNetwork = useCallback(() => {
    socketRef.current?.emit('get_network');
    void fetchNetwork();
  }, [fetchNetwork]);

  return {
    isConnected,
    network,
    simulationState,
    decisions,
    startSimulation,
    pauseSimulation,
    resetSimulation,
    spawnVehicle,
    getAgentDecision,
    getTrafficLightDecision,
    requestNetwork,
  };
};
