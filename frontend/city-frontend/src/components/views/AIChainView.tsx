import React from 'react';
import { Card, Empty } from 'antd';
import { RobotOutlined } from '@ant-design/icons';

interface AIChainViewProps {
  network: any;
  vehicles: any[];
  pedestrians: any[];
  trafficLights: any[];
  trafficLightAgents: any[];
  selectedAgentId: string | null;
  selectedAgentType: string | null;
  decisions: any[];
  onSelectAgent: (agentId: string | null, agentType?: 'vehicle' | 'pedestrian' | 'traffic_light') => void;
}

export const AIChainView: React.FC<AIChainViewProps> = ({
  network,
  vehicles,
  selectedAgentId,
  decisions,
}) => {
  const selectedVehicle = vehicles.find(v => v.id === selectedAgentId);
  const vehicleDecisions = decisions.filter(d => d.agent_id === selectedAgentId);

  return (
    <div style={{ padding: 16 }}>
      <Card title={<><RobotOutlined /> AI决策链</>}>
        {selectedVehicle ? (
          <div>
            <h3>选中车辆: {selectedVehicle.id}</h3>
            <p>类型: {selectedVehicle.vehicle_type}</p>
            <p>速度: {selectedVehicle.speed.toFixed(2)} m/s</p>
            <h4>决策历史:</h4>
            {vehicleDecisions.map((d, idx) => (
              <Card key={idx} size="small" style={{ marginBottom: 8 }}>
                <p>动作: {d.decision?.action}</p>
                <p>原因: {d.decision?.reason}</p>
              </Card>
            ))}
          </div>
        ) : (
          <Empty description="点击车辆查看AI决策链" />
        )}
      </Card>
    </div>
  );
};
