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
          <span>运行态势</span>
        </Space>
      }
    >
      <Row gutter={[12, 12]}>
        <Col span={8}>
          <div style={statPanelStyle}>
            <Statistic title="仿真时间" value={currentTime} precision={1} suffix="s" valueStyle={{ color: '#48636c', fontSize: 16 }} />
          </div>
        </Col>
        <Col span={8}>
          <div style={statPanelStyle}>
            <Statistic title="在线车辆" value={vehicles.length} valueStyle={{ color: '#48636c', fontSize: 16 }} />
          </div>
        </Col>
        <Col span={8}>
          <div style={statPanelStyle}>
            <Statistic title="节点数量" value={network?.nodes.length || 0} valueStyle={{ color: '#48636c', fontSize: 16 }} />
          </div>
        </Col>
        <Col span={8}>
          <div style={statPanelStyle}>
            <Statistic title="道路数量" value={network?.edges.length || 0} valueStyle={{ color: '#48636c', fontSize: 16 }} />
          </div>
        </Col>
        <Col span={8}>
          <div style={statPanelStyle}>
            <Statistic title="区域数量" value={zones.length} valueStyle={{ color: '#48636c', fontSize: 16 }} />
          </div>
        </Col>
        <Col span={8}>
          <div style={statPanelStyle}>
            <Statistic title="总人口" value={statistics?.total_population || 0} valueStyle={{ color: '#48636c', fontSize: 16 }} />
          </div>
        </Col>
        <Col span={8}>
          <div style={statPanelStyle}>
            <Statistic title="扩容次数" value={expansionHistory.length} valueStyle={{ color: '#48636c', fontSize: 16 }} />
          </div>
        </Col>
      </Row>

      <div style={{ marginTop: 16 }}>
        <Space wrap>
          {typeof statistics?.active_vehicles === 'number' && <Tag color="blue">活跃车辆 {statistics.active_vehicles}</Tag>}
          {typeof statistics?.average_speed === 'number' && <Tag color="cyan">平均速度 {statistics.average_speed.toFixed(1)}</Tag>}
          {typeof statistics?.total_population === 'number' && statistics.total_population > 0 && (
            <Tag color="purple">人口 {statistics.total_population}</Tag>
          )}
          {typeof statistics?.total_zones === 'number' && statistics.total_zones > 0 && (
            <Tag color="geekblue">功能区 {statistics.total_zones}</Tag>
          )}
          {typeof statistics?.population_pressure === 'number' && (
            <Tag color={statistics.population_pressure > 0.7 ? 'red' : 'green'}>
              人口压力 {(statistics.population_pressure * 100).toFixed(0)}%
            </Tag>
          )}
        </Space>
      </div>

      <div style={{ marginTop: 18 }}>
        <Space size={8} style={{ marginBottom: 12 }}>
          <RobotOutlined style={{ color: '#5b9daa' }} />
          <Typography.Text style={{ color: '#4c6a74', fontSize: 13 }}>规划代理状态</Typography.Text>
        </Space>
        {planningAgent || zoningAgent ? (
          <Space direction="vertical" style={{ width: '100%' }} size={10}>
            {planningAgent && (
              <div style={statPanelStyle}>
                <Space wrap>
                  <BranchesOutlined style={{ color: '#58b38b' }} />
                  <Typography.Text style={{ color: '#47616a' }}>路网规划</Typography.Text>
                  <Tag color="cyan">{planningAgent.state}</Tag>
                  <Tag color="green">扩容 {planningAgent.expansion_count}</Tag>
                  <Tag color="blue">OD {planningAgent.od_record_count}</Tag>
                </Space>
              </div>
            )}
            {zoningAgent && (
              <div style={statPanelStyle}>
                <Space wrap>
                  <RiseOutlined style={{ color: '#e4a44a' }} />
                  <Typography.Text style={{ color: '#47616a' }}>城市分区</Typography.Text>
                  <Tag color="magenta">{zoningAgent.state}</Tag>
                  <Tag color="purple">区域 {zoningAgent.zone_count}</Tag>
                </Space>
              </div>
            )}
          </Space>
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无规划代理状态" />
        )}
      </div>
    </Card>
  );
};

export default CityBirthStatusCard;
