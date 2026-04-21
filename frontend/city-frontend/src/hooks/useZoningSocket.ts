import { useState, useEffect, useCallback, useRef } from 'react';
import { Zone } from '../types';
import { io, Socket } from 'socket.io-client';

interface ZoningState {
  zones: Zone[];
  zoning_agent: any;
  is_running: boolean;
  time: number;
}

export const useZoningSocket = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [zones, setZones] = useState<Zone[]>([]);
  const [zoningAgent, setZoningAgent] = useState<any>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const socketRef = useRef<Socket | null>(null);

  useEffect(() => {
    const socket = io('http://localhost:8000/zoning', {
      transports: ['websocket'],
      reconnection: true,
      reconnectionAttempts: 5,
    });
    socketRef.current = socket;

    socket.on('connect', () => {
      console.log('Connected to zoning backend');
      setIsConnected(true);
    });

    socket.on('disconnect', () => {
      console.log('Disconnected from zoning backend');
      setIsConnected(false);
    });

    socket.on('zoning_state', (data: ZoningState) => {
      setZones(data.zones);
      setZoningAgent(data.zoning_agent);
      setIsRunning(data.is_running);
      setCurrentTime(data.time);
    });

    return () => {
      socket.disconnect();
    };
  }, []);

  const startSimulation = useCallback(() => {
    socketRef.current?.emit('control', { action: 'start' });
  }, []);

  const pauseSimulation = useCallback(() => {
    socketRef.current?.emit('control', { action: 'pause' });
  }, []);

  const resetSimulation = useCallback(() => {
    socketRef.current?.emit('control', { action: 'reset' });
  }, []);

  return {
    isConnected,
    zones,
    zoningAgent,
    isRunning,
    currentTime,
    startSimulation,
    pauseSimulation,
    resetSimulation,
  };
};
