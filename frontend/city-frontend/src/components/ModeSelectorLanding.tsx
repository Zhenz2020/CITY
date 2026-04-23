import React, { useState } from 'react';
import { Badge, Button, Card, Col, Divider, Modal, Row, Space, Tag, Typography } from 'antd';
import {
  ApartmentOutlined,
  BranchesOutlined,
  CarOutlined,
  CheckCircleFilled,
  ClusterOutlined,
  DatabaseOutlined,
  DeploymentUnitOutlined,
  GlobalOutlined,
  RadarChartOutlined,
  RobotOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';

const { Title, Paragraph, Text } = Typography;

type AppMode = 'simulation' | 'citybirth';

interface ModeSelectorLandingProps {
  onSelectMode: (mode: AppMode) => void;
  isConnected: boolean;
}

const introParagraphs = [
  'TASP 3.0 studies how transportation behavior, planning logic, and infrastructure co-evolve inside a unified simulation environment.',
  'The platform combines agent-based behavior, traffic operations, and AI-assisted planning into a single interactive workspace rather than separating them into disconnected tools.',
  'Use Simulation Mode for fixed-network inspection and replay. Use City Birth Mode when you want to observe road growth, zoning, and emergent urban structure over time.'
];

const systemCards = [
  {
    title: 'Simulation Engine',
    value: 'Ready',
    icon: <ThunderboltOutlined style={{ fontSize: 18, color: '#0f62fe' }} />,
    accent: '#e8f1ff',
    desc: 'Playback, runtime control, and state updates'
  },
  {
    title: 'Agent Stack',
    value: 'Multi-Agent',
    icon: <RobotOutlined style={{ fontSize: 18, color: '#16803c' }} />,
    accent: '#eaf8ef',
    desc: 'Vehicle, signal, planning, and zoning agents'
  },
  {
    title: 'Spatial Model',
    value: 'Macro + Micro',
    icon: <ClusterOutlined style={{ fontSize: 18, color: '#b45309' }} />,
    accent: '#fff2e2',
    desc: 'Road network, zones, flows, and runtime metrics'
  },
  {
    title: 'Data Layer',
    value: 'Live Views',
    icon: <DatabaseOutlined style={{ fontSize: 18, color: '#7c3aed' }} />,
    accent: '#f3ebff',
    desc: 'Analytics, logs, memory, and decision traces'
  }
];

const modeCards = [
  {
    key: 'simulation' as AppMode,
    title: 'Simulation Mode',
    subtitle: 'Fixed Network Workspace',
    accent: '#0f62fe',
    icon: <GlobalOutlined style={{ fontSize: 30, color: '#0f62fe' }} />,
    summary: 'Inspect an existing road network, replay behavior, and compare AI decisions in a stable operating context.',
    bullets: ['Playback and timeline control', 'AI decision-chain inspection', 'Analytics under fixed topology']
  },
  {
    key: 'citybirth' as AppMode,
    title: 'City Birth Mode',
    subtitle: 'Dynamic Growth Workspace',
    accent: '#16803c',
    icon: <ApartmentOutlined style={{ fontSize: 30, color: '#16803c' }} />,
    summary: 'Launch the integrated planning workspace where road growth, zoning, traffic demand, and agent coordination evolve together.',
    bullets: ['Road expansion and zoning', 'LLM planning records', '2D and 3D city views']
  }
];

const quickFacts = [
  { label: 'Default View', value: 'Software Console' },
  { label: 'Primary Entry', value: 'Mode Launcher' },
  { label: 'Runtime Status', value: 'Backend-aware' },
  { label: 'Interface Style', value: 'Operational' }
];

export const ModeSelectorLanding: React.FC<ModeSelectorLandingProps> = ({
  onSelectMode,
  isConnected,
}) => {
  const [isIntroOpen, setIsIntroOpen] = useState(false);

  return (
    <div
      style={{
        minHeight: 'calc(100vh - 72px)',
        padding: '20px 20px 28px',
        background:
          'radial-gradient(circle at top left, rgba(15,98,254,0.12), transparent 26%), radial-gradient(circle at top right, rgba(22,128,60,0.10), transparent 28%), linear-gradient(180deg, #eef3f8 0%, #f4f7fb 48%, #f7f9fc 100%)'
      }}
    >
      <div style={{ maxWidth: 1380, margin: '0 auto' }}>
        <div
          style={{
            borderRadius: 28,
            overflow: 'hidden',
            border: '1px solid rgba(15, 23, 42, 0.08)',
            boxShadow: '0 24px 80px rgba(15, 23, 42, 0.10)',
            background: 'rgba(255,255,255,0.78)',
            backdropFilter: 'blur(16px)',
            marginBottom: 18
          }}
        >
          <div
            style={{
              padding: '18px 22px',
              background: 'linear-gradient(90deg, #0f172a 0%, #12253b 54%, #17334d 100%)',
              borderBottom: '1px solid rgba(255,255,255,0.08)'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 18, alignItems: 'center', flexWrap: 'wrap' }}>
              <Space size={14} wrap>
                <div
                  style={{
                    width: 42,
                    height: 42,
                    borderRadius: 14,
                    display: 'grid',
                    placeItems: 'center',
                    background: 'linear-gradient(135deg, #1d4ed8 0%, #22c55e 100%)',
                    color: '#fff'
                  }}
                >
                  <ThunderboltOutlined />
                </div>
                <div>
                  <div style={{ color: '#e2e8f0', fontSize: 12, letterSpacing: 1.6, textTransform: 'uppercase' }}>
                    TASP 3.0
                  </div>
                  <div style={{ color: '#f8fafc', fontSize: 22, fontWeight: 700 }}>
                    Transport Agent-based Simulation Platform
                  </div>
                </div>
              </Space>

              <Space size={10} wrap>
                <Tag color="blue" style={{ borderRadius: 999, padding: '4px 12px' }}>
                  Macro-Micro Integrated
                </Tag>
                <Tag color="purple" style={{ borderRadius: 999, padding: '4px 12px' }}>
                  Generative AI Enabled
                </Tag>
                <Badge
                  status={isConnected ? 'success' : 'error'}
                  text={<span style={{ color: '#cbd5e1' }}>{isConnected ? 'Backend Online' : 'Backend Offline'}</span>}
                />
              </Space>
            </div>
          </div>

          <div style={{ padding: 22 }}>
            <Row gutter={[18, 18]}>
              <Col xs={24} xl={16}>
                <Card
                  bordered={false}
                  style={{
                    borderRadius: 24,
                    background: 'linear-gradient(135deg, #ffffff 0%, #f8fbff 100%)',
                    boxShadow: 'inset 0 0 0 1px rgba(15, 23, 42, 0.05)',
                    height: '100%'
                  }}
                  bodyStyle={{ padding: 24 }}
                >
                  <Space direction="vertical" size={18} style={{ width: '100%' }}>
                    <div>
                      <Text style={{ color: '#3b82f6', fontWeight: 700, letterSpacing: 1.2, textTransform: 'uppercase' }}>
                        Workspace Launcher
                      </Text>
                      <Title level={2} style={{ margin: '8px 0 10px', color: '#0f172a' }}>
                        Generative AI-Powered Integrated Macro-Micro Simulation Platform
                      </Title>
                      <Paragraph style={{ margin: 0, color: '#475569', fontSize: 15, lineHeight: 1.85, maxWidth: 860 }}>
                        Open a working mode, inspect live system status, and move directly into simulation operations. This homepage now behaves like a product launcher instead of an introduction page.
                      </Paragraph>
                    </div>

                    <Row gutter={[12, 12]}>
                      {quickFacts.map(item => (
                        <Col xs={24} sm={12} lg={6} key={item.label}>
                          <div
                            style={{
                              borderRadius: 18,
                              background: '#ffffff',
                              border: '1px solid rgba(15, 23, 42, 0.07)',
                              padding: '14px 16px'
                            }}
                          >
                            <div style={{ color: '#64748b', fontSize: 12, marginBottom: 6 }}>{item.label}</div>
                            <div style={{ color: '#0f172a', fontWeight: 700 }}>{item.value}</div>
                          </div>
                        </Col>
                      ))}
                    </Row>

                    <Space wrap size={12}>
                      <Button type="primary" size="large" onClick={() => onSelectMode('citybirth')}>
                        Open City Birth Workspace
                      </Button>
                      <Button size="large" onClick={() => onSelectMode('simulation')}>
                        Open Simulation Workspace
                      </Button>
                      <Button size="large" onClick={() => setIsIntroOpen(true)}>
                        View Intro Notes
                      </Button>
                    </Space>
                  </Space>
                </Card>
              </Col>

              <Col xs={24} xl={8}>
                <Card
                  bordered={false}
                  style={{
                    borderRadius: 24,
                    background: 'linear-gradient(180deg, #f8fbff 0%, #ffffff 100%)',
                    boxShadow: 'inset 0 0 0 1px rgba(15, 23, 42, 0.05)',
                    height: '100%'
                  }}
                  bodyStyle={{ padding: 24 }}
                >
                  <Space direction="vertical" size={14} style={{ width: '100%' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Title level={4} style={{ margin: 0, color: '#0f172a' }}>
                        System Status
                      </Title>
                      <Tag color={isConnected ? 'success' : 'error'}>{isConnected ? 'Ready' : 'Unavailable'}</Tag>
                    </div>

                    {systemCards.map(card => (
                      <div
                        key={card.title}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 14,
                          padding: '14px 16px',
                          borderRadius: 18,
                          background: '#ffffff',
                          border: '1px solid rgba(15, 23, 42, 0.07)'
                        }}
                      >
                        <div
                          style={{
                            width: 42,
                            height: 42,
                            borderRadius: 14,
                            display: 'grid',
                            placeItems: 'center',
                            background: card.accent,
                            flexShrink: 0
                          }}
                        >
                          {card.icon}
                        </div>
                        <div style={{ minWidth: 0 }}>
                          <div style={{ color: '#0f172a', fontWeight: 700 }}>{card.title}</div>
                          <div style={{ color: '#475569', fontSize: 13 }}>{card.desc}</div>
                        </div>
                        <Tag style={{ marginLeft: 'auto' }}>{card.value}</Tag>
                      </div>
                    ))}
                  </Space>
                </Card>
              </Col>
            </Row>
          </div>
        </div>

        <Row gutter={[18, 18]}>
          {modeCards.map(card => (
            <Col xs={24} xl={12} key={card.key}>
              <Card
                hoverable
                onClick={() => onSelectMode(card.key)}
                style={{
                  borderRadius: 26,
                  border: '1px solid rgba(15, 23, 42, 0.08)',
                  boxShadow: '0 20px 56px rgba(15, 23, 42, 0.08)',
                  overflow: 'hidden',
                  height: '100%'
                }}
                bodyStyle={{
                  padding: 24,
                  background: `radial-gradient(circle at top right, ${card.accent}16, transparent 38%), linear-gradient(180deg, #ffffff 0%, #fbfcfe 100%)`
                }}
              >
                <Space direction="vertical" size={18} style={{ width: '100%' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16 }}>
                    <Space size={14} align="start">
                      <div
                        style={{
                          width: 58,
                          height: 58,
                          borderRadius: 18,
                          display: 'grid',
                          placeItems: 'center',
                          background: `${card.accent}14`,
                          boxShadow: `inset 0 0 0 1px ${card.accent}24`
                        }}
                      >
                        {card.icon}
                      </div>
                      <div>
                        <Title level={3} style={{ margin: 0, color: '#0f172a' }}>
                          {card.title}
                        </Title>
                        <Text style={{ color: card.accent, fontWeight: 700 }}>{card.subtitle}</Text>
                      </div>
                    </Space>
                    <Button type="primary" ghost style={{ borderColor: card.accent, color: card.accent }}>
                      Launch
                    </Button>
                  </div>

                  <Paragraph style={{ margin: 0, color: '#475569', lineHeight: 1.85, minHeight: 56 }}>
                    {card.summary}
                  </Paragraph>

                  <div
                    style={{
                      borderRadius: 18,
                      background: '#f8fafc',
                      border: '1px solid rgba(15, 23, 42, 0.06)',
                      padding: '14px 16px'
                    }}
                  >
                    <Space direction="vertical" size={10} style={{ width: '100%' }}>
                      {card.bullets.map(item => (
                        <div key={item} style={{ display: 'flex', alignItems: 'center', gap: 10, color: '#334155' }}>
                          <CheckCircleFilled style={{ color: card.accent }} />
                          <span>{item}</span>
                        </div>
                      ))}
                    </Space>
                  </div>

                  <Divider style={{ margin: 0 }} />

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                    <Space wrap size={[8, 8]}>
                      <Tag color={card.key === 'simulation' ? 'blue' : 'green'}>{card.key === 'simulation' ? 'Playback' : 'Planning'}</Tag>
                      <Tag>{card.key === 'simulation' ? 'Stable Topology' : 'Adaptive Topology'}</Tag>
                    </Space>
                    <Text style={{ color: '#64748b' }}>Click anywhere on the card to open</Text>
                  </div>
                </Space>
              </Card>
            </Col>
          ))}
        </Row>

        <Row gutter={[18, 18]} style={{ marginTop: 18 }}>
          <Col xs={24} xl={14}>
            <Card
              bordered={false}
              style={{
                borderRadius: 24,
                border: '1px solid rgba(15, 23, 42, 0.08)',
                boxShadow: '0 16px 42px rgba(15, 23, 42, 0.06)'
              }}
              bodyStyle={{ padding: 22 }}
            >
              <Title level={4} style={{ marginTop: 0, color: '#0f172a' }}>
                Recommended Starting Path
              </Title>
              <Space direction="vertical" size={12} style={{ width: '100%' }}>
                <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
                  <BranchesOutlined style={{ color: '#0f62fe', fontSize: 18, marginTop: 3 }} />
                  <div>
                    <div style={{ color: '#0f172a', fontWeight: 700 }}>Start with City Birth Mode</div>
                    <div style={{ color: '#475569' }}>Use it when you want the most complete software workspace with planning, growth, zoning, and live decision logs.</div>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
                  <CarOutlined style={{ color: '#16803c', fontSize: 18, marginTop: 3 }} />
                  <div>
                    <div style={{ color: '#0f172a', fontWeight: 700 }}>Use Simulation Mode for focused inspection</div>
                    <div style={{ color: '#475569' }}>It is better when you only need replay, traffic behavior review, and stable scenario comparisons.</div>
                  </div>
                </div>
              </Space>
            </Card>
          </Col>

          <Col xs={24} xl={10}>
            <Card
              bordered={false}
              style={{
                borderRadius: 24,
                border: '1px solid rgba(15, 23, 42, 0.08)',
                boxShadow: '0 16px 42px rgba(15, 23, 42, 0.06)'
              }}
              bodyStyle={{ padding: 22 }}
            >
              <Title level={4} style={{ marginTop: 0, color: '#0f172a' }}>
                Interface Focus
              </Title>
              <Space direction="vertical" size={12} style={{ width: '100%' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <DeploymentUnitOutlined style={{ color: '#0f62fe' }} />
                  <Text>Mode-first launcher instead of narrative landing page</Text>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <RadarChartOutlined style={{ color: '#16803c' }} />
                  <Text>Operational cards, status blocks, and launch actions</Text>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <RobotOutlined style={{ color: '#7c3aed' }} />
                  <Text>Intro content moved behind a secondary modal action</Text>
                </div>
              </Space>
            </Card>
          </Col>
        </Row>
      </div>

      <Modal
        open={isIntroOpen}
        onCancel={() => setIsIntroOpen(false)}
        footer={null}
        width={820}
        title="Platform Notes"
      >
        <Space direction="vertical" size={14} style={{ width: '100%' }}>
          {introParagraphs.map(paragraph => (
            <Paragraph key={paragraph} style={{ margin: 0, color: '#334155', lineHeight: 1.9 }}>
              {paragraph}
            </Paragraph>
          ))}
        </Space>
      </Modal>
    </div>
  );
};

export default ModeSelectorLanding;
