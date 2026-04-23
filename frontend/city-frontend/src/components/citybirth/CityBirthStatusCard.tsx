import React from 'react';
import { Card, Col, Empty, Row, Space, Statistic, Tag, Typography } from 'antd';
import { BranchesOutlined, RadarChartOutlined, RiseOutlined, RobotOutlined } from '@ant-design/icons';
import { ExpansionRecord, Network, PlanningAgentStatus, Vehicle, Zone, ZoningAgentStatus } from '../../types';

interface CityBirthStatusCardProps {
  currentTime: number;
  vehicles: Vehicle[];
  network: Network | null;
  zones: Zone[];
  expansionHistory: ExpansionRecord[];
  statistics: any;
  planningAgent: PlanningAgentStatus | null;
  zoningAgent: ZoningAgentStatus | null;
}

const statPanelStyle: React.CSSProperties = {
  borderRadius: 16,
  background: 'rgba(244, 251, 250, 0.96)',
  border: '1px solid rgba(142, 196, 199, 0.32)',
  padding: 14
};

export const CityBirthStatusCard: React.FC<CityBirthStatusCardProps> = ({
  currentTime,
  vehicles,
  network,
  zones,
  expansionHistory,
  statistics,
  planningAgent,
  zoningAgent
}) => {
  return (
    <Card
      size="small"
      style={{
        borderRadius: 20,
        border: '1px solid rgba(128, 186, 206, 0.3)',
        background: 'rgba(255,255,255,0.88)',
        boxShadow: '0 18px 44px rgba(129, 170, 188, 0.12)'
      }}
      headStyle={{ color: '#45636d', borderBottom: '1px solid rgba(129, 183, 196, 0.24)' }}
      bodyStyle={{ padding: 18 }}
      title={
        <Space size={10}>
          <RadarChartOutlined style={{ color: '#3f95a0' }} />
          <span>Runtime Status</span>
        </Space>
      }
    >
      <Row gutter={[12, 12]}>
        <Col span={8}>
          <div style={statPanelStyle}>
            <Statistic title="Simulation Time" value={currentTime} precision={1} suffix="s" valueStyle={{ color: '#48636c', fontSize: 16 }} />
          </div>
        </Col>
        <Col span={8}>
          <div style={statPanelStyle}>
            <Statistic title="Vehicles" value={vehicles.length} valueStyle={{ color: '#48636c', fontSize: 16 }} />
          </div>
        </Col>
        <Col span={8}>
          <div style={statPanelStyle}>
            <Statistic title="Nodes" value={network?.nodes.length || 0} valueStyle={{ color: '#48636c', fontSize: 16 }} />
          </div>
        </Col>
        <Col span={8}>
          <div style={statPanelStyle}>
            <Statistic title="Roads" value={network?.edges.length || 0} valueStyle={{ color: '#48636c', fontSize: 16 }} />
          </div>
        </Col>
        <Col span={8}>
          <div style={statPanelStyle}>
            <Statistic title="Zones" value={zones.length} valueStyle={{ color: '#48636c', fontSize: 16 }} />
          </div>
        </Col>
        <Col span={8}>
          <div style={statPanelStyle}>
            <Statistic title="Population" value={statistics?.total_population || 0} valueStyle={{ color: '#48636c', fontSize: 16 }} />
          </div>
        </Col>
        <Col span={8}>
          <div style={statPanelStyle}>
            <Statistic title="Expansions" value={expansionHistory.length} valueStyle={{ color: '#48636c', fontSize: 16 }} />
          </div>
        </Col>
      </Row>

      <div style={{ marginTop: 16 }}>
        <Space wrap>
          {typeof statistics?.active_vehicles === 'number' && <Tag color="blue">Active vehicles {statistics.active_vehicles}</Tag>}
          {typeof statistics?.average_speed === 'number' && <Tag color="cyan">Average speed {statistics.average_speed.toFixed(1)}</Tag>}
          {typeof statistics?.total_population === 'number' && statistics.total_population > 0 && (
            <Tag color="purple">Population {statistics.total_population}</Tag>
          )}
          {typeof statistics?.total_zones === 'number' && statistics.total_zones > 0 && (
            <Tag color="geekblue">Zones {statistics.total_zones}</Tag>
          )}
          {typeof statistics?.population_pressure === 'number' && (
            <Tag color={statistics.population_pressure > 0.7 ? 'red' : 'green'}>
              Population pressure {(statistics.population_pressure * 100).toFixed(0)}%
            </Tag>
          )}
        </Space>
      </div>

      <div style={{ marginTop: 18 }}>
        <Space size={8} style={{ marginBottom: 12 }}>
          <RobotOutlined style={{ color: '#5b9daa' }} />
          <Typography.Text style={{ color: '#4c6a74', fontSize: 13 }}>Planning Agent Status</Typography.Text>
        </Space>
        {planningAgent || zoningAgent ? (
          <Space direction="vertical" style={{ width: '100%' }} size={10}>
            {planningAgent && (
              <div style={statPanelStyle}>
                <Space wrap>
                  <BranchesOutlined style={{ color: '#58b38b' }} />
                  <Typography.Text style={{ color: '#47616a' }}>Road Planning</Typography.Text>
                  <Tag color="cyan">{planningAgent.state}</Tag>
                  <Tag color="green">Expansions {planningAgent.expansion_count}</Tag>
                  <Tag color="blue">OD {planningAgent.od_record_count}</Tag>
                </Space>
              </div>
            )}
            {zoningAgent && (
              <div style={statPanelStyle}>
                <Space wrap>
                  <RiseOutlined style={{ color: '#e4a44a' }} />
                  <Typography.Text style={{ color: '#47616a' }}>Urban Zoning</Typography.Text>
                  <Tag color="magenta">{zoningAgent.state}</Tag>
                  <Tag color="purple">Zones {zoningAgent.zone_count}</Tag>
                </Space>
              </div>
            )}
          </Space>
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No planning agent status available" />
        )}
      </div>
    </Card>
  );
};

export default CityBirthStatusCard;
