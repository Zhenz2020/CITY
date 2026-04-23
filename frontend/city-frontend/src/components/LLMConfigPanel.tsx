import React from 'react';
import { Card, Space, Switch, Typography } from 'antd';
import { ApiOutlined, RobotOutlined } from '@ant-design/icons';

export interface AgentLLMConfig {
  vehicle: boolean;
  traffic_light: boolean;
  road_planning: boolean;
  zoning: boolean;
}

interface LLMConfigPanelProps {
  config: AgentLLMConfig;
  onChange: (config: AgentLLMConfig) => void;
}

const itemStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: 12,
  padding: '12px 14px',
  borderRadius: 14,
  background: 'rgba(245, 252, 251, 0.96)',
  border: '1px solid rgba(142, 196, 199, 0.32)'
};

const ConfigRow: React.FC<{
  title: string;
  desc: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}> = ({ title, desc, checked, onChange }) => (
  <div style={itemStyle}>
    <div>
      <Typography.Text style={{ color: '#47616a', display: 'block' }}>{title}</Typography.Text>
      <Typography.Text style={{ color: '#7e99a1', fontSize: 12 }}>{desc}</Typography.Text>
    </div>
    <Switch checked={checked} onChange={onChange} />
  </div>
);

export const LLMConfigPanel: React.FC<LLMConfigPanelProps> = ({ config, onChange }) => {
  return (
    <Card
      size="small"
      style={{
        borderRadius: 20,
        border: '1px solid rgba(128, 186, 206, 0.3)',
        background: 'rgba(255,255,255,0.88)',
        boxShadow: '0 18px 44px rgba(129, 170, 188, 0.12)',
        height: '100%'
      }}
      headStyle={{ color: '#45636d', borderBottom: '1px solid rgba(129, 183, 196, 0.24)' }}
      bodyStyle={{ padding: 18 }}
      title={
        <Space size={10}>
          <ApiOutlined style={{ color: '#3f95a0' }} />
          <span>Agent Settings</span>
        </Space>
      }
    >
      <Space direction="vertical" style={{ width: '100%' }} size={12}>
        <ConfigRow
          title="Vehicle Agent"
          desc="Controls vehicle perception, decision making, and actions."
          checked={config.vehicle}
          onChange={checked => onChange({ ...config, vehicle: checked })}
        />
        <ConfigRow
          title="Traffic Light Agent"
          desc="Controls intersection phases and traffic rhythm."
          checked={config.traffic_light}
          onChange={checked => onChange({ ...config, traffic_light: checked })}
        />
        <ConfigRow
          title="Road Planning Agent"
          desc="Controls road expansion and network growth."
          checked={config.road_planning}
          onChange={checked => onChange({ ...config, road_planning: checked })}
        />
        <ConfigRow
          title="Urban Zoning Agent"
          desc="Controls district layout and zone evolution."
          checked={config.zoning}
          onChange={checked => onChange({ ...config, zoning: checked })}
        />
      </Space>

      <div
        style={{
          marginTop: 14,
          padding: '10px 12px',
          borderRadius: 14,
          background: 'rgba(238, 248, 247, 0.95)',
          color: '#7d98a0',
          fontSize: 12,
          border: '1px solid rgba(142, 196, 199, 0.24)'
        }}
      >
        <RobotOutlined style={{ marginRight: 8, color: '#58a9b5' }} />
        These switches are merged directly into the backend configuration when City Birth starts.
      </div>
    </Card>
  );
};

export default LLMConfigPanel;
