// 网络相关类型
export interface Node {
  id: string;
  x: number;
  y: number;
  name?: string;
  is_intersection?: boolean;
}

export interface Edge {
  id: string;
  from_node: string;
  to_node: string;
  num_lanes: number;
  length?: number;
}

export interface Network {
  nodes: Node[];
  edges: Edge[];
}

export interface NetworkData extends Network {}

// 车辆相关类型
export interface Vehicle {
  id: string;
  x: number;
  y: number;
  direction: number;
  speed: number;
  vehicle_type: 'CAR' | 'BUS' | 'TRUCK' | 'EMERGENCY' | 'MOTORCYCLE';
  length: number;
  width: number;
  agent_id?: string;
}

// 行人相关类型
export interface Pedestrian {
  id: string;
  x: number;
  y: number;
  speed: number;
  state: string;
  size?: number;
}

// 信号灯相关类型
export interface TrafficLight {
  node_id: string;
  state: 'RED' | 'YELLOW' | 'GREEN';
  ns_state?: 'RED' | 'YELLOW' | 'GREEN';
  ew_state?: 'RED' | 'YELLOW' | 'GREEN';
  phase?: string;
}

export interface TrafficLightAgent {
  id: string;
  node_id: string;
  name?: string;
}

// Zone相关类型
export interface Zone {
  zone_id: string;
  zone_type: string;
  zone_type_display?: string;
  name?: string;
  center_x: number;
  center_y: number;
  width: number;
  height: number;
  bounds?: [number, number, number, number];
}

// 智能体决策相关类型
export interface AgentDecision {
  agent_id: string;
  agent_type: string;
  timestamp: number;
  decision: {
    action: string;
    reason?: string;
    [key: string]: any;
  };
  llm_response?: string;
  context?: any;
}

// 仿真统计相关类型
export interface SimulationStatistics {
  active_vehicles: number;
  active_pedestrians: number;
  total_vehicles_completed: number;
  vehicle_completion_rate: number;
  total_agents: number;
  average_speed?: number;
  total_distance?: number;
}

// 规划智能体相关类型
export interface ExpansionRecord {
  timestamp: number;
  action: string;
  details: any;
  type?: string;
  node_id?: string;
  edge_id?: string;
  reverse_edge_id?: string;
  from_node?: string;
  to_node?: string;
  old_num_lanes?: number;
  new_num_lanes?: number;
}

export interface PlanningAgentStatus {
  agent_id: string;
  state: string;
  expansion_count: number;
  od_record_count: number;
}

export interface ZoningAgentStatus {
  agent_id: string;
  state: string;
  zone_count: number;
}

export interface LLMDecisionRecord {
  id: string;
  timestamp: number;
  agent_id: string;
  agent_type: string;
  category: string;
  summary: string;
  prompt: string;
  response: string;
  parsed_decision?: any;
  adopted?: boolean | null;
  status: string;
  extra?: any;
}

// 智能体记忆相关类型
export interface AgentMemory {
  agent_id: string;
  agent_type: string;
  short_term: MemoryEntry[];
  long_term: MemoryEntry[];
}

export interface MemoryEntry {
  timestamp: number;
  type: string;
  content: any;
  importance: number;
}
