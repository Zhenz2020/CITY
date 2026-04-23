import React, { useCallback, useEffect, useState } from 'react';
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

type AppMode = 'simulation' | 'citybirth';
type SimulationTabKey = 'playback' | 'aichain' | 'analytics';

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

  useEffect(() => {
    if (isConnected) {
      requestNetwork();
    }
  }, [isConnected, requestNetwork]);

  useEffect(() => {
    if (selectedAgentId && decisions.length > 0) {
      const latest = decisions.filter(d => d.agent_id === selectedAgentId).pop();
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

  const tabItems: TabsProps['items'] = [
    {
      key: 'playback',
      label: (
        <Space>
          <HistoryOutlined />
          <span>Playback</span>
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
          <span>AI Decision Chain</span>
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
          <span>Analytics</span>
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
      <Header
        style={{
          background: '#001529',
          padding: '0 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}
      >
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
            <span style={{ color: 'white' }}>Back</span>
          </div>
          <h1 style={{ color: 'white', margin: 0, fontSize: 18 }}>
            <GlobalOutlined style={{ marginRight: 8 }} />
            TASP 3.0
          </h1>
        </div>

        <Space>
          <Badge
            status={isConnected ? 'success' : 'error'}
            text={<span style={{ color: 'rgba(255,255,255,0.65)' }}>{isConnected ? 'Connected' : 'Disconnected'}</span>}
          />
          {isRunning ? (
            <Badge status="processing" text={<span style={{ color: '#52c41a' }}>Running</span>} />
          ) : (
            <Badge status="default" text={<span style={{ color: 'rgba(255,255,255,0.45)' }}>Paused</span>} />
          )}
          <Badge
            status="processing"
            color="#722ed1"
            text={<span style={{ color: '#d3adf7' }}>AI-Driven Decisions</span>}
          />
          <span style={{ color: 'rgba(255,255,255,0.45)', marginLeft: 16 }}>
            <CarOutlined style={{ marginRight: 4 }} />
            Vehicles: {vehicles.length}
          </span>
          <span style={{ color: 'rgba(255,255,255,0.45)', marginLeft: 8 }}>
            Time: {currentTime.toFixed(1)}s
          </span>
        </Space>
      </Header>

      <Layout>
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

const CityBirthMode: React.FC<{
  onBack: () => void;
}> = ({ onBack }) => {
  const planningSocket = usePlanningSocket();

  const [llmConfig, setLLMConfig] = useState<AgentLLMConfig>({
    vehicle: false,
    traffic_light: false,
    road_planning: true,
    zoning: true
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
    city_birth_network_type: 'procedural',
    city_birth_seed: 42,
    city_birth_nodes: 18,
    city_birth_scale: 120,
    city_birth_min_edge: 160,
    city_birth_max_edge: 420
  });

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

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header
        style={{
          background: '#001529',
          padding: '0 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}
      >
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
            <span style={{ color: 'white' }}>Back</span>
          </div>
          <h1 style={{ color: 'white', margin: 0, fontSize: 18 }}>
            <NodeIndexOutlined style={{ marginRight: 8 }} />
            TASP 3.0 City Birth
          </h1>
        </div>

        <Space>
          <Badge
            status={isConnected ? 'success' : 'error'}
            text={<span style={{ color: 'rgba(255,255,255,0.65)' }}>{isConnected ? 'Connected' : 'Disconnected'}</span>}
          />
          {isRunning ? (
            <Badge status="processing" text={<span style={{ color: '#52c41a' }}>Running</span>} />
          ) : (
            <Badge status="default" text={<span style={{ color: 'rgba(255,255,255,0.45)' }}>Paused</span>} />
          )}
          <Badge
            status="processing"
            color="#722ed1"
            text={<span style={{ color: '#d3adf7' }}>AI Planning Agents</span>}
          />
          {expansionHistory.length > 0 && (
            <Badge count={expansionHistory.length} style={{ backgroundColor: '#52c41a', marginLeft: 8 }} />
          )}
          <span style={{ color: 'rgba(255,255,255,0.45)', marginLeft: 16 }}>
            <CarOutlined style={{ marginRight: 4 }} />
            Vehicles: {vehicles.length}
          </span>
          <span style={{ color: 'rgba(255,255,255,0.45)', marginLeft: 8 }}>
            Time: {currentTime.toFixed(1)}s
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

const App: React.FC = () => {
  const [mode, setMode] = useState<AppMode | null>(null);
  const { isConnected } = useSocket();

  const handleSelectMode = (selectedMode: AppMode) => {
    setMode(selectedMode);
    message.success(`Switched to ${selectedMode === 'simulation' ? 'Simulation' : 'City Birth'} mode`);
  };

  const handleBackToMenu = () => {
    setMode(null);
  };

  if (mode === 'simulation') {
    return <SimulationMode onBack={handleBackToMenu} />;
  }

  if (mode === 'citybirth') {
    return <CityBirthMode onBack={handleBackToMenu} />;
  }

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
          TASP 3.0 | Transport Agent-based Simulation Platform | Generative AI-Powered Integrated Macro-Micro Simulation Platform
        </h1>
      </Header>
      <Content>
        <ModeSelectorLanding onSelectMode={handleSelectMode} isConnected={isConnected} />
      </Content>
    </Layout>
  );
};

export default App;
