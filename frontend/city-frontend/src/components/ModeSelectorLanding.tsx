import React from 'react';
import { Badge, Card, Col, Row, Space, Typography } from 'antd';
import {
  ApartmentOutlined,
  BranchesOutlined,
  CarOutlined,
  CheckCircleFilled,
  CompassOutlined,
  GlobalOutlined,
  RadarChartOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';

const { Title, Paragraph, Text } = Typography;

type AppMode = 'simulation' | 'citybirth';

interface ModeSelectorLandingProps {
  onSelectMode: (mode: AppMode) => void;
  isConnected: boolean;
}

const articleParagraphs = [
  '西方诸多文字中的“文明”一词，都源自拉丁文的“Civitas”（意为“城市”）。这一词源学上的渊源揭示了一个深刻的本质关联：城市与文明从来是一体两面。从乌鲁克到罗马，从长安到巴黎，人类文明的每一次飞跃，都伴随着城市形态的根本性变革。城市不仅是文明的容器，更是文明本身最集中的体现。',
  '曼纽·卡斯特关于“城市是社会的表现”与“空间是结晶化的时间”的论断，揭示了城市空间并非中立容器，而是社会活动在历史维度上的沉淀。每一座城市的结构与纹理，都承载着生产方式、社会关系、文化观念与集体记忆在物理空间中的凝结。',
  '然而，理解城市“从零到一”的涌现过程始终面临方法论困境。真实城市的演化跨越漫长历史，关键转折点不可复现；传统模型又往往预设宏观结构或固定规则，难以捕捉从个体行为到集体秩序的内生生成。',
  '生成式智能体的出现，为这一研究打开了新的实验窗口。具备记忆、规划、感知与社会交互能力的智能体，被置于一个开放、可重复、可干预的数字环境后，城市的起源与演化第一次能够被完整观察与记录。',
  '本研究构建了一个基于生成式智能体的城市仿真器，试图回答一个根本问题：在没有预设规划、没有中央指令、没有外部设计的前提下，仅凭大量智能体的局部交互，能否从零开始涌现出具有人类城市特征的空间结构、功能分区与基础设施体系？',
  '仿真结果表明，宏观城市结构并非由任何单一主体设计产生，而是在个体对局部环境的持续适应中，经由行为痕迹累积、集体约定固化与功能分化强化，逐步结晶为具有秩序的城市空间。我们将这一过程称为“城市结晶化”（urban crystallization）。',
];

const insightCards = [
  {
    title: '文明与城市',
    icon: <GlobalOutlined style={{ fontSize: 22, color: '#1d4ed8' }} />,
    accent: '#dbeafe',
    text: '“Civitas”同时指向城市与文明，说明城市不是文明的附属物，而是文明最集中的物质显影。',
  },
  {
    title: '空间与时间',
    icon: <CompassOutlined style={{ fontSize: 22, color: '#0f766e' }} />,
    accent: '#ccfbf1',
    text: '城市空间是历史行动的沉淀，是社会矛盾、生产关系与集体选择在物质环境中的连续书写。',
  },
  {
    title: '涌现机制',
    icon: <RadarChartOutlined style={{ fontSize: 22, color: '#b45309' }} />,
    accent: '#ffedd5',
    text: '路径、聚落、规则与设施并非先验设计，而是在微观互动的反复强化中逐步形成。',
  },
];

export const ModeSelectorLanding: React.FC<ModeSelectorLandingProps> = ({
  onSelectMode,
  isConnected,
}) => {
  const modeCards = [
    {
      key: 'simulation' as AppMode,
      title: '常规仿真模式',
      accent: '#0f62fe',
      icon: <GlobalOutlined style={{ fontSize: 34, color: '#0f62fe' }} />,
      badge: '固定路网',
      description:
        '在既有道路网络中观察车辆、信号灯与统计指标，适合做单场景回放、AI 决策链分析与稳定对照实验。',
      bullets: ['适合验证单个场景行为', '支持 AI 决策链回放', '更适合做参数对照实验'],
    },
    {
      key: 'citybirth' as AppMode,
      title: '城市诞生模式',
      accent: '#16803c',
      icon: <ApartmentOutlined style={{ fontSize: 34, color: '#16803c' }} />,
      badge: '动态演化',
      description:
        '从初始空白或早期路网出发，观察道路扩展、功能区规划与交通需求如何共同驱动城市空间的生成。',
      bullets: ['路网与区域同步生长', '支持多类智能体与 LLM 协同', '最适合直接观察“城市结晶化”'],
    },
  ];

  return (
    <div
      style={{
        minHeight: 'calc(100vh - 72px)',
        padding: '36px 24px 72px',
        background:
          'radial-gradient(circle at 8% 12%, rgba(18, 76, 150, 0.18), transparent 26%), radial-gradient(circle at 90% 14%, rgba(22, 128, 60, 0.12), transparent 24%), linear-gradient(180deg, #eef4fb 0%, #f7f5ef 52%, #fbfaf7 100%)',
      }}
    >
      <div style={{ maxWidth: 1240, margin: '0 auto' }}>
        <div
          style={{
            position: 'relative',
            overflow: 'hidden',
            padding: '32px 32px 30px',
            borderRadius: 34,
            background:
              'linear-gradient(135deg, rgba(9, 20, 35, 0.96) 0%, rgba(19, 39, 60, 0.95) 44%, rgba(42, 63, 49, 0.93) 100%)',
            border: '1px solid rgba(255,255,255,0.08)',
            boxShadow: '0 28px 90px rgba(15, 23, 42, 0.22)',
            marginBottom: 24,
          }}
        >
          <div
            style={{
              position: 'absolute',
              inset: 0,
              background:
                'radial-gradient(circle at top left, rgba(96, 165, 250, 0.24), transparent 30%), radial-gradient(circle at bottom right, rgba(74, 222, 128, 0.16), transparent 24%)',
              pointerEvents: 'none',
            }}
          />
          <div style={{ position: 'relative' }}>
            <Space wrap size={12} style={{ marginBottom: 20 }}>
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '7px 14px',
                  borderRadius: 999,
                  background: 'rgba(96,165,250,0.14)',
                  color: '#bfdbfe',
                  fontWeight: 700,
                  fontSize: 12,
                  letterSpacing: 0.6,
                }}
              >
                <ThunderboltOutlined />
                TASP 3.0
              </span>
              <Badge
                status={isConnected ? 'success' : 'error'}
                text={
                  <span style={{ color: 'rgba(226,232,240,0.88)' }}>
                    {isConnected ? '后端服务已连接' : '后端服务未连接'}
                  </span>
                }
              />
            </Space>

            <Row gutter={[28, 28]} align="middle">
              <Col xs={24} xl={15}>
                <div style={{ maxWidth: 760 }}>
                  <Text
                    style={{
                      color: '#93c5fd',
                      fontSize: 13,
                      letterSpacing: 2.2,
                      textTransform: 'uppercase',
                    }}
                  >
                    Urban Crystallization / Generative Agents / Civitas
                  </Text>
                  <Title
                    level={1}
                    style={{
                      margin: '12px 0 14px',
                      color: '#f8fafc',
                      fontSize: 48,
                      lineHeight: 1.05,
                      fontFamily: '"Georgia", "Times New Roman", serif',
                    }}
                  >
                    从 “Civitas” 到
                    <br />
                    城市结晶化
                  </Title>
                  <Paragraph
                    style={{
                      margin: 0,
                      color: 'rgba(226,232,240,0.86)',
                      fontSize: 17,
                      lineHeight: 1.9,
                      maxWidth: 720,
                    }}
                  >
                    一个以生成式智能体为核心的城市仿真平台，用来观察文明如何从微观交互中生长为可感知的空间秩序。
                  </Paragraph>
                </div>
              </Col>

              <Col xs={24} xl={9}>
                <div
                  style={{
                    padding: 22,
                    borderRadius: 24,
                    background: 'rgba(255,255,255,0.08)',
                    border: '1px solid rgba(255,255,255,0.10)',
                    backdropFilter: 'blur(12px)',
                  }}
                >
                  <div
                    style={{
                      color: '#f8fafc',
                      fontSize: 20,
                      lineHeight: 1.8,
                      fontFamily: '"Georgia", "Times New Roman", serif',
                    }}
                  >
                    “城市是社会的表现”
                    <br />
                    “空间是结晶化的时间”
                  </div>
                </div>
              </Col>
            </Row>
          </div>
        </div>

        <Row gutter={[20, 20]} style={{ marginBottom: 24 }}>
          {insightCards.map(card => (
            <Col xs={24} md={8} key={card.title}>
              <Card
                bordered={false}
                style={{
                  height: '100%',
                  borderRadius: 24,
                  background: '#ffffffcc',
                  boxShadow: '0 16px 50px rgba(15, 23, 42, 0.08)',
                }}
                bodyStyle={{ padding: 22 }}
              >
                <div
                  style={{
                    width: 48,
                    height: 48,
                    borderRadius: 16,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: card.accent,
                    marginBottom: 14,
                  }}
                >
                  {card.icon}
                </div>
                <Title level={4} style={{ margin: 0, color: '#0f172a' }}>
                  {card.title}
                </Title>
                <Paragraph style={{ margin: '10px 0 0', color: '#475569', lineHeight: 1.85, fontSize: 15 }}>
                  {card.text}
                </Paragraph>
              </Card>
            </Col>
          ))}
        </Row>

        <div
          style={{
            padding: '26px 28px',
            borderRadius: 30,
            background: 'rgba(255,255,255,0.78)',
            border: '1px solid rgba(15, 23, 42, 0.08)',
            boxShadow: '0 24px 70px rgba(15, 23, 42, 0.08)',
            marginBottom: 24,
          }}
        >
          <Row gutter={[28, 24]}>
            <Col xs={24} lg={8}>
              <div style={{ position: 'sticky', top: 16 }}>
                <Text
                  style={{
                    display: 'inline-block',
                    padding: '6px 12px',
                    borderRadius: 999,
                    background: '#e8eefc',
                    color: '#1d4ed8',
                    fontWeight: 700,
                    letterSpacing: 0.4,
                  }}
                >
                  首页导言
                </Text>
                <Title
                  level={2}
                  style={{ margin: '14px 0 0', color: '#0f172a', fontFamily: '"Georgia", "Times New Roman", serif', lineHeight: 1.18 }}
                >
                  城市作为文明的物质显影
                </Title>
              </div>
            </Col>

            <Col xs={24} lg={16}>
              <div
                style={{
                  columnGap: 0,
                  display: 'grid',
                  gridTemplateColumns: '1fr',
                  rowGap: 18,
                }}
              >
                {articleParagraphs.map(paragraph => (
                  <Paragraph
                    key={paragraph}
                    style={{
                      margin: 0,
                      color: '#1f2937',
                      fontSize: 17,
                      lineHeight: 2.02,
                      fontFamily: '"Georgia", "Times New Roman", serif',
                      textAlign: 'justify',
                    }}
                  >
                    {paragraph}
                  </Paragraph>
                ))}
              </div>
            </Col>
          </Row>
        </div>

        <Row gutter={[20, 20]} style={{ marginBottom: 24 }}>
          <Col xs={24} lg={9}>
            <Card
              bordered={false}
              style={{
                height: '100%',
                borderRadius: 26,
                background: 'linear-gradient(180deg, #fff9ef 0%, #fffdf7 100%)',
                boxShadow: '0 20px 56px rgba(15, 23, 42, 0.08)',
              }}
              bodyStyle={{ padding: 24 }}
            >
              <Title level={4} style={{ marginTop: 0, color: '#7c2d12' }}>
                研究问题
              </Title>
              <Paragraph style={{ color: '#7c2d12', lineHeight: 1.9, fontSize: 15, marginBottom: 12 }}>
                当不存在预设规划、中央指令与宏观模板时，大量局部交互能否从零涌现出具有人类城市特征的空间秩序？
              </Paragraph>
            </Card>
          </Col>

          <Col xs={24} lg={15}>
            <Card
              bordered={false}
              style={{
                height: '100%',
                borderRadius: 26,
                background: 'linear-gradient(180deg, #f6fbff 0%, #f8fcf8 100%)',
                boxShadow: '0 20px 56px rgba(15, 23, 42, 0.08)',
              }}
              bodyStyle={{ padding: 24 }}
            >
              <Title level={4} style={{ marginTop: 0, color: '#0f172a' }}>
                观察到的涌现现象
              </Title>
              <Row gutter={[16, 16]}>
                <Col xs={24} md={8}>
                  <div style={{ padding: 16, borderRadius: 18, background: '#ffffff', height: '100%' }}>
                    <Text strong style={{ color: '#0f62fe' }}>路径网络</Text>
                    <div style={{ color: '#475569', marginTop: 8, lineHeight: 1.8 }}>
                      重复使用的移动痕迹逐步固化为道路，交通流量出现可辨识的层级结构。
                    </div>
                  </div>
                </Col>
                <Col xs={24} md={8}>
                  <div style={{ padding: 16, borderRadius: 18, background: '#ffffff', height: '100%' }}>
                    <Text strong style={{ color: '#16803c' }}>功能分区</Text>
                    <div style={{ color: '#475569', marginTop: 8, lineHeight: 1.8 }}>
                      聚落围绕资源、分工与交换关系自然集聚，形成具备专业化趋势的区域结构。
                    </div>
                  </div>
                </Col>
                <Col xs={24} md={8}>
                  <div style={{ padding: 16, borderRadius: 18, background: '#ffffff', height: '100%' }}>
                    <Text strong style={{ color: '#b45309' }}>基础设施</Text>
                    <div style={{ color: '#475569', marginTop: 8, lineHeight: 1.8 }}>
                      信号灯与交通规则等集体约定在拥堵节点上涌现，并逐渐传播为制度化设施。
                    </div>
                  </div>
                </Col>
              </Row>
            </Card>
          </Col>
        </Row>

        <div
          style={{
            padding: '12px 0 18px',
          }}
        >
          <Title level={2} style={{ margin: '0 0 6px', color: '#0f172a' }}>
            进入实验
          </Title>
        </div>

        <Row gutter={[20, 20]}>
          {modeCards.map((card) => (
            <Col xs={24} lg={12} key={card.key}>
              <Card
                hoverable
                onClick={() => onSelectMode(card.key)}
                style={{
                  height: '100%',
                  minHeight: 332,
                  borderRadius: 30,
                  border: '1px solid rgba(15, 23, 42, 0.08)',
                  overflow: 'hidden',
                  boxShadow: '0 22px 64px rgba(15, 23, 42, 0.08)',
                  background: '#ffffff',
                }}
                bodyStyle={{
                  height: '100%',
                  padding: 28,
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  background: `radial-gradient(circle at top right, ${card.accent}18, transparent 42%), linear-gradient(180deg, #ffffff 0%, #fbfcfd 100%)`,
                }}
              >
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
                    <div
                      style={{
                        width: 76,
                        height: 76,
                        borderRadius: 24,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        background: `${card.accent}14`,
                        boxShadow: `inset 0 0 0 1px ${card.accent}24`,
                      }}
                    >
                      {card.icon}
                    </div>
                    <span
                      style={{
                        padding: '7px 12px',
                        borderRadius: 999,
                        background: `${card.accent}12`,
                        color: card.accent,
                        fontSize: 12,
                        fontWeight: 700,
                      }}
                    >
                      {card.badge}
                    </span>
                  </div>

                  <Title level={3} style={{ margin: 0, color: '#111827' }}>
                    {card.title}
                  </Title>
                  <Paragraph style={{ marginTop: 12, marginBottom: 20, color: '#475569', fontSize: 15, lineHeight: 1.85 }}>
                    {card.description}
                  </Paragraph>

                  <Space direction="vertical" size={10} style={{ width: '100%' }}>
                    {card.bullets.map((item) => (
                      <div key={item} style={{ display: 'flex', alignItems: 'center', gap: 10, color: '#334155' }}>
                        <CheckCircleFilled style={{ color: card.accent }} />
                        <span>{item}</span>
                      </div>
                    ))}
                  </Space>
                </div>

                <div
                  style={{
                    marginTop: 28,
                    paddingTop: 18,
                    borderTop: '1px solid rgba(15, 23, 42, 0.08)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                  }}
                >
                  <Text style={{ color: '#64748b' }}>点击进入</Text>
                  <span style={{ color: card.accent, fontWeight: 700 }}>进入模式</span>
                </div>
              </Card>
            </Col>
          ))}
        </Row>

        <div
          style={{
            marginTop: 20,
            padding: '16px 20px',
            borderRadius: 20,
            background: 'rgba(255,255,255,0.72)',
            border: '1px solid rgba(15, 23, 42, 0.06)',
            color: '#64748b',
          }}
        >
          <Space wrap size={[16, 8]}>
            <span><BranchesOutlined style={{ marginRight: 8, color: '#0f62fe' }} />推荐先进入“城市诞生模式”观察从局部交互到宏观秩序的形成。</span>
            <span><CarOutlined style={{ marginRight: 8, color: '#16803c' }} />若只想查看已有道路网络中的运行效果，则使用“常规仿真模式”。</span>
          </Space>
        </div>
      </div>
    </div>
  );
};

export default ModeSelectorLanding;
