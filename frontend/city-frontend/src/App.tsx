import React, { useState, useEffect, useCallback } from 'react';
import { Layout, Tabs, message, Badge, Space } from 'antd';
import { 
  HistoryOutlined, 
  RobotOutlined, 
  DashboardOutlined,
  CarOutlined,
  NodeIndexOutlined,
  GlobalOutlined,
  ArrowLeftOutlined
} from '@ant-design/icons';
import { ControlPanel } from './components/ControlPanel';
import { DecisionLog } from './components/DecisionLog';
import { PlaybackView } from './components/views/PlaybackView';
import { AIChainView } from './components/views/AIChainView';
import { AnalyticsView } from './components/views/AnalyticsView';
import { RoadPlanningView } from './components/views/RoadPlanningView';
import { ModeSelectorLanding } from './components/ModeSelectorLanding';
import { useSocket } from './hooks/useSocket';
import { usePlanningSocket } from './hooks/usePlanningSocket';
import { AgentDecision } from './types';
import { AgentLLMConfig } from './components/LLMConfigPanel';
import type { TabsProps } from 'antd';

const { Header, Content, Sider } = Layout;

// 应用程序模式类型
type AppMode = 'simulation' | 'citybirth';

// 仿真模式下的子Tab类型
type SimulationTabKey = 'playback' | 'aichain' | 'analytics';



