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
  vehicles,
  selectedAgentId,
  decisions,
}) => {
  const selectedVehicle = vehicles.find(v => v.id === selectedAgentId);
  const vehicleDecisions = decisions.filter(d => d.agent_id === selectedAgentId);

  return (
    <div style={{ padding: 16 }}>
      <Card title={<><RobotOutlined /> AI Decision Chain</>}>
        {selectedVehicle ? (
          <div>
            <h3>Selected Vehicle: {selectedVehicle.id}</h3>
            <p>Type: {selectedVehicle.vehicle_type}</p>
            <p>Speed: {selectedVehicle.speed.toFixed(2)} m/s</p>
            <h4>Decision History:</h4>
            {vehicleDecisions.map((d, idx) => (
              <Card key={idx} size="small" style={{ marginBottom: 8 }}>
                <p>Action: {d.decision?.action}</p>
                <p>Reason: {d.decision?.reason}</p>
              </Card>
            ))}
          </div>
        ) : (
          <Empty description="Click a vehicle to inspect its AI decision chain" />
        )}
      </Card>
    </div>
  );
};
