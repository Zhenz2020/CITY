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
    <Card title="仿真控制" size="small">
      <Space direction="vertical" style={{ width: '100%' }}>
        <Space>
          <Button
            type={isRunning ? "default" : "primary"}
            icon={<PlayCircleOutlined />}
            onClick={onStart}
            disabled={isRunning || !isConnected}
          >
            开始
          </Button>
          <Button
            type={isRunning ? "primary" : "default"}
            icon={<PauseCircleOutlined />}
            onClick={onPause}
            disabled={!isRunning}
          >
            暂停
          </Button>
          <Button icon={<ReloadOutlined />} onClick={onReset}>
            重置
          </Button>
        </Space>
        <Button icon={<CarOutlined />} onClick={onSpawnVehicle} block>
          生成车辆
        </Button>
        {statistics && (
          <>
            <Statistic title="活跃车辆" value={statistics.active_vehicles || 0} />
            <Statistic title="已完成车辆" value={statistics.total_vehicles_completed || 0} />
          </>
        )}
      </Space>
    </Card>
  );
};