// 仿真模式主组件
const SimulationMode: React.FC<{
  onBack: () => void;
}> = ({ onBack }) => {
  const {
    isConnected,
    network,
    simulationState,
    decisions,
    startSimulation,
    pauseSimulation,
    resetSimulation,
    spawnVehicle,
    getAgentDecision,
    getTrafficLightDecision,
    requestNetwork,
  } = useSocket();

  const [activeTab, setActiveTab] = useState<SimulationTabKey>('playback');
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [selectedAgentType, setSelectedAgentType] = useState<'vehicle' | 'pedestrian' | 'traffic_light' | null>(null);
  const [, setCurrentDecision] = useState<AgentDecision | null>(null);

  // 连接成功后请求网络数据
  useEffect(() => {
    if (isConnected) {
      requestNetwork();
    }
  }, [isConnected, requestNetwork]);

  // 当选择代理时，获取最新的决策
  useEffect(() => {
    if (selectedAgentId && decisions.length > 0) {
      const latest = decisions
        .filter(d => d.agent_id === selectedAgentId)
        .pop();
      if (latest) {
        setCurrentDecision(latest);
      }
    }
  }, [selectedAgentId, decisions]);

  const handleSelectAgent = useCallback((agentId: string | null, agentType?: 'vehicle' | 'pedestrian' | 'traffic_light') => {
    setSelectedAgentId(agentId);
    setSelectedAgentType(agentType || null);
    setCurrentDecision(null);
    if (agentId) {
      if (agentType === 'traffic_light') {
        getTrafficLightDecision(agentId);
      } else {
        getAgentDecision(agentId);
      }
    }
  }, [getAgentDecision, getTrafficLightDecision]);



  const vehicles = simulationState?.agents?.vehicles || [];
  const pedestrians = simulationState?.agents?.pedestrians || [];
  const trafficLights = simulationState?.traffic_lights || [];
  const trafficLightAgents = simulationState?.traffic_light_agents || [];
  const isRunning = simulationState?.is_running || false;
  const statistics = simulationState?.statistics || null;
  const currentTime = simulationState?.time || 0;

  // Tab 配置
  const tabItems: TabsProps['items'] = [
    {
      key: 'playback',
      label: (
        <Space>
          <HistoryOutlined />
          <span>决策回放</span>
          <Badge count={decisions.length} style={{ backgroundColor: '#1890ff' }} />
        </Space>
      ),
      children: (
        <PlaybackView
          network={network}
          vehicles={vehicles}
          pedestrians={pedestrians}
          trafficLights={trafficLights}
          statistics={statistics}
          decisions={decisions}
          isRunning={isRunning}
          currentTime={currentTime}
          onStart={startSimulation}
          onPause={pauseSimulation}
          onReset={resetSimulation}
        />
      ),
    },
    {
      key: 'aichain',
      label: (
        <Space>
          <RobotOutlined />
          <span>AI 决策链</span>
          {selectedAgentId && <Badge status="processing" color="#52c41a" />}
        </Space>
      ),
      children: (
        <AIChainView
          network={network}
          vehicles={vehicles}
          pedestrians={pedestrians}
          trafficLights={trafficLights}
          trafficLightAgents={trafficLightAgents}
          selectedAgentId={selectedAgentId}
          selectedAgentType={selectedAgentType}
          decisions={decisions}
          onSelectAgent={handleSelectAgent}
        />
      ),
    },
    {
      key: 'analytics',
      label: (
        <Space>
          <DashboardOutlined />
          <span>数据分析</span>
        </Space>
      ),
      children: (
        <AnalyticsView
          statistics={statistics}
          network={network}
          vehicles={vehicles}
          trafficLights={trafficLights}
          currentTime={currentTime}
        />
      ),
    },
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      {/* 顶部导航栏 */}
      <Header style={{ 
        background: '#001529', 
        padding: '0 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between'
      }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <div 
            onClick={onBack}
            style={{ 
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              marginRight: 16,
              padding: '4px 12px',
              borderRadius: 4,
              background: 'rgba(255,255,255,0.1)'
            }}
          >
            <ArrowLeftOutlined style={{ color: 'white', marginRight: 8 }} />
            <span style={{ color: 'white' }}>返回</span>
          </div>
          <h1 style={{ color: 'white', margin: 0, fontSize: 18 }}>
            <GlobalOutlined style={{ marginRight: 8 }} />
            智能交通仿真系统
          </h1>
        </div>
        
        <Space>
          <Badge 
            status={isConnected ? 'success' : 'error'} 
            text={<span style={{ color: 'rgba(255,255,255,0.65)' }}>
              {isConnected ? '已连接' : '未连接'}
            </span>}
          />
          {isRunning ? (
            <Badge status="processing" text={<span style={{ color: '#52c41a' }}>运行中</span>} />
          ) : (
            <Badge status="default" text={<span style={{ color: 'rgba(255,255,255,0.45)' }}>已暂停</span>} />
          )}
          <Badge 
            status="processing" 
            color="#722ed1"
            text={<span style={{ color: '#d3adf7' }}>AI 驱动决策</span>}
          />
          <span style={{ color: 'rgba(255,255,255,0.45)', marginLeft: 16 }}>
            <CarOutlined style={{ marginRight: 4 }} />
            车辆: {vehicles.length}
          </span>
          <span style={{ color: 'rgba(255,255,255,0.45)', marginLeft: 8 }}>
            时间: {currentTime.toFixed(1)}s
          </span>
        </Space>
      </Header>

      <Layout>
        {/* 左侧控制面板和决策日志 */}
        <Sider width={280} style={{ background: '#f0f2f5', padding: 16 }}>
          <ControlPanel
            isRunning={isRunning}
            isConnected={isConnected}
            statistics={statistics}
            onStart={startSimulation}
            onPause={pauseSimulation}
            onReset={resetSimulation}
            onSpawnVehicle={spawnVehicle}
          />
          <div style={{ marginTop: 16 }}>
            <DecisionLog decisions={decisions} />
          </div>
        </Sider>

        {/* 主内容区域 - Tab 切换 */}
        <Content style={{ padding: 16, background: '#fff' }}>
          <Tabs
            activeKey={activeTab}
            onChange={(key) => setActiveTab(key as SimulationTabKey)}
            items={tabItems}
            type="card"
            style={{ height: 'calc(100vh - 96px)' }}
            tabBarStyle={{ marginBottom: 0 }}
          />
        </Content>
      </Layout>
    </Layout>
  );
};

// 城市诞生模式主组件
const CityBirthMode: React.FC<{
  onBack: () => void;
}> = ({ onBack }) => {
  const planningSocket = usePlanningSocket();
  
  // LLM 配置状态
  const [llmConfig, setLLMConfig] = useState<AgentLLMConfig>({
    vehicle: false,
    traffic_light: false,
    road_planning: true,  // 路网规划智能体启用
    zoning: true          // 城市规划智能体启用
  });
  const [birthConfig, setBirthConfig] = useState<{
    city_birth: boolean;
    city_birth_network_type: 'procedural' | 'grid' | 'cross' | 'radial';
    city_birth_seed: number;
    city_birth_nodes: number;
    city_birth_scale: number;
    city_birth_min_edge: number;
    city_birth_max_edge: number;
  }>({
    city_birth: true,
    city_birth_network_type: 'procedural',  // 程序化生成网络
    city_birth_seed: 42,
    city_birth_nodes: 18,
    city_birth_scale: 120,
    city_birth_min_edge: 160,
    city_birth_max_edge: 420
  });

  // 连接成功后请求网络数据

  const { 
    isConnected,
    network, 
    vehicles = [], 
    trafficLights = [], 
    expansionHistory = [], 
    planningAgent,
    zoningAgent,
    zones = [],
    llmDecisions = [],
    isRunning, 
    currentTime,
    statistics,
    agentMemories = [],
    agentsWithMemory = [],
    startSimulation,
    pauseSimulation,
    resetSimulation
  } = planningSocket;

  
  // 渲染

  return (
    <Layout style={{ minHeight: '100vh' }}>
      {/* 顶部导航 */}
      <Header style={{ 
        background: '#001529', 
        padding: '0 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between'
      }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <div 
            onClick={onBack}
            style={{ 
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              marginRight: 16,
              padding: '4px 12px',
              borderRadius: 4,
              background: 'rgba(255,255,255,0.1)'
            }}
          >
            <ArrowLeftOutlined style={{ color: 'white', marginRight: 8 }} />
            <span style={{ color: 'white' }}>返回</span>
          </div>
          <h1 style={{ color: 'white', margin: 0, fontSize: 18 }}>
            <NodeIndexOutlined style={{ marginRight: 8 }} />
            城市诞生模拟
          </h1>
        </div>
        
        <Space>
          <Badge 
            status={isConnected ? 'success' : 'error'} 
            text={<span style={{ color: 'rgba(255,255,255,0.65)' }}>{isConnected ? '已连接' : '未连接'}</span>}
          />
          {isRunning ? (
            <Badge status="processing" text={<span style={{ color: '#52c41a' }}>运行中</span>} />
          ) : (
            <Badge status="default" text={<span style={{ color: 'rgba(255,255,255,0.45)' }}>已暂停</span>} />
          )}
          <Badge 
            status="processing" 
            color="#722ed1"
            text={<span style={{ color: '#d3adf7' }}>AI 规划智能体</span>}
          />
          {expansionHistory.length > 0 && (
            <Badge 
              count={expansionHistory.length} 
              style={{ backgroundColor: '#52c41a', marginLeft: 8 }}
            />
          )}
          <span style={{ color: 'rgba(255,255,255,0.45)', marginLeft: 16 }}>
            <CarOutlined style={{ marginRight: 4 }} />
            车辆: {vehicles.length}
          </span>
          <span style={{ color: 'rgba(255,255,255,0.45)', marginLeft: 8 }}>
            时间: {currentTime.toFixed(1)}s
          </span>
        </Space>
      </Header>

      <Content style={{ padding: 16, background: '#fff' }}>
        <RoadPlanningView
          network={network}
          vehicles={vehicles}
          trafficLights={trafficLights}
          expansionHistory={expansionHistory}
          planningAgent={planningAgent}
          zoningAgent={zoningAgent}
          zones={zones}
          llmDecisions={llmDecisions}
          isRunning={isRunning}
          currentTime={currentTime}
          statistics={statistics}
          llmConfig={llmConfig}
          onLLMConfigChange={setLLMConfig}
          birthConfig={birthConfig}
          onBirthConfigChange={setBirthConfig}
          onStart={() => startSimulation({ ...llmConfig, ...birthConfig })}
          onPause={pauseSimulation}
          onReset={() => resetSimulation({ ...llmConfig, ...birthConfig })}
          agentMemories={agentMemories}
          agentsWithMemory={agentsWithMemory}
        />
      </Content>
    </Layout>
  );
};

// 主应用程序组件
const App: React.FC = () => {
  const [mode, setMode] = useState<AppMode | null>(null);
  const { isConnected } = useSocket();

  const handleSelectMode = (selectedMode: AppMode) => {
    setMode(selectedMode);
    message.success(`已切换到${selectedMode === 'simulation' ? '智能仿真' : '城市诞生'}模式`);
  };

  const handleBackToMenu = () => {
    setMode(null);
  };

  // 根据当前模式渲染对应的组件
  if (mode === 'simulation') {
    return <SimulationMode onBack={handleBackToMenu} />;
  }

  if (mode === 'citybirth') {
    return <CityBirthMode onBack={handleBackToMenu} />;
  }

  // 模式选择界面
  return (
    <Layout style={{ minHeight: '100vh', background: '#eef4f8' }}>
      <Header
        style={{
          background: 'linear-gradient(90deg, #0f172a 0%, #132238 48%, #16324f 100%)',
          padding: '0 24px',
          borderBottom: '1px solid rgba(255,255,255,0.08)',
        }}
      >
        <h1 style={{ color: 'white', margin: 0, fontSize: 20 }}>
          智能交通 TASP 3.0 综合仿真系统 - 选择仿真模式开始探索
        </h1>
      </Header>
      <Content>
        <ModeSelectorLanding onSelectMode={handleSelectMode} isConnected={isConnected} />
      </Content>
    </Layout>
  );
};

export default App;
