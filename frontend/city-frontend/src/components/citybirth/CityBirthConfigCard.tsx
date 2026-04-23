import React from 'react';
import { Card, Col, InputNumber, Row, Select, Space, Switch, Tag, Typography } from 'antd';
import { ControlOutlined, DeploymentUnitOutlined, RadiusSettingOutlined } from '@ant-design/icons';

interface CityBirthConfigCardProps {
  birthConfig: any;
  onBirthConfigChange: (config: any) => void;
  isRunning: boolean;
}

const fieldLabelStyle: React.CSSProperties = {
  display: 'block',
  marginBottom: 8,
  color: '#71909a',
  fontSize: 12,
  letterSpacing: 0.5
};

const fieldCardStyle: React.CSSProperties = {
  background: 'rgba(245, 252, 251, 0.96)',
  border: '1px solid rgba(142, 196, 199, 0.32)',
  borderRadius: 16,
  padding: 14
};

export const CityBirthConfigCard: React.FC<CityBirthConfigCardProps> = ({
  birthConfig,
  onBirthConfigChange,
  isRunning
}) => {
  const birthDisabled = isRunning || !birthConfig?.city_birth;

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
      headStyle={{
        borderBottom: '1px solid rgba(129, 183, 196, 0.24)',
        color: '#45636d'
      }}
      bodyStyle={{ padding: 18 }}
      title={
        <Space size={10}>
          <ControlOutlined style={{ color: '#3f95a0' }} />
          <span>City Birth Settings</span>
          <Tag color={birthConfig?.city_birth ? 'cyan' : 'default'}>
            {birthConfig?.city_birth ? 'Enabled' : 'Disabled'}
          </Tag>
        </Space>
      }
    >
      <div style={{ ...fieldCardStyle, marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
          <div>
            <Typography.Text style={{ color: '#43606a', fontSize: 15 }}>Master Switch</Typography.Text>
            <div style={{ color: '#7e99a1', fontSize: 12, marginTop: 4 }}>
              Controls whether the initial city is generated automatically with City Birth rules.
            </div>
          </div>
          <Switch
            checked={birthConfig?.city_birth}
            disabled={isRunning}
            onChange={checked => onBirthConfigChange({ ...birthConfig, city_birth: checked })}
          />
        </div>
      </div>

      <Space direction="vertical" style={{ width: '100%' }} size={16}>
        <div>
          <Space size={8} style={{ marginBottom: 12 }}>
            <DeploymentUnitOutlined style={{ color: '#5ca8b1' }} />
            <Typography.Text style={{ color: '#4c6a74', fontSize: 13 }}>Topology</Typography.Text>
          </Space>
          <Row gutter={[12, 12]}>
            <Col span={24}>
              <div style={fieldCardStyle}>
                <label style={fieldLabelStyle}>Network Type</label>
                <Select
                  style={{ width: '100%' }}
                  value={birthConfig?.city_birth_network_type}
                  disabled={birthDisabled}
                  options={[
                    { label: 'Procedural', value: 'procedural' },
                    { label: 'Grid', value: 'grid' },
                    { label: 'Cross', value: 'cross' },
                    { label: 'Radial', value: 'radial' }
                  ]}
                  onChange={value => onBirthConfigChange({ ...birthConfig, city_birth_network_type: value })}
                />
              </div>
            </Col>
            <Col xs={24} sm={12}>
              <div style={fieldCardStyle}>
                <label style={fieldLabelStyle}>Random Seed</label>
                <InputNumber
                  style={{ width: '100%' }}
                  value={birthConfig?.city_birth_seed}
                  disabled={birthDisabled}
                  onChange={value => onBirthConfigChange({ ...birthConfig, city_birth_seed: Number(value ?? 0) })}
                />
              </div>
            </Col>
            <Col xs={24} sm={12}>
              <div style={fieldCardStyle}>
                <label style={fieldLabelStyle}>Node Count</label>
                <InputNumber
                  style={{ width: '100%' }}
                  min={4}
                  max={128}
                  value={birthConfig?.city_birth_nodes}
                  disabled={birthDisabled}
                  onChange={value => onBirthConfigChange({ ...birthConfig, city_birth_nodes: Number(value ?? 0) })}
                />
              </div>
            </Col>
          </Row>
        </div>

        <div>
          <Space size={8} style={{ marginBottom: 12 }}>
            <RadiusSettingOutlined style={{ color: '#58b38b' }} />
            <Typography.Text style={{ color: '#4c6a74', fontSize: 13 }}>Spatial Scale</Typography.Text>
          </Space>
          <Row gutter={[12, 12]}>
            <Col xs={24} sm={8}>
              <div style={fieldCardStyle}>
                <label style={fieldLabelStyle}>City Scale</label>
                <InputNumber
                  style={{ width: '100%' }}
                  min={20}
                  max={1000}
                  value={birthConfig?.city_birth_scale}
                  disabled={birthDisabled}
                  onChange={value => onBirthConfigChange({ ...birthConfig, city_birth_scale: Number(value ?? 0) })}
                />
              </div>
            </Col>
            <Col xs={24} sm={8}>
              <div style={fieldCardStyle}>
                <label style={fieldLabelStyle}>Min Edge Length</label>
                <InputNumber
                  style={{ width: '100%' }}
                  min={10}
                  max={5000}
                  value={birthConfig?.city_birth_min_edge}
                  disabled={birthDisabled}
                  onChange={value => onBirthConfigChange({ ...birthConfig, city_birth_min_edge: Number(value ?? 0) })}
                />
              </div>
            </Col>
            <Col xs={24} sm={8}>
              <div style={fieldCardStyle}>
                <label style={fieldLabelStyle}>Max Edge Length</label>
                <InputNumber
                  style={{ width: '100%' }}
                  min={10}
                  max={5000}
                  value={birthConfig?.city_birth_max_edge}
                  disabled={birthDisabled}
                  onChange={value => onBirthConfigChange({ ...birthConfig, city_birth_max_edge: Number(value ?? 0) })}
                />
              </div>
            </Col>
          </Row>
        </div>
      </Space>
    </Card>
  );
};

export default CityBirthConfigCard;
