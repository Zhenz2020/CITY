import React from 'react';
import { Card, Button, Space, Tag } from 'antd';
import { PlayCircleOutlined, PauseCircleOutlined, HistoryOutlined } from '@ant-design/icons';
import { SimulationCanvas } from '../SimulationCanvas';

interface PlaybackViewProps {
  network: any;
  vehicles: any[];
  pedestrians: any[];
  trafficLights: any[];
  statistics: any;
  decisions: any[];
  isRunning: boolean;
  currentTime: number;
  onStart: () => void;
  onPause: () => void;
  onReset: () => void;
}

export const PlaybackView: React.FC<PlaybackViewProps> = ({
  network,
  vehicles,
  trafficLights,
  isRunning,
  currentTime,
  onStart,
  onPause,
  onReset,
}) => {
  return (
    <div style={{ height: '100%', display: 'flex', gap: 16 }}>
      <div style={{ flex: 2 }}>
        <SimulationCanvas
          network={network}
          vehicles={vehicles}
          pedestrians={[]}
          trafficLights={trafficLights}
          selectedAgentId={null}
          onSelectAgent={() => {}}
          width={900}
          height={600}
        />
      </div>
      <div style={{ flex: 1 }}>
        <Card title={<><HistoryOutlined /> Playback Control</>} size="small">
          <Space direction="vertical" style={{ width: '100%' }}>
            <Space>
              <Button
                type={isRunning ? 'default' : 'primary'}
                icon={<PlayCircleOutlined />}
                onClick={onStart}
                disabled={isRunning}
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
              <Button onClick={onReset}>Reset</Button>
            </Space>
            <div>
              <span>Current Time: </span>
              <Tag color="blue" style={{ fontSize: 16 }}>
                {currentTime.toFixed(1)}s
              </Tag>
            </div>
            <div>
              <span>Vehicles: </span>
              <Tag color="blue">{vehicles.length}</Tag>
            </div>
          </Space>
        </Card>
      </div>
    </div>
  );
};
