import React from 'react';
import { Card, Button, Space, Statistic } from 'antd';
import { PlayCircleOutlined, PauseCircleOutlined, ReloadOutlined, CarOutlined } from '@ant-design/icons';

interface ControlPanelProps {
  isRunning: boolean;
  isConnected: boolean;
  statistics: any;
  onStart: () => void;
  onPause: () => void;
  onReset: () => void;
  onSpawnVehicle: () => void;
}

export const ControlPanel: React.FC<ControlPanelProps> = ({
  isRunning,
  isConnected,
  statistics,
  onStart,
  onPause,
  onReset,
  onSpawnVehicle,
}) => {
  return (
    <Card title="Simulation Control" size="small">
      <Space direction="vertical" style={{ width: '100%' }}>
        <Space>
          <Button
            type={isRunning ? 'default' : 'primary'}
            icon={<PlayCircleOutlined />}
            onClick={onStart}
            disabled={isRunning || !isConnected}
          >
            Start
          </Button>
          <Button
            type={isRunning ? 'primary' : 'default'}
            icon={<PauseCircleOutlined />}
            onClick={onPause}
            disabled={!isRunning}
          >
            Pause
          </Button>
          <Button icon={<ReloadOutlined />} onClick={onReset}>
            Reset
          </Button>
        </Space>
        <Button icon={<CarOutlined />} onClick={onSpawnVehicle} block>
          Spawn Vehicle
        </Button>
        {statistics && (
          <>
            <Statistic title="Active Vehicles" value={statistics.active_vehicles || 0} />
            <Statistic title="Completed Vehicles" value={statistics.total_vehicles_completed || 0} />
          </>
        )}
      </Space>
    </Card>
  );
};
