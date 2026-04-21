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
          <span>智能体参数</span>
        </Space>
      }
    >
      <Space direction="vertical" style={{ width: '100%' }} size={12}>
        <ConfigRow
          title="车辆智能体"
          desc="控制车辆的感知、决策与行动。"
          checked={config.vehicle}
          onChange={checked => onChange({ ...config, vehicle: checked })}
        />
        <ConfigRow
          title="信号灯智能体"
          desc="控制路口相位和交通节奏。"
          checked={config.traffic_light}
          onChange={checked => onChange({ ...config, traffic_light: checked })}
        />
        <ConfigRow
          title="路网规划智能体"
          desc="控制道路扩容和网络生长。"
          checked={config.road_planning}
          onChange={checked => onChange({ ...config, road_planning: checked })}
        />
        <ConfigRow
          title="城市分区智能体"
          desc="控制功能区布局和区域演化。"
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
        这些开关会在启动 City Birth 时直接组合进后端配置。
      </div>
    </Card>
  );
};

export default LLMConfigPanel;
