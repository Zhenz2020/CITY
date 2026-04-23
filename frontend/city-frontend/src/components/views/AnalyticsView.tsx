import React from 'react';
import { Card, Statistic, Row, Col } from 'antd';
import { DashboardOutlined } from '@ant-design/icons';

interface AnalyticsViewProps {
  statistics: any;
  network: any;
  vehicles: any[];
  trafficLights: any[];
  currentTime: number;
}

export const AnalyticsView: React.FC<AnalyticsViewProps> = ({
  statistics,
  vehicles,
  currentTime,
}) => {
  return (
    <div style={{ padding: 16 }}>
      <Card title={<><DashboardOutlined /> Analytics</>}>
        <Row gutter={16}>
          <Col span={8}>
            <Statistic title="Simulation Time" value={currentTime.toFixed(1)} suffix="s" />
          </Col>
          <Col span={8}>
            <Statistic title="Active Vehicles" value={statistics?.active_vehicles || vehicles.length} />
          </Col>
          <Col span={8}>
            <Statistic title="Completed Vehicles" value={statistics?.total_vehicles_completed || 0} />
          </Col>
        </Row>
      </Card>
    </div>
  );
};
