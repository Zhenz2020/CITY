"""
路网规划智能体(Road Planning Agent) - 人口驱动城市演化版

基于人口密度自动扩展路网的智能体，采用网格状布局避免长条化。
专注于道路网络扩展，与城市规划智能体协同工作。
"""

from __future__ import annotations

import json
import math
import os
import random
from typing import TYPE_CHECKING, Any

from city.agents.base import AgentType, BaseAgent
from city.agents.vehicle import Vehicle, VehicleType
from city.utils.vector import Vector2D

if TYPE_CHECKING:
    from city.simulation.environment import SimulationEnvironment
    from city.environment.road_network import Node, Edge


class PopulationCityPlanner(BaseAgent):
    """
    人口驱动的路网规划智能体。
    
    核心机制：
    1. 每个节点有一定人口容量
    2. 车辆代表人口/通勤者
    3. 当人口密度超过阈值，城市扩张（添加新节点）
    4. 自动在OD对之间生成通勤车辆
    5. 采用网格状布局，避免城市长条化
    
    与城市规划智能体(ZoningAgent)协同工作，路网扩张后由ZoningAgent规划功能区域。
    
    Attributes:
        population_per_node: 每个节点的人口容量
        current_population: 当前总人口（车辆数）
        expansion_threshold: 扩张阈值（人口密度）
        auto_spawn_timer: 自动生成车辆计时器
    """
    
    def __init__(
        self,
        environment: SimulationEnvironment | None = None,
        use_llm: bool = True,
        population_per_node: int = 3,
        expansion_threshold: float = 0.5,
        spawn_interval: float = 3.0,
        max_nodes: int = 25,
        min_edge_length: float = 200.0,
        max_edge_length: float = 500.0,
        enable_memory: bool = True
    ):
        super().__init__(AgentType.TRAFFIC_PLANNER, environment, use_llm, enable_memory=enable_memory, memory_capacity=50)
        
        # 人口管理
        self.population_per_node = population_per_node
        self.expansion_threshold = expansion_threshold
        self.spawn_interval = spawn_interval
        
        # 路网扩展限制
        self.max_nodes = max_nodes
        self.min_edge_length = min_edge_length
        self.max_edge_length = max_edge_length
        
        # 状态
        self.auto_spawn_timer = 0.0
        self.last_expansion_time = 0.0
        self.expansion_cooldown = 30.0
        
        # 统计
        self.total_spawns = 0
        self.expansion_history: list[dict[str, Any]] = []

        # 记录最近的扩展方向以避免重复
        self.recent_expansion_directions: list[str] = []
        self.direction_window = 6
        self._procedural_growth_config: dict[str, Any] | None = None
        
        # LLM决策记录（用于前端展示）
        self.last_decision: dict[str, Any] | None = None
        self.llm_decision_archive: list[dict[str, Any]] = []
        
        # 城市演化阶段
        self.city_stage = 'initial'  # initial, developing, mature
        self.stage_thresholds = {
            'initial': 4,      # 初阶段：2x2网格
            'developing': 9,   # 发展阶段：3x3网格
            'mature': 16       # 成熟阶段：4x4网格
        }
        
    def get_population_density(self) -> float:
        """计算当前人口密度 (0.0 - 1.0)。"""
        if not self.environment:
            return 0.0
        
        num_nodes = len(self.environment.road_network.nodes)
        if num_nodes == 0:
            return 0.0
        
        current_vehicles = len(self.environment.vehicles)
        max_capacity = num_nodes * self.population_per_node
        
        return current_vehicles / max_capacity if max_capacity > 0 else 0.0
    
    def get_city_stats(self) -> dict[str, Any]:
        """获取城市统计信息。"""
        if not self.environment:
            return {}
        
        num_nodes = len(self.environment.road_network.nodes)
        current_vehicles = len(self.environment.vehicles)
        max_capacity = num_nodes * self.population_per_node
        density = self.get_population_density()
        
        # 计算网络形状指标
        network_shape = self._analyze_network_shape()
        
        return {
            'nodes': num_nodes,
            'current_population': current_vehicles,
            'max_capacity': max_capacity,
            'density': density,
            'density_percent': density * 100,
            'expansion_threshold': self.expansion_threshold,
            'should_expand': density >= self.expansion_threshold,
            'total_spawns': self.total_spawns,
            'expansion_count': len(self.expansion_history),
            'network_shape': network_shape
        }
    
    def _analyze_network_shape(self) -> dict[str, Any]:
        """分分网络形状，避免长条化。"""
        if not self.environment or len(self.environment.road_network.nodes) < 2:
            return {'aspect_ratio': 1.0, 'shape': 'balanced'}
        
        positions = [n.position for n in self.environment.road_network.nodes.values()]
        xs = [p.x for p in positions]
        ys = [p.y for p in positions]
        
        width = max(xs) - min(xs)
        height = max(ys) - min(ys)
        
        if height == 0:
            aspect_ratio = float('inf')
        else:
            aspect_ratio = width / height
        
        # 判断形状
        if aspect_ratio > 2:
            shape = 'too_wide'
        elif aspect_ratio < 0.5:
            shape = 'too_tall'
        else:
            shape = 'balanced'
        
        return {
            'aspect_ratio': aspect_ratio,
            'shape': shape,
            'width': width,
            'height': height
        }
    
    def perceive(self) -> dict[str, Any]:
        """感知城市状态"""
        return {
            'city_stats': self.get_city_stats(),
            'current_time': self.environment.current_time if self.environment else 0
        }
    
    def decide(self) -> dict[str, Any] | None:
        """
        决策：根据人口密度决定是否扩张城市。
        """
        if not self.environment:
            return None
        
        stats = self.get_city_stats()
        current_time = self.environment.current_time
        self.record_perception(
            {
                'city_stats': stats,
                'current_time': current_time,
                'expansion_history_count': len(self.expansion_history),
            },
            importance=3.0
        )
        if self.has_memory():
            self.get_memory().set_working_memory('latest_city_stats', stats)
        
        # 检查冷却时间
        if current_time - self.last_expansion_time < self.expansion_cooldown:
            return None
        
        # 检查是否已达最大规模
        if stats['nodes'] >= self.max_nodes:
            return None
        
        # 人口密度超过阈值，需要扩张
        if stats['density'] >= self.expansion_threshold:
            expansion_plan = self._plan_expansion()
            if expansion_plan:
                self.last_decision = expansion_plan
                self.record_decision(
                    {
                        'action': expansion_plan.get('action', 'expand_city'),
                        'source': 'llm' if expansion_plan.get('is_llm') else 'rule',
                        'expansion_direction': expansion_plan.get('expansion_direction', 'unknown'),
                    },
                    {
                        'density': stats['density'],
                        'reason': expansion_plan.get('reason', ''),
                        'connect_to': expansion_plan.get('connect_to', []),
                    },
                    importance=6.0 if expansion_plan.get('is_llm') else 5.0
                )
                return expansion_plan
        
        return None
    
    def _plan_expansion(self) -> dict[str, Any] | None:
        """规划城市扩张（使用LLM决策最优位置和连接方式）"""
        if not self.environment:
            return None
        
        network = self.environment.road_network
        if len(network.nodes) == 0:
            return None
        
        # 分析网络状态信息
        nodes_info = []
        for node in network.nodes.values():
            load = len(node.incoming_edges) + len(node.outgoing_edges)
            nodes_info.append({
                'id': node.node_id,
                'name': node.name,
                'x': node.position.x,
                'y': node.position.y,
                'load': load
            })
        
        # 计算网络边界和中心状态
        positions = [n.position for n in network.nodes.values()]
        min_x, max_x = min(p.x for p in positions), max(p.x for p in positions)
        min_y, max_y = min(p.y for p in positions), max(p.y for p in positions)
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        
        # 计算形状指标
        width = max_x - min_x
        height = max_y - min_y
        aspect_ratio = width / height if height > 0 else 1.0
        
        # 确定优先扩张方向（避免长条化）
        if aspect_ratio > 1.5:
            preferred_direction = 'vertical'
        elif aspect_ratio < 0.67:
            preferred_direction = 'horizontal'
        else:
            preferred_direction = 'balanced'
        
        if self.use_llm:
            return self._llm_plan_expansion(
                nodes_info, min_x, max_x, min_y, max_y, 
                center_x, center_y, aspect_ratio, preferred_direction
            )
        else:
            # 不使用LLM，直接规则规划并记录
            rule_plan = self._rule_plan_expansion(
                nodes_info, min_x, max_x, min_y, max_y,
                center_x, center_y, aspect_ratio, preferred_direction
            )
            if rule_plan:
                self._archive_llm_decision(
                    category="road_expansion",
                    prompt="[规则规划] LLM已禁用，使用规则规划",
                    parsed=rule_plan,
                    adopted=True,
                    status="success",
                    summary="道路扩展选址（规则规划）",
                    extra={"source": "rule", "reason": "llm_disabled"},
                )
            return rule_plan
    
    def _llm_plan_expansion(
        self, nodes_info: list, min_x: float, max_x: float, 
        min_y: float, max_y: float, center_x: float, center_y: float,
        aspect_ratio: float, preferred_direction: str
    ) -> dict[str, Any] | None:
        """使用LLM规划城市扩张。"""
        prompt = f"""你是一位城市规划专家。基于当前城市网络状态，决定新区域的位置和连接方式。

## 当前网络状态
- 节点数 {len(nodes_info)}
- 网络范围: X[{min_x:.0f}, {max_x:.0f}], Y[{min_y:.0f}, {max_y:.0f}]
- 中心点 ({center_x:.0f}, {center_y:.0f})
- 宽高比 {aspect_ratio:.2f}
- 人口密度: {self.get_population_density()*100:.0f}%

## 形状分析
当前城市网络形状: {preferred_direction}
- 'vertical': 网络太宽，应优先向上/下扩展
- 'horizontal': 网络太高，应优先向左/右扩展 
- 'balanced': 网络均衡，可向任何方向扩展

## 现有节点信息
{json.dumps(nodes_info[:10], ensure_ascii=False, indent=2)}

## 规划约束
1. **避免长条化**: 根据形状分析，优先在较少重叠的方向扩展
2. **网格布局**: 新节点位置应与现有点保持接近网格状布局
3. **可达性**: 新节点必须与至少2个现有点相连接，确保路网连通
4. **优先连接**: 优先连接负载较低的节点，平衡网络
5. **距离控制**: 新节点应与最远的现有点距离250-350米

## 输出格式
请返回JSON格式决策:
{{
    "new_node_x": 坐标x（整数）,
    "new_node_y": 坐标y（整数）,
    "connect_to": ["节点ID1", "节点ID2"],
    "expansion_direction": "扩展方向描述",
    "connect_reason": "选择这些连接的理由",",
    "shape_consideration": "如何改善网络形状",
    "reason": "整体决策理由"
}}
"""
        try:
            llm_manager = self._get_llm_manager()
            if llm_manager:
                response = llm_manager.request_sync_decision(prompt, timeout=15.0)
                if response:
                    plan = self._parse_llm_expansion_plan(
                        response, nodes_info, center_x, center_y
                    )
                    if plan:
                        # 检查新节点位置是否过于靠近现有节点（避免重叠）
                        try:
                            pos_data = plan.get('new_node_position', {})
                            x = float(pos_data.get('x', center_x))
                            y = float(pos_data.get('y', center_y))
                            
                            # 检查是否与现有节点位置重叠（距离小于30米）
                            min_distance_to_existing = float('inf')
                            for node in nodes_info:
                                dist = ((x - node['x']) ** 2 + (y - node['y']) ** 2) ** 0.5
                                min_distance_to_existing = min(min_distance_to_existing, dist)
                            
                            # 只有当新节点与现有节点重叠（距离小于30米）时才拒绝
                            if min_distance_to_existing < 30.0:
                                self._archive_llm_decision(
                                    category="road_expansion",
                                    prompt=prompt,
                                    response=response,
                                    parsed=plan,
                                    adopted=False,
                                    status="fallback",
                                    summary="道路扩展选址",
                                    extra={"fallback_reason": "too_close_to_existing_node", "distance": min_distance_to_existing},
                                )
                                print(f"[城市扩张] LLM 规划点与现有节点距离{min_distance_to_existing:.1f}m过近，回退规则规划")
                                rule_plan = self._rule_plan_expansion(
                                    nodes_info, min_x, max_x, min_y, max_y,
                                    center_x, center_y, aspect_ratio, preferred_direction
                                )
                                # 记录规则规划决策
                                if rule_plan:
                                    self._archive_llm_decision(
                                        category="road_expansion",
                                        prompt="[规则回退] " + prompt[:200] + "...",
                                        parsed=rule_plan,
                                        adopted=True,
                                        status="success",
                                        summary="道路扩展选址（规则规划）",
                                        extra={"source": "rule", "fallback_from": "llm_bounds_check"},
                                    )
                                return rule_plan
                            else:
                                # 检查方向重复
                                plan_direction = plan.get('expansion_direction')
                                recent = self.recent_expansion_directions
                                if plan_direction and len(recent) >= 2 and recent[-1] == plan_direction and recent[-2] == plan_direction:
                                    self._archive_llm_decision(
                                        category="road_expansion",
                                        prompt=prompt,
                                        response=response,
                                        parsed=plan,
                                        adopted=False,
                                        status="fallback",
                                        summary="道路扩展选址",
                                        extra={"fallback_reason": "repeated_direction"},
                                    )
                                    print("[城市扩张] 连续同方向扩张，回退规则规划")
                                    rule_plan = self._rule_plan_expansion(
                                        nodes_info, min_x, max_x, min_y, max_y,
                                        center_x, center_y, aspect_ratio, preferred_direction
                                    )
                                    # 记录规则规划决策
                                    if rule_plan:
                                        self._archive_llm_decision(
                                            category="road_expansion",
                                            prompt="[规则回退] " + prompt[:200] + "...",
                                            parsed=rule_plan,
                                            adopted=True,
                                            status="success",
                                            summary="道路扩展选址（规则规划）",
                                            extra={"source": "rule", "fallback_from": "llm_direction_repeat"},
                                        )
                                    return rule_plan
                                else:
                                    self._archive_llm_decision(
                                        category="road_expansion",
                                        prompt=prompt,
                                        response=response,
                                        parsed=plan,
                                        adopted=True,
                                        status="success",
                                        summary="道路扩展选址",
                                    )
                                    return plan
                        except Exception:
                            self._archive_llm_decision(
                                category="road_expansion",
                                prompt=prompt,
                                response=response,
                                parsed=plan,
                                adopted=False,
                                status="fallback",
                                summary="道路扩展选址",
                                extra={"fallback_reason": "post_validation_exception"},
                            )
                            print("[城市扩张] LLM 结果不可用，回退规则规划")
                            rule_plan = self._rule_plan_expansion(
                                nodes_info, min_x, max_x, min_y, max_y,
                                center_x, center_y, aspect_ratio, preferred_direction
                            )
                            if rule_plan:
                                self._archive_llm_decision(
                                    category="road_expansion",
                                    prompt="[规则回退] " + prompt[:200] + "...",
                                    parsed=rule_plan,
                                    adopted=True,
                                    status="success",
                                    summary="道路扩展选址（规则规划）",
                                    extra={"source": "rule", "fallback_from": "llm_validation_exception"},
                                )
                            return rule_plan
                    else:
                        self._archive_llm_decision(
                            category="road_expansion",
                            prompt=prompt,
                            response=response,
                            parsed=None,
                            adopted=False,
                            status="parse_failed",
                            summary="道路扩展选址",
                        )
                        print("[城市扩张] LLM 结果解析失败，回退规则规划")
                        rule_plan = self._rule_plan_expansion(
                            nodes_info, min_x, max_x, min_y, max_y,
                            center_x, center_y, aspect_ratio, preferred_direction
                        )
                        if rule_plan:
                            self._archive_llm_decision(
                                category="road_expansion",
                                prompt="[规则回退] " + prompt[:200] + "...",
                                parsed=rule_plan,
                                adopted=True,
                                status="success",
                                summary="道路扩展选址（规则规划）",
                                extra={"source": "rule", "fallback_from": "llm_parse_failed"},
                            )
                        return rule_plan
                else:
                    self._archive_llm_decision(
                        category="road_expansion",
                        prompt=prompt,
                        response=None,
                        parsed=None,
                        adopted=False,
                        status="empty_response",
                        summary="道路扩展选址",
                    )
                    print("[城市扩张] LLM 无响应，回退规则规划")
                    rule_plan = self._rule_plan_expansion(
                        nodes_info, min_x, max_x, min_y, max_y,
                        center_x, center_y, aspect_ratio, preferred_direction
                    )
                    if rule_plan:
                        self._archive_llm_decision(
                            category="road_expansion",
                            prompt="[规则回退] 原LLM请求失败",
                            parsed=rule_plan,
                            adopted=True,
                            status="success",
                            summary="道路扩展选址（规则规划）",
                            extra={"source": "rule", "fallback_from": "llm_empty_response"},
                        )
                    return rule_plan
        except Exception as e:
            self._archive_llm_decision(
                category="road_expansion",
                prompt=prompt if 'prompt' in locals() else "",
                response=None,
                parsed=None,
                adopted=False,
                status="error",
                summary="道路扩展选址",
                extra={"error": str(e)},
            )
            print(f"[城市扩张] LLM 规划失败: {e}")
        
        # 最终回退到规则规划
        rule_plan = self._rule_plan_expansion(
            nodes_info, min_x, max_x, min_y, max_y,
            center_x, center_y, aspect_ratio, preferred_direction
        )
        if rule_plan:
            self._archive_llm_decision(
                category="road_expansion",
                prompt="[规则回退] 原LLM请求异常",
                parsed=rule_plan,
                adopted=True,
                status="success",
                summary="道路扩展选址（规则规划）",
                extra={"source": "rule", "fallback_from": "llm_exception"},
            )
        return rule_plan
    
    def _archive_llm_decision(
        self,
        category: str,
        prompt: str,
        response: str | None = None,
        parsed: dict[str, Any] | None = None,
        adopted: bool | None = None,
        status: str = "success",
        summary: str | None = None,
        extra: dict[str, Any] | None = None
    ) -> None:
        """归档路网规划相关的大模型决策文本。"""
        timestamp = self.environment.current_time if self.environment else 0.0
        record = {
            "id": f"{self.agent_id}_{category}_{int(timestamp * 1000)}_{len(self.llm_decision_archive) + 1}",
            "timestamp": timestamp,
            "agent_id": self.agent_id,
            "agent_type": "planning",
            "category": category,
            "summary": summary or "道路扩展决策",
            "prompt": prompt,
            "response": response or "",
            "parsed_decision": parsed or {},
            "adopted": adopted,
            "status": status,
        }
        if extra:
            record["extra"] = extra
        self.llm_decision_archive.append(record)
        if len(self.llm_decision_archive) > 300:
            self.llm_decision_archive = self.llm_decision_archive[-300:]

    def _parse_llm_expansion_plan(
        self, response: str, nodes_info: list, center_x: float, center_y: float
    ) -> dict[str, Any] | None:
        """解析LLM的扩张计划响应"""
        try:
            start = response.find('{')
            end = response.rfind('}')
            if start == -1 or end == -1:
                return None
            
            plan = json.loads(response[start:end+1])
            
            # 验证节点ID
            connect_to = plan.get('connect_to', [])
            valid_nodes = [n['id'] for n in nodes_info]
            valid_connections = [nid for nid in connect_to if nid in valid_nodes]
            
            if len(valid_connections) < 1:
                return None
            
            return {
                'action': 'expand_city',
                'new_node_position': {
                    'x': plan.get('new_node_x', center_x),
                    'y': plan.get('new_node_y', center_y)
                },
                'connect_to': valid_connections[:3],
                'expansion_direction': plan.get('expansion_direction', '未知'),
                'connect_reason': plan.get('connect_reason', ''),
                'shape_consideration': plan.get('shape_consideration', ''),
                'reason': plan.get('reason', 'LLM规划'),
                'is_llm': True
            }
            
        except Exception as e:
            print(f"[城市扩张] 解分 LLM 响应失败: {e}")
            return None
    
    def _get_zones_for_expansion_planning(self) -> list:
        """获取环版有区域列表用ㄤ于扩展张规划。"""
        zoning_agent = self._get_zoning_agent()
        if zoning_agent and hasattr(zoning_agent, 'zone_manager'):
            return list(zoning_agent.zone_manager.zones.values())
        return []

    def _load_procedural_growth_config(self) -> dict[str, Any]:
        """加载 procedural_city_generation 的 roadmap 参数。"""
        if self._procedural_growth_config is not None:
            return self._procedural_growth_config

        default_conf: dict[str, Any] = {
            "gridpForward": 100.0,
            "gridpTurn": 9.0,
            "gridlMin": 1.0,
            "gridlMax": 1.0,
            "organicpForward": 92.0,
            "organicpTurn": 7.0,
            "organiclMin": 0.8,
            "organiclMax": 1.6,
            "radialpForward": 100.0,
            "radialpTurn": 10.0,
            "radiallMin": 0.8,
            "radiallMax": 1.5,
        }

        try:
            conf_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "procedural_city_generation-master",
                "procedural_city_generation",
                "inputs",
                "roadmap.conf",
            )
            if os.path.exists(conf_path):
                with open(conf_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                for k, v in raw.items():
                    if isinstance(v, dict) and "value" in v:
                        default_conf[k] = v["value"]
                    else:
                        default_conf[k] = v
        except Exception as e:
            print(f"[城市扩张] 读取 procedural roadmap.conf 失败，使用默认参数: {e}")

        self._procedural_growth_config = default_conf
        return default_conf

    def _find_procedural_expansion_candidates(
        self,
        nodes_info: list[dict[str, Any]],
        grid_size: float,
        preferred_direction: str,
    ) -> list[dict[str, Any]]:
        """
        参考 procedural_city_generation 的 grid/organic/radial growth 方则生成候选点。
        """
        if not nodes_info:
            return []

        conf = self._load_procedural_growth_config()
        center_x = sum(n["x"] for n in nodes_info) / len(nodes_info)
        center_y = sum(n["y"] for n in nodes_info) / len(nodes_info)
        existing_positions = [(n["x"], n["y"]) for n in nodes_info]

        leftmost_x = min(n["x"] for n in nodes_info)
        rightmost_x = max(n["x"] for n in nodes_info)
        topmost_y = min(n["y"] for n in nodes_info)
        bottommost_y = max(n["y"] for n in nodes_info)
        frontier_nodes = [
            n for n in nodes_info
            if abs(n["x"] - leftmost_x) < 12
            or abs(n["x"] - rightmost_x) < 12
            or abs(n["y"] - topmost_y) < 12
            or abs(n["y"] - bottommost_y) < 12
        ]
        if not frontier_nodes:
            frontier_nodes = nodes_info[:]

        min_node_gap = max(self.min_edge_length * 0.7, grid_size * 0.55)
        min_length = max(self.min_edge_length * 0.75, grid_size * 0.7)
        max_length = max(self.max_edge_length * 0.9, grid_size * 1.25)

        def _too_close(x: float, y: float) -> bool:
            for ex, ey in existing_positions:
                if math.hypot(x - ex, y - ey) < min_node_gap:
                    return True
            return False

        def _direction_label(dx: float, dy: float) -> str:
            if abs(dx) > abs(dy):
                return "right" if dx >= 0 else "left"
            return "down" if dy >= 0 else "up"

        def _normalize(vx: float, vy: float) -> tuple[float, float]:
            norm = math.hypot(vx, vy)
            if norm < 1e-6:
                return (1.0, 0.0)
            return (vx / norm, vy / norm)

        candidates: list[dict[str, Any]] = []

        for anchor in frontier_nodes:
            ax, ay = anchor["x"], anchor["y"]
            vx, vy = _normalize(ax - center_x, ay - center_y)
            if preferred_direction == "horizontal":
                vx, vy = _normalize(vx + random.choice([-0.2, 0.2]), vy * 0.4)
            elif preferred_direction == "vertical":
                vx, vy = _normalize(vx * 0.4, vy + random.choice([-0.2, 0.2]))

            # 1) grid 风格（正交、直线延展）
            grid_len = random.uniform(
                float(conf.get("gridlMin", 1.0)) * grid_size * 0.9,
                float(conf.get("gridlMax", 1.0)) * grid_size * 1.05,
            )
            gx = ax + round(vx) * max(min_length, min(max_length, grid_len))
            gy = ay + round(vy) * max(min_length, min(max_length, grid_len))
            if not _too_close(gx, gy):
                candidates.append({
                    "x": gx,
                    "y": gy,
                    "direction": _direction_label(gx - ax, gy - ay),
                    "anchor": anchor,
                    "priority": 1 if preferred_direction in ("horizontal", "vertical") else 2,
                    "type": "procedural_grid",
                    "source": "procedural",
                })

            # 2) organic 风格（偏转 30~120 度）
            organic_len = random.uniform(
                float(conf.get("organiclMin", 0.8)) * grid_size * 0.85,
                float(conf.get("organiclMax", 1.6)) * grid_size * 1.1,
            )
            turn = random.choice([-1, 1]) * random.uniform(30, 120)
            rad = math.radians(turn)
            ox = vx * math.cos(rad) - vy * math.sin(rad)
            oy = vx * math.sin(rad) + vy * math.cos(rad)
            ox, oy = _normalize(ox, oy)
            oxp = ax + ox * max(min_length, min(max_length, organic_len))
            oyp = ay + oy * max(min_length, min(max_length, organic_len))
            if not _too_close(oxp, oyp):
                candidates.append({
                    "x": oxp,
                    "y": oyp,
                    "direction": _direction_label(oxp - ax, oyp - ay),
                    "anchor": anchor,
                    "priority": 2,
                    "type": "procedural_organic",
                    "source": "procedural",
                })

            # 3) radial 风格（向中心/离中心辐射）
            radial_len = random.uniform(
                float(conf.get("radiallMin", 0.8)) * grid_size * 0.85,
                float(conf.get("radiallMax", 1.5)) * grid_size * 1.1,
            )
            rsign = random.choice([1.0, -1.0])
            rx, ry = _normalize((ax - center_x) * rsign, (ay - center_y) * rsign)
            rxp = ax + rx * max(min_length, min(max_length, radial_len))
            ryp = ay + ry * max(min_length, min(max_length, radial_len))
            if not _too_close(rxp, ryp):
                candidates.append({
                    "x": rxp,
                    "y": ryp,
                    "direction": _direction_label(rxp - ax, ryp - ay),
                    "anchor": anchor,
                    "priority": 2,
                    "type": "procedural_radial",
                    "source": "procedural",
                })

        return candidates
    
    def _find_expansion_candidates_with_zones(
        self, nodes_info: list, grid_size: float, preferred_direction: str
    ) -> list:
        """
        扩惧埌扩展张值欓変綅网?- 涓否牸浠庡体鍓嶆要最栧洿否戝扩展展。?
        
        口冭檻鍦ㄥ体鍓嶈矾网戞要最栧洿涔嬪鐨勪綅网）确繚城市否戝用熼暱。?
        """
        candidates = []
        
        # 扩惧埌最大栧洿鐨划潗标?
        leftmost_x = min(n['x'] for n in nodes_info)
        rightmost_x = max(n['x'] for n in nodes_info)
        topmost_y = min(n['y'] for n in nodes_info)
        bottommost_y = max(n['y'] for n in nodes_info)
        
        # 口在最大栧洿涔嬪添诲姞值欓変綅网?
        # 向左扩展展 - 鍦ㄦ要作︿晶涔嬪
        leftmost_nodes = [n for n in nodes_info if abs(n['x'] - leftmost_x) < 10]
        for n in leftmost_nodes:
            new_x = leftmost_x - grid_size
            candidates.append({
                'x': new_x,
                'y': n['y'],
                'direction': 'left',
                'anchor': n,
                'priority': 1 if preferred_direction == 'horizontal' else 2,
                'type': 'grid_outward'
            })
        
        # 向右扩展展 - 鍦ㄦ要口位晶涔嬪
        rightmost_nodes = [n for n in nodes_info if abs(n['x'] - rightmost_x) < 10]
        for n in rightmost_nodes:
            new_x = rightmost_x + grid_size
            candidates.append({
                'x': new_x,
                'y': n['y'],
                'direction': 'right',
                'anchor': n,
                'priority': 1 if preferred_direction == 'horizontal' else 2,
                'type': 'grid_outward'
            })
        
        # 向上扩展展 - 鍦ㄦ要涓婃式涔嬪
        topmost_nodes = [n for n in nodes_info if abs(n['y'] - topmost_y) < 10]
        for n in topmost_nodes:
            new_y = topmost_y - grid_size
            candidates.append({
                'x': n['x'],
                'y': new_y,
                'direction': 'up',
                'anchor': n,
                'priority': 1 if preferred_direction == 'vertical' else 2,
                'type': 'grid_outward'
            })
        
        # 向下扩展展 - 鍦ㄦ要涓嬫式涔嬪
        bottommost_nodes = [n for n in nodes_info if abs(n['y'] - bottommost_y) < 10]
        for n in bottommost_nodes:
            new_y = bottommost_y + grid_size
            candidates.append({
                'x': n['x'],
                'y': new_y,
                'direction': 'down',
                'anchor': n,
                'priority': 1 if preferred_direction == 'vertical' else 2,
                'type': 'grid_outward'
            })
        
        return candidates
    
    def _line_intersects_zone(self, x1: float, y1: float, x2: float, y2: float, zone) -> bool:
        """检查ョ嚎娈垫是否︿与区域鐩镐氦：进冭檻避撹矾缂撳啿：夈"""
        road_buffer = 30  # 避撹矾却婂 + 定夊叏距离
        
        # 扩展展区域边界和浠冷寘否于路紦决?
        zone_min_x = zone.center.x - zone.width / 2 - road_buffer
        zone_max_x = zone.center.x + zone.width / 2 + road_buffer
        zone_min_y = zone.center.y - zone.height / 2 - road_buffer
        zone_max_y = zone.center.y + zone.height / 2 + road_buffer
        
        # 蹇拟查ワ细濡傛灉涓や釜绔偣閮藉在区域否优一渚э）涓尖细鐩镐氦
        if (x1 < zone_min_x and x2 < zone_min_x) or (x1 > zone_max_x and x2 > zone_max_x):
            return False
        if (y1 < zone_min_y and y2 < zone_min_y) or (y1 > zone_max_y and y2 > zone_max_y):
            return False
        
        # 优跨敤 Liang-Barsky 管楁硶检查ョ嚎娈典与鐭展心鐩镐氦
        dx = x2 - x1
        dy = y2 - y1
        
        p = [-dx, dx, -dy, dy]
        q = [x1 - zone_min_x, zone_max_x - x1, y1 - zone_min_y, zone_max_y - y1]
        
        u1 = 0
        u2 = 1
        
        for i in range(4):
            if p[i] == 0:
                if q[i] < 0:
                    return False
            else:
                t = q[i] / p[i]
                if p[i] < 0:
                    u1 = max(u1, t)
                else:
                    u2 = min(u2, t)
                if u1 > u2:
                    return False
        
        return True
    
    def _find_path_around_zones(
        self, from_node, to_node, zones: list
    ) -> list[dict] | None:
        """
        密绘壘络曡繃功能区域鐨勮矾寰勶紙鎶樼嚎路緞：夈?
        
        返回路緞涓婄的涓棿点方垪琛紙涓嶅寘否捣点方和络堢偣：夈?
        路緞娌跨潃区域边界紭璧般?
        """
        x1, y1 = from_node.position.x, from_node.position.y
        x2, y2 = to_node.position.x, to_node.position.y
        
        # 检查ョ洿鎺ヨ繛鎺否是否︿细绌胯繃区域
        intersects = False
        for zone in zones:
            if self._line_intersects_zone(x1, y1, x2, y2, zone):
                intersects = True
                break
        
        if not intersects:
            # 鐩却帴连接涓尖细绌胯繃区域
            return []
        
        # 需要佺粫琛岋）娌跨潃区域边界紭璧?
        # 扩惧埌需要佺粫琛岀的区域
        blocking_zones = []
        for zone in zones:
            if self._line_intersects_zone(x1, y1, x2, y2, zone):
                blocking_zones.append(zone)
        
        if not blocking_zones:
            return []
        
        # 管却曠略鐣ワ细娌跨潃闃绘尅区域鐨勮竟缂樿蛋
        # 选择最过戠的闃绘尅区域：优粠鍏惰竟缂樼粫琛?
        nearest_zone = min(blocking_zones, 
            key=lambda z: ((z.center.x - (x1+x2)/2)**2 + (z.center.y - (y1+y2)/2)**2))
        
        road_buffer = 40
        
        # 区域边界和：堝惈避撹矾缂撳啿：?
        z_min_x = nearest_zone.center.x - nearest_zone.width / 2 - road_buffer
        z_max_x = nearest_zone.center.x + nearest_zone.width / 2 + road_buffer
        z_min_y = nearest_zone.center.y - nearest_zone.height / 2 - road_buffer
        z_max_y = nearest_zone.center.y + nearest_zone.height / 2 + road_buffer
        
        # 判断浠庡摢涓式否戠粫琛?
        # 比较涓ょ络曡新方鐨勭粫琛岃窛绂?
        
        # 新方1：氫粠涓婃式/涓嬫式络曡：堟按骞决式否戣繛鎺ワ級
        if abs(x2 - x1) > abs(y2 - y1):
            # 姘村钩连接：优粠涓婃式我栦笅新界粫琛?
            mid_x = (x1 + x2) / 2
            
            # 计算涓や釜络曡新方鐨勪唬浠?
            # 浠庝笂新界粫琛?
            path_top = [
                {'x': mid_x, 'y': z_min_y, 'type': 'corner'},
            ]
            # 浠庝笅新界粫琛?
            path_bottom = [
                {'x': mid_x, 'y': z_max_y, 'type': 'corner'},
            ]
            
            # 选择络曡距离鏇寸煭鐨勬式免?
            dist_via_top = abs(y1 - z_min_y) + abs(z_min_y - y2)
            dist_via_bottom = abs(y1 - z_max_y) + abs(z_max_y - y2)
            
            return path_top if dist_via_top < dist_via_bottom else path_bottom
        
        else:
            # 鍨傜洿连接：优粠作︿晶我栧彸渚х粫琛?
            mid_y = (y1 + y2) / 2
            
            # 浠庡乏渚х粫琛?
            path_left = [
                {'x': z_min_x, 'y': mid_y, 'type': 'corner'},
            ]
            # 浠庡彸渚х粫琛?
            path_right = [
                {'x': z_max_x, 'y': mid_y, 'type': 'corner'},
            ]
            
            # 选择络曡距离鏇寸煭鐨勬式免?
            dist_via_left = abs(x1 - z_min_x) + abs(z_min_x - x2)
            dist_via_right = abs(x1 - z_max_x) + abs(z_max_x - x2)
            
            return path_left if dist_via_left < dist_via_right else path_right
    
    def _rule_plan_expansion(
        self, nodes_info: list, min_x: float, max_x: float,
        min_y: float, max_y: float, center_x: float, center_y: float,
        aspect_ratio: float, preferred_direction: str
    ) -> dict[str, Any] | None:
        """优跨敤规划则规划城市扩展张：屾柊节点鍦ㄥ鍥达）避撹矾娌垮尯城熻竟缂樿蛋：堟姌绾匡級。"""
        # 鏀堕泦扩最夌幇最夌的X和孻坐标
        existing_x = sorted(set(n['x'] for n in nodes_info))
        existing_y = sorted(set(n['y'] for n in nodes_info))
        
        # 计算网戞牸间磋窛
        x_gaps = [existing_x[i+1] - existing_x[i] for i in range(len(existing_x)-1)]
        y_gaps = [existing_y[i+1] - existing_y[i] for i in range(len(existing_y)-1)]
        grid_size = 300
        if x_gaps:
            grid_size = max(250, min(350, sum(x_gaps) / len(x_gaps)))
        elif y_gaps:
            grid_size = max(250, min(350, sum(y_gaps) / len(y_gaps)))
        
        # 计算当前边界和：堝在扩最夊垎鏀能需要侊級
        leftmost_x = min(n['x'] for n in nodes_info)
        rightmost_x = max(n['x'] for n in nodes_info)
        topmost_y = min(n['y'] for n in nodes_info)
        bottommost_y = max(n['y'] for n in nodes_info)
        
        # 获取值欓変綅网?
        candidates = self._find_expansion_candidates_with_zones(
            nodes_info, grid_size, preferred_direction
        )
        candidates.extend(
            self._find_procedural_expansion_candidates(
                nodes_info=nodes_info,
                grid_size=grid_size,
                preferred_direction=preferred_direction,
            )
        )
        
        # 过滤鎺夊否络工瓨鍦ㄧ的节点优嶇疆
        existing_positions = {(n['x'], n['y']) for n in nodes_info}
        candidates = [c for c in candidates if (c['x'], c['y']) not in existing_positions]
        # 去重（却坐标只保留更高优先级）
        unique_candidates: dict[tuple[float, float], dict[str, Any]] = {}
        for c in candidates:
            key = (round(c["x"], 1), round(c["y"], 1))
            old = unique_candidates.get(key)
            if old is None or (c.get("priority", 9) < old.get("priority", 9)):
                unique_candidates[key] = c
        candidates = list(unique_candidates.values())
        
        # 获取区域列表用ㄤ于路緞规划
        zones = self._get_zones_for_expansion_planning()
        
        if not candidates:
            # 濡傛灉娌℃有值欓夛）否戝榛樿扩展展
            if preferred_direction == 'horizontal':
                target_x = rightmost_x + grid_size
                target_y = existing_y[len(existing_y)//2] if existing_y else center_y
                expansion_direction = 'right'
            else:
                target_x = existing_x[len(existing_x)//2] if existing_x else center_x
                target_y = bottommost_y + grid_size
                expansion_direction = 'down'
            anchor_node = nodes_info[0]
            candidate_type = 'grid'
        else:
            # 优先选择优先级高的候选
            direction_counts = {}
            for d in self.recent_expansion_directions:
                direction_counts[d] = direction_counts.get(d, 0) + 1

            def _candidate_score(c):
                dir_count = direction_counts.get(c['direction'], 0)
                source_bonus = 0 if c.get("source") == "procedural" else 1
                type_pref = 0 if c.get("type") == "procedural_grid" else 1
                return (c['priority'], source_bonus, type_pref, dir_count, c['anchor']['load'], random.random() * 0.01)

            candidates.sort(key=_candidate_score)
            
            best_candidate = candidates[0]
            target_x = best_candidate['x']
            target_y = best_candidate['y']
            expansion_direction = best_candidate['direction']
            anchor_node = best_candidate['anchor']
            candidate_type = best_candidate.get('type', 'grid')
        allow_non_orthogonal = candidate_type in {'procedural_organic', 'procedural_radial'}
        
        # 选择连接节点 - 连接划版墍最夊悎通傜的最栧洿閭诲眳：堝心我愮网标肩粨分勶級
        connect_to = []
        path_waypoints = {}  # 却储姣忎釜连接鐨勮矾寰勭偣
        
        # 扩惧埌扩最夊鍥磋妭点?
        outer_nodes = [
            n for n in nodes_info
            if abs(n['x'] - leftmost_x) < 10 or
               abs(n['x'] - rightmost_x) < 10 or
               abs(n['y'] - topmost_y) < 10 or
               abs(n['y'] - bottommost_y) < 10
        ]
        
        if not outer_nodes:
            # 濡傛灉娌℃有最栧洿节点：优使用ㄦ要过戠的节点
            nearest = min(nodes_info, key=lambda n: (n['x'] - target_x)**2 + (n['y'] - target_y)**2)
            connect_to.append(nearest['id'])
        else:
            # 扩惧埌扩最夊在否优傝窛绂诲唴鐨划鍥撮偦灞?
            # 密逛于网格布局：屾柊节点密旇连接划扮浉閭荤的最栧洿节点
            
            for outer_node in outer_nodes:
                # 计算距离
                dist = ((outer_node['x'] - target_x)**2 + (outer_node['y'] - target_y)**2) ** 0.5
                
                # 口冭檻距离鍦ㄥ悎鐞嗚寖鍥村唴鐨勮妭点癸紙网戞牸间磋窛鐨?.5值尖互决咃級
                if dist > grid_size * 1.5:
                    continue
                
                # 检查否是否扩是姝ｄ氦方向鐨勯偦灞咃紙X我朰坐标鐩稿悓我栨帴过戯級
                dx = abs(outer_node['x'] - target_x)
                dy = abs(outer_node['y'] - target_y)
                
                # 姝ｄ氦閭诲眳：氫仅要扩是姘村钩我栧瀭鐩却式否?
                is_orthogonal = min(dx, dy) < 50
                is_near_diagonal = abs(dx - dy) < 80 and max(dx, dy) <= grid_size * 1.35

                if not allow_non_orthogonal and not is_orthogonal and not is_near_diagonal:
                    continue
                
                # 添诲姞划拌繛鎺冷垪琛?
                connect_to.append(outer_node['id'])
                
                # 计算划拌繖涓妭点界的路緞：进冭檻区域络曡：?
                if self.environment:
                    from_node_obj = None
                    for node in self.environment.road_network.nodes.values():
                        if node.node_id == outer_node['id']:
                            from_node_obj = node
                            break
                    
                    if from_node_obj:
                        temp_pos = Vector2D(target_x, target_y)
                        temp_node = type('TempNode', (), {'position': temp_pos})()
                        
                        path = self._find_path_around_zones(temp_node, from_node_obj, zones)
                        if path:
                            path_waypoints[outer_node['id']] = path
            
            # 濡傛灉过樻是娌℃有扩惧埌否优傜的连接：优使用ㄦ要过戠的閿氱偣
            if len(connect_to) < 2 and outer_nodes:
                nearest_outer = sorted(
                    outer_nodes,
                    key=lambda n: (n['x'] - target_x) ** 2 + (n['y'] - target_y) ** 2
                )
                for n in nearest_outer:
                    if n['id'] not in connect_to:
                        connect_to.append(n['id'])
                    if len(connect_to) >= 2:
                        break

            if not connect_to and anchor_node:
                connect_to.append(anchor_node['id'])

        # 去重并限制连接数，避免一次扩张产生过多边
        connect_to = list(dict.fromkeys(connect_to))[:4]
        
        return {
            'action': 'expand_city',
            'new_node_position': {'x': target_x, 'y': target_y},
            'connect_to': connect_to,
            'path_waypoints': path_waypoints,  # 却储路緞点逛息?
            'expansion_direction': expansion_direction,
            'connect_reason': f'融合 procedural growth: 向{expansion_direction}扩展, 候选类型: {candidate_type}',
            'shape_consideration': f'融合 grid/organic/radial 方则，优先外圈增长并保持道路连通，道路间距约 {grid_size:.0f}m',
            'reason': f'方则规划(融合 procedural): 人口密度达到{self.get_population_density()*100:.0f}%',
            'is_llm': False,
            'candidate_type': candidate_type
        }
    
    def _get_llm_manager(self):
        """获取LLM管理鍣ㄣ"""
        try:
            from city.llm.llm_manager import get_llm_manager
            return get_llm_manager()
        except:
            return None

    def _iter_unique_edges(self):
        """Iterate each physical road once (dedupe bidirectional edges)."""
        if not self.environment:
            return
        seen: set[tuple[str, str]] = set()
        for edge in self.environment.road_network.edges.values():
            key = tuple(sorted((edge.from_node.node_id, edge.to_node.node_id)))
            if key in seen:
                continue
            seen.add(key)
            yield edge

    def _adjust_position_if_near_road(self, pos: Vector2D, min_clearance: float = 35.0) -> Vector2D:
        """
        If a new node falls on an existing road segment, move it slightly away.
        This avoids creating overlapping roads after expansion.
        """
        if not self.environment:
            return pos

        network = self.environment.road_network
        x0, y0 = pos.x, pos.y

        for edge in self._iter_unique_edges():
            x1, y1 = edge.from_node.position.x, edge.from_node.position.y
            x2, y2 = edge.to_node.position.x, edge.to_node.position.y
            dx, dy = x2 - x1, y2 - y1
            seg_len2 = dx * dx + dy * dy
            if seg_len2 < 1e-6:
                continue

            t = ((x0 - x1) * dx + (y0 - y1) * dy) / seg_len2
            if t <= 0.08 or t >= 0.92:
                continue

            proj_x = x1 + t * dx
            proj_y = y1 + t * dy
            dist = math.sqrt((x0 - proj_x) ** 2 + (y0 - proj_y) ** 2)
            if dist >= min_clearance:
                continue

            seg_len = math.sqrt(seg_len2)
            nx, ny = -dy / seg_len, dx / seg_len
            shift = min_clearance - dist + 8.0

            candidates = [
                Vector2D(x0 + nx * shift, y0 + ny * shift),
                Vector2D(x0 - nx * shift, y0 - ny * shift),
            ]

            def score(candidate: Vector2D) -> float:
                node_clear = min(
                    (
                        candidate.distance_to(node.position)
                        for node in network.nodes.values()
                    ),
                    default=9999.0
                )
                edge_clear = min(
                    (
                        self._point_to_segment_distance(
                            candidate.x,
                            candidate.y,
                            e.from_node.position.x,
                            e.from_node.position.y,
                            e.to_node.position.x,
                            e.to_node.position.y
                        )
                        for e in self._iter_unique_edges()
                    ),
                    default=9999.0
                )
                return min(node_clear, edge_clear)

            candidates.sort(key=score, reverse=True)
            for candidate in candidates:
                if score(candidate) >= 22.0:
                    print(
                        f"[城市扩张] 新节点位置贴近道路，自动偏移到 "
                        f"({candidate.x:.1f}, {candidate.y:.1f})"
                    )
                    return candidate

            return candidates[0]

        return pos

    def _orientation(self, ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> float:
        return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)

    def _on_segment(self, ax: float, ay: float, bx: float, by: float, cx: float, cy: float, tol: float = 1e-6) -> bool:
        return (
            min(ax, bx) - tol <= cx <= max(ax, bx) + tol
            and min(ay, by) - tol <= cy <= max(ay, by) + tol
        )

    def _segments_intersect_strict(
        self,
        a1x: float, a1y: float, a2x: float, a2y: float,
        b1x: float, b1y: float, b2x: float, b2y: float,
        tol: float = 1e-6
    ) -> bool:
        """Check whether two segments intersect at a non-endpoint position."""
        o1 = self._orientation(a1x, a1y, a2x, a2y, b1x, b1y)
        o2 = self._orientation(a1x, a1y, a2x, a2y, b2x, b2y)
        o3 = self._orientation(b1x, b1y, b2x, b2y, a1x, a1y)
        o4 = self._orientation(b1x, b1y, b2x, b2y, a2x, a2y)

        # Proper crossing
        if (o1 * o2 < -tol) and (o3 * o4 < -tol):
            return True

        # Colinear / touching cases (treat as intersect if not just endpoint touching)
        colinear_hit = (
            (abs(o1) <= tol and self._on_segment(a1x, a1y, a2x, a2y, b1x, b1y, tol))
            or (abs(o2) <= tol and self._on_segment(a1x, a1y, a2x, a2y, b2x, b2y, tol))
            or (abs(o3) <= tol and self._on_segment(b1x, b1y, b2x, b2y, a1x, a1y, tol))
            or (abs(o4) <= tol and self._on_segment(b1x, b1y, b2x, b2y, a2x, a2y, tol))
        )
        if not colinear_hit:
            return False

        endpoints_a = {(a1x, a1y), (a2x, a2y)}
        endpoints_b = {(b1x, b1y), (b2x, b2y)}
        shared_endpoints = endpoints_a & endpoints_b
        if shared_endpoints:
            return False
        return True

    def _segments_nearly_parallel_and_overlapping(
        self,
        a1x: float, a1y: float, a2x: float, a2y: float,
        b1x: float, b1y: float, b2x: float, b2y: float,
        min_parallel_gap: float = 20.0,
        min_overlap_span: float = 30.0
    ) -> bool:
        """Check if two segments run almost parallel and overlap in projection."""
        adx, ady = a2x - a1x, a2y - a1y
        bdx, bdy = b2x - b1x, b2y - b1y
        alen = math.sqrt(adx * adx + ady * ady)
        blen = math.sqrt(bdx * bdx + bdy * bdy)
        if alen < 1e-6 or blen < 1e-6:
            return False

        cos_theta = abs((adx * bdx + ady * bdy) / (alen * blen))
        if cos_theta < 0.98:
            return False

        # Use dominant axis to compute overlap span.
        if abs(adx) >= abs(ady):
            overlap = min(max(a1x, a2x), max(b1x, b2x)) - max(min(a1x, a2x), min(b1x, b2x))
        else:
            overlap = min(max(a1y, a2y), max(b1y, b2y)) - max(min(a1y, a2y), min(b1y, b2y))

        if overlap < min_overlap_span:
            return False

        dist_a_mid_to_b = self._point_to_segment_distance((a1x + a2x) / 2, (a1y + a2y) / 2, b1x, b1y, b2x, b2y)
        dist_b_mid_to_a = self._point_to_segment_distance((b1x + b2x) / 2, (b1y + b2y) / 2, a1x, a1y, a2x, a2y)
        return min(dist_a_mid_to_b, dist_b_mid_to_a) < min_parallel_gap

    def _has_direct_connection(self, node1: Node, node2: Node) -> bool:
        """Check whether two nodes already have at least one direct edge."""
        for edge in node1.outgoing_edges:
            if edge.to_node == node2:
                return True
        for edge in node1.incoming_edges:
            if edge.from_node == node2:
                return True
        return False

    def _line_intersection_params(
        self,
        a1x: float, a1y: float, a2x: float, a2y: float,
        b1x: float, b1y: float, b2x: float, b2y: float
    ) -> tuple[float, float] | None:
        """
        Return (t, u) for intersection of lines:
        A(t)=A1+t*(A2-A1), B(u)=B1+u*(B2-B1).
        """
        dax = a2x - a1x
        day = a2y - a1y
        dbx = b2x - b1x
        dby = b2y - b1y
        denom = dax * dby - day * dbx
        if abs(denom) < 1e-8:
            return None
        rx = b1x - a1x
        ry = b1y - a1y
        t = (rx * dby - ry * dbx) / denom
        u = (rx * day - ry * dax) / denom
        return (t, u)

    def _find_existing_node_near(self, x: float, y: float, radius: float = 28.0) -> Node | None:
        """Find an existing node near a given coordinate."""
        if not self.environment:
            return None
        best = None
        best_d = float("inf")
        p = Vector2D(x, y)
        for node in self.environment.road_network.nodes.values():
            d = p.distance_to(node.position)
            if d < radius and d < best_d:
                best = node
                best_d = d
        return best

    def _ensure_intersection_node_connected(self, inter_node: Node, host_edge: Edge) -> None:
        """Connect intersection node to both endpoints of the host edge."""
        if not self.environment:
            return
        for endpoint in (host_edge.from_node, host_edge.to_node):
            if inter_node.node_id == endpoint.node_id:
                continue
            if self._has_direct_connection(inter_node, endpoint):
                continue
            if self.environment.can_connect_nodes(
                inter_node,
                endpoint,
                max_distance=max(self.max_edge_length * 1.25, 650.0)
            ):
                self.environment.add_edge_dynamically(
                    from_node=inter_node,
                    to_node=endpoint,
                    num_lanes=2,
                    bidirectional=True
                )

    def _adjust_target_node_with_vertex_checks(self, from_node: Node, to_node: Node) -> tuple[Node, str | None]:
        """
        Apply procedural-style vertex checks before adding edge:
        1) snap to near existing vertex
        2) extend edge to nearby host-edge intersection
        3) shorten edge to first intersection with host edge
        """
        if not self.environment:
            return to_node, None

        x1, y1 = from_node.position.x, from_node.position.y
        x2, y2 = to_node.position.x, to_node.position.y

        # Case 1: new vertex too close to an existing vertex -> snap to that vertex.
        snap_node = self._find_existing_node_near(x2, y2, radius=38.0)
        if snap_node and snap_node.node_id not in {from_node.node_id, to_node.node_id}:
            return snap_node, "snap_to_near_vertex"

        best_shorten: tuple[float, float, float, Edge] | None = None
        best_extend: tuple[float, float, float, Edge] | None = None

        for edge in self._iter_unique_edges():
            a = edge.from_node
            b = edge.to_node
            if from_node.node_id in {a.node_id, b.node_id}:
                continue
            ex1, ey1 = a.position.x, a.position.y
            ex2, ey2 = b.position.x, b.position.y

            params = self._line_intersection_params(x1, y1, x2, y2, ex1, ey1, ex2, ey2)
            if params is None:
                continue
            t, u = params
            ix = x1 + (x2 - x1) * t
            iy = y1 + (y2 - y1) * t
            dist_from_start = math.hypot(ix - x1, iy - y1)

            # Case 3: candidate intersects an existing edge -> shorten to intersection.
            if 1e-3 < t < 0.999 and -1e-3 <= u <= 1.001:
                if best_shorten is None or dist_from_start < best_shorten[0]:
                    best_shorten = (dist_from_start, ix, iy, edge)
                continue

            # Case 2: candidate stops shortly before host edge -> extend to intersection.
            end_to_edge = self._point_to_segment_distance(x2, y2, ex1, ey1, ex2, ey2)
            if 1.0 < t <= 1.35 and -1e-3 <= u <= 1.001 and end_to_edge <= 36.0:
                if best_extend is None or dist_from_start < best_extend[0]:
                    best_extend = (dist_from_start, ix, iy, edge)

        chosen = best_shorten if best_shorten is not None else best_extend
        if chosen is None:
            return to_node, None

        _, ix, iy, host_edge = chosen
        near_node = self._find_existing_node_near(ix, iy, radius=22.0)
        if near_node:
            return near_node, "snap_to_intersection_near_vertex"

        inter_node = self.environment.add_node_dynamically(
            position=Vector2D(ix, iy),
            name=f"inter_{len(self.expansion_history)+1}"
        )
        self._ensure_intersection_node_connected(inter_node, host_edge)
        if best_shorten is not None:
            return inter_node, "shorten_to_intersection"
        return inter_node, "extend_to_intersection"

    def _would_overlap_existing_roads(self, from_node: Node, to_node: Node) -> bool:
        """Validate whether a new road segment would overlap/cross existing roads."""
        if not self.environment:
            return True

        x1, y1 = from_node.position.x, from_node.position.y
        x2, y2 = to_node.position.x, to_node.position.y
        candidate_key = tuple(sorted((from_node.node_id, to_node.node_id)))

        for edge in self._iter_unique_edges():
            a = edge.from_node
            b = edge.to_node
            existing_key = tuple(sorted((a.node_id, b.node_id)))

            # Same undirected road already exists.
            if existing_key == candidate_key:
                return True

            # Shared endpoint is allowed as a proper intersection.
            if len({from_node.node_id, to_node.node_id} & {a.node_id, b.node_id}) > 0:
                continue

            ex1, ey1 = a.position.x, a.position.y
            ex2, ey2 = b.position.x, b.position.y

            if self._segments_intersect_strict(x1, y1, x2, y2, ex1, ey1, ex2, ey2):
                # Allow touching host edge exactly at candidate endpoint when
                # endpoint is already connected to host edge endpoints.
                endpoint_touch = self._point_to_segment_distance(x2, y2, ex1, ey1, ex2, ey2) <= 1.0
                if endpoint_touch and self._has_direct_connection(to_node, a) and self._has_direct_connection(to_node, b):
                    continue
                return True

            if self._segments_nearly_parallel_and_overlapping(x1, y1, x2, y2, ex1, ey1, ex2, ey2):
                return True

        return False

    def _safe_add_edge(self, from_node: Node, to_node: Node, num_lanes: int = 2, bidirectional: bool = True):
        """Add edge with geometric overlap guards."""
        if not self.environment:
            return None

        adjusted_to_node, adjust_reason = self._adjust_target_node_with_vertex_checks(from_node, to_node)
        if adjusted_to_node.node_id != to_node.node_id:
            to_node = adjusted_to_node
            if adjust_reason:
                print(f"[城市扩张] 顶点检查命中: {adjust_reason}, 终点调整为 {to_node.node_id}")

        if not self.environment.can_connect_nodes(
            from_node, to_node, max_distance=max(self.max_edge_length * 1.25, 650.0)
        ):
            return None
        if self._would_overlap_existing_roads(from_node, to_node):
            print(f"[城市扩张] 跳过重叠道路: {from_node.node_id} -> {to_node.node_id}")
            return None
        return self.environment.add_edge_dynamically(
            from_node=from_node,
            to_node=to_node,
            num_lanes=num_lanes,
            bidirectional=bidirectional
        )
    
    def _expand_with_growth(self, expansion_size: str = "medium") -> bool:
        """
        使用真正仿 procedural_city_generation 的方式扩展城市路网。
        
        核心机制：
        1. Vertex + neighbours 图结构
        2. Front (生长前沿) 迭代生长
        3. Check 函数处理相交、吸附、创建交叉口
        4. Seed + vertex_queue 支路生成机制
        5. KDTree 空间查询加速
        
        Args:
            expansion_size: 扩展方模 (small/medium/large)
            
        Returns:
            是否成功扩展
        """
        if not self.environment:
            return False
        
        try:
            from city.environment.procedural_roadmap import (
                expand_with_procedural_roadmap,
                ProceduralRoadmapGenerator,
                ProceduralConfig
            )
            
            print(f"\n{'='*60}")
            print(f"[城市扩张] 启动真正 Procedural 扩展 (方模: {expansion_size})")
            print(f"{'='*60}")
            
            # 根据方模选择配置
            configs = {
                "small": {"iterations": 2, "description": "小幅扩展"},
                "medium": {"iterations": 3, "description": "中等扩展"},
                "large": {"iterations": 5, "description": "大幅扩展"}
            }
            config = configs.get(expansion_size, configs["medium"])
            
            # 记录扩展前状态
            nodes_before = len(self.environment.road_network.nodes)
            edges_before = len(self.environment.road_network.edges)
            
            # 执行生长扩展
            num_new = expand_with_procedural_roadmap(
                self.environment,
                num_iterations=config["iterations"]
            )
            
            # 记录扩展结果
            nodes_after = len(self.environment.road_network.nodes)
            edges_after = len(self.environment.road_network.edges)
            
            if num_new > 0:
                self.last_expansion_time = self.environment.current_time
                
                # 记录扩展历史
                expansion_record = {
                    'time': self.environment.current_time,
                    'method': 'procedural_roadmap_v2',
                    'size': expansion_size,
                    'description': config["description"],
                    'nodes_added': num_new,
                    'nodes_before': nodes_before,
                    'nodes_after': nodes_after,
                    'edges_before': edges_before,
                    'edges_after': edges_after
                }
                self.expansion_history.append(expansion_record)
                
                print(f"[城市扩张] 完成! 新增 {num_new} 个节点, "
                      f"{edges_after - edges_before} 条边")
                print(f"  当前路网: {nodes_after} 节点, {edges_after} 边")
                
                # 为新节点添加红绿灯
                new_nodes = list(self.environment.road_network.nodes.values())[-num_new:]
                self._add_traffic_lights_to_new_nodes(new_nodes)
                
                return True
            else:
                print("[城市扩张] 没有生成新节点")
                return False
                
        except Exception as e:
            print(f"[城市扩张] 生长扩展失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _add_traffic_lights_to_new_nodes(self, nodes: list) -> None:
        """为新节点中的交叉口添加红绿灯。"""
        if not self.environment:
            return
        
        from city.environment.road_network import TrafficLight
        from city.agents.traffic_light_agent import TrafficLightAgent
        
        count = 0
        for node in nodes:
            # 如果是交叉口（连接数 >= 3）
            total_connections = len(node.incoming_edges) + len(node.outgoing_edges)
            if total_connections >= 3 and not node.traffic_light:
                node.is_intersection = True
                node.traffic_light = TrafficLight(
                    node, cycle_time=60, green_duration=25, yellow_duration=5
                )
                
                tl_agent = TrafficLightAgent(
                    control_node=node,
                    environment=self.environment,
                    use_llm=self.use_llm,
                    name=f"红绿灯_{node.node_id}",
                    enable_memory=self.use_llm
                )
                tl_agent.activate()
                self.environment.add_agent(tl_agent)
                count += 1
        
        if count > 0:
            print(f"[城市扩张] 为 {count} 个交叉口添加了红绿灯")
    
    def act(self, decision: dict[str, Any] | None) -> bool:
        """
        执行城市扩展。
        
        优先使用生长式扩展（多分支、自然生长），
        回退到传统单节点扩展。
        """
        if not decision or not self.environment:
            return False
        
        action = decision.get('action')
        if action != 'expand_city':
            return False
        
        self.record_action(
            'expand_city',
            {
                'source': 'llm' if decision.get('is_llm') else 'rule',
                'direction': decision.get('expansion_direction', 'unknown'),
            },
            importance=5.0
        )
        
        # 优先使用生长式扩展
        try:
            # 根据城市方模选择扩展大小
            current_nodes = len(self.environment.road_network.nodes)
            if current_nodes < 8:
                expansion_size = "small"
            elif current_nodes < 15:
                expansion_size = "medium"
            else:
                expansion_size = "large"
            
            # 尝试生长式扩展
            success = self._expand_with_growth(expansion_size)
            if success:
                self.record_event(
                    '路网扩展成功',
                    {
                        'mode': 'growth',
                        'expansion_size': expansion_size,
                        'nodes': len(self.environment.road_network.nodes),
                        'edges': len(self.environment.road_network.edges),
                    },
                    importance=7.0
                )
                return True
            
            print("[城市扩张] 生长式扩展未生成节点，回退到传统扩展")
            
        except Exception as e:
            print(f"[城市扩张] 生长式扩展异常: {e}，回退到传统扩展")
        
        # 回退到传统单节点扩展
        success = self._act_traditional(decision)
        if success:
            self.record_event(
                '路网扩展成功',
                {
                    'mode': 'traditional',
                    'direction': decision.get('expansion_direction', 'unknown'),
                    'nodes': len(self.environment.road_network.nodes),
                    'edges': len(self.environment.road_network.edges),
                },
                importance=7.0
            )
        return success
    
    def _create_orthogonal_path(
        self, 
        from_pos: Vector2D, 
        to_pos: Vector2D,
        prefer_horizontal_first: bool = True
    ) -> list[dict[str, float]]:
        """
        创建方正的正交路径（水平+垂直的直角转弯）。
        
        如果直接连接是斜的，添加中间点使其变成直角转弯。
        优先沿途经过功能区域。
        
        Args:
            from_pos: 起点位置
            to_pos: 终点位置
            prefer_horizontal_first: 优先水平方向先走
            
        Returns:
            中间点列表（不包含起点和终点）
        """
        import math
        
        dx = to_pos.x - from_pos.x
        dy = to_pos.y - from_pos.y
        
        # 如果已经是水平或垂直，不需要中间点
        if abs(dx) < 10 or abs(dy) < 10:
            return []
        
        # 计算角度，如果接近45度，需要决定先水平还是先垂直
        angle = math.degrees(math.atan2(abs(dy), abs(dx)))
        
        zones = self._get_zones_for_expansion_planning()
        
        # 两种路径方案
        # 方案1: 先水平后垂直
        path1_corner = Vector2D(to_pos.x, from_pos.y)
        path1_score = self._score_path_through_zones(from_pos, path1_corner, to_pos, zones)
        
        # 方案2: 先垂直后水平
        path2_corner = Vector2D(from_pos.x, to_pos.y)
        path2_score = self._score_path_through_zones(from_pos, path2_corner, to_pos, zones)
        
        # 选择经过更多功能区域的路径
        if path1_score >= path2_score:
            corner = path1_corner
        else:
            corner = path2_corner
        
        # 只有当转角点与起点/终点有足够距离时才添加
        min_leg_length = 30  # 最小路段长度
        
        dist_to_corner = from_pos.distance_to(corner)
        dist_from_corner = corner.distance_to(to_pos)
        
        if dist_to_corner < min_leg_length or dist_from_corner < min_leg_length:
            # 转角太近，使用斜线
            return []
        
        # 将转角点对齐到网格
        corner = self._align_to_grid(corner, grid_size=50.0)
        
        return [{'x': corner.x, 'y': corner.y}]
    
    def _score_path_through_zones(
        self, 
        start: Vector2D, 
        corner: Vector2D, 
        end: Vector2D,
        zones: list
    ) -> float:
        """
        给路径打分，考虑是否经过功能区域。
        
        Returns:
            分数，越高表示经过的功能区域越多/越好
        """
        score = 0.0
        
        # 两段路径
        segments = [
            (start, corner),
            (corner, end)
        ]
        
        for seg_start, seg_end in segments:
            for zone in zones:
                # 检查线段是否经过区域附近
                if self._line_near_zone(
                    seg_start.x, seg_start.y,
                    seg_end.x, seg_end.y,
                    zone
                ):
                    # 根据区域类型给分
                    zone_type_scores = {
                        'RESIDENTIAL': 2.0,
                        'COMMERCIAL': 3.0,
                        'OFFICE': 2.5,
                        'SCHOOL': 1.5,
                        'HOSPITAL': 1.5,
                        'PARK': 1.0,
                        'INDUSTRIAL': 0.5,
                    }
                    score += zone_type_scores.get(zone.zone_type.name, 1.0)
        
        return score
    
    def _line_near_zone(
        self, 
        x1: float, y1: float, 
        x2: float, y2: float,
        zone,
        buffer: float = 50.0
    ) -> bool:
        """检查线段是否在区域附近（有buffer距离内）。"""
        min_x, min_y, max_x, max_y = zone.bounds
        
        # 扩展边界
        min_x -= buffer
        min_y -= buffer
        max_x += buffer
        max_y += buffer
        
        # 检查线段是否与扩展后的边界相交或接近
        # 简化的检查：检查线段的中点是否在扩展边界内
        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2
        
        if min_x <= mid_x <= max_x and min_y <= mid_y <= max_y:
            return True
        
        # 检查线段的两个端点
        points = [(x1, y1), (x2, y2)]
        for px, py in points:
            if min_x <= px <= max_x and min_y <= py <= max_y:
                return True
        
        return False
    
    def _align_to_grid(self, pos: Vector2D, grid_size: float = 50.0) -> Vector2D:
        """
        将位置对齐到网格，使道路更方正。
        
        Args:
            pos: 原始位置
            grid_size: 网格大小（米）
            
        Returns:
            对齐后的位置
        """
        aligned_x = round(pos.x / grid_size) * grid_size
        aligned_y = round(pos.y / grid_size) * grid_size
        
        # 确保对齐后的位置不会与原始位置偏离太远（最大偏离半个网格）
        if abs(aligned_x - pos.x) > grid_size / 2:
            aligned_x = pos.x
        if abs(aligned_y - pos.y) > grid_size / 2:
            aligned_y = pos.y
            
        return Vector2D(aligned_x, aligned_y)
    
    def _act_traditional(self, decision: dict[str, Any] | None) -> bool:
        """传统的单节点扩展方式（作为回退）。"""
        if not decision or not self.environment:
            return False
        
        try:
            # 创建新拌妭点?
            pos_data = decision['new_node_position']
            planned_pos = Vector2D(pos_data['x'], pos_data['y'])
            new_pos = self._adjust_position_if_near_road(planned_pos)
            
            # 将位置对齐到网格，使道路更方正
            new_pos = self._align_to_grid(new_pos, grid_size=50.0)
            print(f"[城市扩张] 新节点位置对齐到网格: ({new_pos.x:.0f}, {new_pos.y:.0f})")
            
            new_node = self.environment.add_node_dynamically(
                position=new_pos,
                name=f"district_{len(self.expansion_history)+1}"
            )
            
            # 连接划板决绛栨寚定氱的节点
            network = self.environment.road_network
            connect_to = decision.get('connect_to', [])
            path_waypoints = decision.get('path_waypoints', {})
            
            print(f"[城市扩张] 新节点 {new_node.node_id} 计划连接: {connect_to}")
            if path_waypoints:
                print(f"[城市扩张] 使用折线路径，路径点: {path_waypoints}")
            
            connections = 0
            connected_nodes = []
            
            # 获取扩最夊姛能藉尯城知敤人庤矾寰勮划?
            zones = self._get_zones_for_expansion_planning()
            
            for nid in connect_to:
                if nid == new_node.node_id:
                    continue
                target_node = network.nodes.get(nid)
                if not target_node:
                    continue
                    
                dist = new_node.position.distance_to(target_node.position)
                print(f"[城市扩张] 尝试连接 {nid}, 距离 {dist:.1f}m")
                
                # 生成方正的正交路径（优先水平+垂直的直角转弯）
                orthogonal_waypoints = self._create_orthogonal_path(
                    new_node.position,
                    target_node.position,
                    prefer_horizontal_first=True
                )
                
                # 检查ョ洿鎺ヨ繛鎺否是否︿细绌胯繃功能区域
                needs_waypoints = False
                waypoints = []
                
                # 优先使用方正路径（如果有的话）
                if orthogonal_waypoints:
                    waypoints = orthogonal_waypoints
                    print(f"[城市扩张] 使用方正正交路径，经过 {len(waypoints)} 个转角点")
                else:
                    # 检查是否需要绕行功能区域
                    for zone in zones:
                        if self._line_intersects_zone(
                            new_node.position.x, new_node.position.y,
                            target_node.position.x, target_node.position.y,
                            zone
                        ):
                            print(f"[城市扩张] 直接连接会穿过区域 {zone.name}，需要绕行")
                            needs_waypoints = True
                            # 计算络曡路緞
                            path = self._find_path_around_zones(new_node, target_node, [zone])
                            if path:
                                waypoints.extend(path)
                            break
                
                # 濡傛灉最夐计算鐨勮矾寰勭偣我栬呭垰计算鐨勭粫琛岃矾寰勶）优跨敤鎶樼嚎
                if (nid in path_waypoints and path_waypoints[nid]) or waypoints:
                    if not waypoints and nid in path_waypoints:
                        waypoints = path_waypoints[nid]
                    
                    print(f"[城市扩张] 使用折线路径连接 {nid}，经过 {len(waypoints)} 个中间点")
                    
                    # 创建鎶樼嚎路緞：避柊节点 -> 涓棿点?-> 鐩标节点
                    current_node = new_node
                    path_success = True
                    
                    for i, wp in enumerate(waypoints):
                        # 创建涓棿节点：堝分扩是鎶樼嚎路緞：?
                        wp_pos = Vector2D(wp['x'], wp['y'])
                        
                        # 检查否是否度否最夎妭点方在过欎釜优嶇疆
                        existing = None
                        for node in network.nodes.values():
                            if node.position.distance_to(wp_pos) < 30:
                                existing = node
                                break
                        
                        if existing:
                            # 优跨敤环版有节点
                            intermediate_node = existing
                            print(f"[城市扩张] 使用现有节点作为中间点: {intermediate_node.node_id}")
                        else:
                            # 创建新扮的涓棿节点：堢敤人庢姌绾胯浆开級
                            intermediate_node = self.environment.add_node_dynamically(
                                position=wp_pos,
                                name=f"corner_{new_node.node_id}_{i}"
                            )
                            print(f"[城市扩张] 创建中间节点: {intermediate_node.node_id}")
                        
                        # 连接当前节点划颁中间磋妭点?
                        edge1 = self._safe_add_edge(
                            from_node=current_node,
                            to_node=intermediate_node,
                            num_lanes=2,
                            bidirectional=True
                        )
                        
                        if edge1:
                            print(f"[城市扩张] 折线连接: {current_node.node_id} -> {intermediate_node.node_id}")
                        else:
                            path_success = False
                            break
                        
                        current_node = intermediate_node
                    
                    # 最否庤繛鎺冷埌鐩标节点
                    if path_success:
                        final_edge = self._safe_add_edge(
                            from_node=current_node,
                            to_node=target_node,
                            num_lanes=2,
                            bidirectional=True
                        )
                        if final_edge:
                            connections += 1
                            connected_nodes.append(nid)
                            print(f"[城市扩张] 折线连接成功: {new_node.node_id} ... -> {nid}")
                else:
                    # 鐩却帴连接：堜不浼氱┛过准尯城燂級
                    edge = self._safe_add_edge(
                        from_node=new_node,
                        to_node=target_node,
                        num_lanes=2,
                        bidirectional=True
                    )
                    if edge:
                        connections += 1
                        connected_nodes.append(nid)
                        print(f"[城市扩张] 成功连接 {nid}")
            
            # 确繚自冲皯2涓繛鎺ワ紙濡傛灉娌℃有超冲连接：中皾误曠洿鎺ヨ繛鎺否要过戠的节点：?
            # 闄愬埗：勤彧连接划扮洿鎺ョ浉閭荤的节点：堢网标奸棿路濊寖鍥村唴：夛）避垮免长胯窛绂诲方掕繛鎺?
            has_detour_path = any(
                nid in path_waypoints and path_waypoints[nid] 
                for nid in connected_nodes
            )
            
            # 计算否堢理鐨勬要最方繛鎺ヨ窛绂伙紙城轰于网戞牸间磋窛：中厑璁稿皯采忎綑采忥級
            max_connection_dist = max(self.max_edge_length * 0.95, 360.0)
            
            if connections < 2 and not has_detour_path:
                distances = [
                    (nid, new_node.position.distance_to(n.position))
                    for nid, n in network.nodes.items()
                    if nid != new_node.node_id 
                    and nid not in connected_nodes
                    and new_node.position.distance_to(n.position) <= max_connection_dist  # 口冭檻过戣窛绂昏妭点?
                ]
                distances.sort(key=lambda x: x[1])
                
                for nid, dist in distances:
                    if connections >= 2:
                        break
                    target_node = network.nodes.get(nid)
                    if target_node:
                        # 口冭檻姝ｄ氦方向鐨勮妭点癸紙X我朰坐标鐩稿悓我栨帴过戯級
                        dx = abs(new_node.position.x - target_node.position.x)
                        dy = abs(new_node.position.y - target_node.position.y)
                        
                        # 蹇部』显人ら偦灞咃紙涓昏显按骞决垨鍨傜洿方向：?
                        is_orthogonal = min(dx, dy) < 50
                        is_near_diagonal = abs(dx - dy) < 80 and max(dx, dy) <= self.max_edge_length
                        
                        if not allow_non_orthogonal and not is_orthogonal and not is_near_diagonal:
                            continue  # 路宠繃密硅绾胯妭点?
                        
                        # 检查ョ洿鎺ヨ繛鎺否是否︿细绌胯繃区域
                        would_intersect = False
                        for zone in zones:
                            if self._line_intersects_zone(
                                new_node.position.x, new_node.position.y,
                                target_node.position.x, target_node.position.y,
                                zone
                            ):
                                would_intersect = True
                                break
                        
                        if would_intersect:
                            continue  # 路宠繃浼氱┛过准尯城知的连接
                        
                        edge = self._safe_add_edge(
                            from_node=new_node,
                            to_node=target_node,
                            num_lanes=2,
                            bidirectional=True
                        )
                        if edge:
                            connections += 1
                            connected_nodes.append(nid)
                            print(f"[城市扩张] 补位连接 {nid} (距离 {dist:.0f}m)")
            
            if connections > 0:
                self.last_expansion_time = self.environment.current_time
                
                # 记录扩展展鍘嗗彶
                expansion_record = {
                    'time': self.environment.current_time,
                    'new_node': new_node.node_id,
                    'position': pos_data,
                    'connections': connections,
                    'connected_to': connected_nodes,
                    'population_before': len(self.environment.vehicles),
                    'decision': decision
                }
                self.expansion_history.append(expansion_record)
                
                # 记录扩展方向历史
                direction = decision.get('expansion_direction')
                if direction:
                    self.recent_expansion_directions.append(direction)
                    if len(self.recent_expansion_directions) > self.direction_window:
                        self.recent_expansion_directions.pop(0)
                
                print(f"[城市扩张] 新增区域 {new_node.node_id}，连接 {connections} 条道路")
                return True
            
            return False
            
        except Exception as e:
            print(f"[城市扩张] 执行失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _get_time_of_day(self) -> str:
        """
        获取当前鏃态。?
        
        模℃嫙涓最?4灏子时鐨勬时娈碉细
        - morning_rush: 鏃╅珮宄?(7-9点?
        - daytime: 鐧藉ぉ (9-17点?
        - evening_rush: 能氶珮宄?(17-19点?
        - night: 最滈棿 (19-7点?
        """
        if not self.environment:
            return 'daytime'
        
        # 灏嗕豢鐪拟时间却槧灏划埌24灏子时划?(姣忎釜浠跨湡鏃冷亣璁句为360绉掞）却?划嗛挓)
        day_seconds = 360
        time_of_day = self.environment.current_time % day_seconds
        hour = (time_of_day / day_seconds) * 24
        
        if 7 <= hour < 9:
            return 'morning_rush'
        elif 9 <= hour < 17:
            return 'daytime'
        elif 17 <= hour < 19:
            return 'evening_rush'
        else:
            return 'night'
    
    def _get_zone_travel_multiplier(self, zone_type_name: str, time_period: str, is_origin: bool) -> float:
        """
        获取区域鍦ㄧ壒定避时娈用的鍑体值嶆暟。?
        
        Args:
            zone_type_name: 区域类型名称
            time_period: 鏃态
            is_origin: 显惁显捣点癸紙True=鍑哄彂：孎alse=划拌揪：?
        
        Returns:
            鍑体值嶆暟：?.0涓哄熀鍑嗭級
        """
        multipliers = {
            'RESIDENTIAL': {
                'morning_rush': {'origin': 2.5, 'destination': 0.3},  # 鏃╅珮宄板ぇ采工出间?
                'daytime': {'origin': 0.8, 'destination': 0.6},
                'evening_rush': {'origin': 0.3, 'destination': 2.5},  # 能氶珮宄板ぇ采工洖定?
                'night': {'origin': 0.2, 'destination': 1.0}
            },
            'COMMERCIAL': {
                'morning_rush': {'origin': 0.3, 'destination': 2.0},  # 鏃╅珮宄板幓商嗕笟鍖?
                'daytime': {'origin': 1.0, 'destination': 1.5},       # 鐧藉ぉ商嗕笟鍖烘椿路?
                'evening_rush': {'origin': 1.5, 'destination': 0.5},
                'night': {'origin': 0.5, 'destination': 0.3}
            },
            'OFFICE': {
                'morning_rush': {'origin': 0.2, 'destination': 2.5},  # 鏃╅珮宄板幓鍔炲叕鍖?
                'daytime': {'origin': 0.8, 'destination': 0.8},
                'evening_rush': {'origin': 2.5, 'destination': 0.2},  # 能氶珮宄扮开鍔炲叕鍖?
                'night': {'origin': 0.1, 'destination': 0.1}
            },
            'INDUSTRIAL': {
                'morning_rush': {'origin': 0.3, 'destination': 2.0},
                'daytime': {'origin': 1.2, 'destination': 1.0},
                'evening_rush': {'origin': 2.0, 'destination': 0.3},
                'night': {'origin': 0.5, 'destination': 0.5}
            },
            'SCHOOL': {
                'morning_rush': {'origin': 0.3, 'destination': 2.0},  # 鏃╀笂涓婂
                'daytime': {'origin': 0.5, 'destination': 0.3},
                'evening_rush': {'origin': 2.0, 'destination': 0.3},  # 涓嬪崍鏀惧
                'night': {'origin': 0.1, 'destination': 0.1}
            },
            'HOSPITAL': {
                'morning_rush': {'origin': 0.8, 'destination': 1.0},
                'daytime': {'origin': 1.0, 'destination': 1.2},
                'evening_rush': {'origin': 1.0, 'destination': 0.8},
                'night': {'origin': 0.5, 'destination': 0.5}
            },
            'PARK': {
                'morning_rush': {'origin': 0.5, 'destination': 0.8},
                'daytime': {'origin': 1.0, 'destination': 1.5},       # 鐧藉ぉ鍘诲叕鍥?
                'evening_rush': {'origin': 1.0, 'destination': 0.5},
                'night': {'origin': 0.1, 'destination': 0.1}
            }
        }
        
        zone_multipliers = multipliers.get(zone_type_name, multipliers['RESIDENTIAL'])
        period_multipliers = zone_multipliers.get(time_period, zone_multipliers['daytime'])
        return period_multipliers['origin'] if is_origin else period_multipliers['destination']
    
    def _get_node_zones_info(self, node) -> list[dict]:
        """获取节点闄勮繎鐨划尯城熶息"""
        nearby_zones = []
        if not self.environment:
            return nearby_zones
        
        # 获取城市规划能体能优撶的区域管理鍣?
        zoning_agent = None
        for agent in self.environment.agents:
            if hasattr(agent, 'zone_manager') and agent.agent_type == AgentType.TRAFFIC_PLANNER:
                zoning_agent = agent
                break
        
        if not zoning_agent:
            # 濡傛灉娌℃有扩惧埌城市规划能体能优擄）返回绌哄垪琛?
            return nearby_zones
        
        zone_manager = zoning_agent.zone_manager
        for zone in zone_manager.zones.values():
            # 计算节点划板尯城知的距离
            dist = node.position.distance_to(zone.center)
            if dist < 250:  # 250类冲唴璁や为显檮过?
                nearby_zones.append({
                    'type': zone.zone_type.name,
                    'population': zone.population,
                    'distance': dist
                })
        
        return nearby_zones
    
    def _get_zoning_agent(self):
        """获取城市规划能体能优撱"""
        if not self.environment:
            return None
        for agent in self.environment.agents.values():
            if hasattr(agent, 'zone_manager') and agent.agent_type == AgentType.TRAFFIC_PLANNER:
                return agent
        return None
    
    def _auto_spawn_vehicles(self) -> int:
        """
        城轰于区域人哄口和屾时娈用壒寰佺敓我愯溅边嗭紙OD密癸級。?
        
        杞﹁辆用拟垚通昏緫：?
        1. 鑰冭檻鏃态鐗方緛：堟棭楂樺嘲。扩櫄楂樺嘲绛夛級
        2. 城轰于区域人哄口和岀被鍨嬭管楃敓我愭环?
        3. 优工畢鍖烘棭涓婄敓我愬出间ㄨ溅边嗭）能氫笂用拟垚鍥炲杞﹁辆
        4. 商嗕笟鍖?鍔炲叕鍖烘有密方应鐨划出琛屾ā开?
        """
        if not self.environment:
            return 0
        
        network = self.environment.road_network
        nodes = list(network.nodes.values())
        
        if len(nodes) < 2:
            return 0
        
        spawned = 0
        stats = self.get_city_stats()
        time_period = self._get_time_of_day()
        
        # 计算城轰于鏃态鐨划熀确用拟垚环?
        base_spawn_rate = {
            'morning_rush': 0.8,    # 鏃╅珮宄扮敓我愮巼楂?
            'daytime': 0.4,
            'evening_rush': 0.8,    # 能氶珮宄扮敓我愮巼楂?
            'night': 0.15
        }.get(time_period, 0.4)
        
        # 标方嵁当前人哄口和中采工决定氱敓我愭暟采?
        if stats['current_population'] < stats['max_capacity']:
            # 计算口敓我愮的杞﹁辆鏁?
            available_slots = stats['max_capacity'] - stats['current_population']
            
            # 城轰于区域计算姣忎釜节点鐨勭敓我愭潈采?
            node_weights = []
            for node in nodes:
                weight = 0
                nearby_zones = self._get_node_zones_info(node)
                
                for zone_info in nearby_zones:
                    # 条冮噸 = 人哄口 * 鏃态值嶆暟 * 距离琛板噺
                    zone_type = zone_info['type']
                    population = zone_info['population']
                    distance = zone_info['distance']
                    
                    # 鏃态值嶆暟：堜。涓体捣点癸級
                    time_multiplier = self._get_zone_travel_multiplier(
                        zone_type, time_period, is_origin=True
                    )
                    
                    # 距离琛板噺：进秺过戝奖鍝嶈秺最э級
                    distance_decay = max(0, 1 - distance / 200)
                    
                    weight += population * time_multiplier * distance_decay
                
                # 濡傛灉娌℃有闄勮繎区域：岀粰人堝熀确条冮噸
                if weight == 0:
                    weight = 10
                
                node_weights.append((node, weight))
            
            # 鎸夋潈采嶉夋嫨璧风偣
            total_weight = sum(w for _, w in node_weights)
            if total_weight == 0:
                return spawned
            
            # 用拟垚杞﹁辆鏁板熀人庢时娈靛和口敤容量
            num_to_spawn = min(
                int(available_slots * base_spawn_rate) + 1,
                available_slots,
                5  # 姣子最大氱敓我?边?
            )
            
            for _ in range(num_to_spawn):
                # 鎸夋潈采嶉夋嫨璧风偣
                r = random.uniform(0, total_weight)
                cumsum = 0
                origin = nodes[0]
                for node, weight in node_weights:
                    cumsum += weight
                    if cumsum >= r:
                        origin = node
                        break
                
                # 选择络堢偣 - 城轰于络堢偣鐨划惛开曟潈采?
                dest_candidates = []
                for node in nodes:
                    if node.node_id == origin.node_id:
                        continue
                    
                    # 计算络堢偣否稿紩鍔?
                    attraction = 0
                    nearby_zones = self._get_node_zones_info(node)
                    
                    for zone_info in nearby_zones:
                        zone_type = zone_info['type']
                        population = zone_info['population']
                        distance = zone_info['distance']
                        
                        # 鏃态值嶆暟：堜。涓虹粓点癸級
                        time_multiplier = self._get_zone_travel_multiplier(
                            zone_type, time_period, is_origin=False
                        )
                        
                        distance_decay = max(0, 1 - distance / 200)
                        attraction += population * time_multiplier * distance_decay
                    
                    if attraction > 0:
                        dest_candidates.append((node, attraction))
                
                if dest_candidates:
                    # 鎸夊惛开曞姏选择络堢偣
                    total_attraction = sum(a for _, a in dest_candidates)
                    r = random.uniform(0, total_attraction)
                    cumsum = 0
                    destination = dest_candidates[0][0]
                    for node, attraction in dest_candidates:
                        cumsum += attraction
                        if cumsum >= r:
                            destination = node
                            break
                else:
                    # 闅子満选择
                    destination = random.choice([n for n in nodes if n.node_id != origin.node_id])
                
                # 用拟垚杞﹁辆
                vehicle = self.environment.spawn_vehicle(
                    start_node=origin,
                    end_node=destination,
                    vehicle_type=VehicleType.CAR
                )
                
                if vehicle:
                    vehicle_config = getattr(self.environment, 'agent_configs', {})
                    vehicle.use_llm = vehicle_config.get('vehicle', True)
                    spawned += 1
                    self.total_spawns += 1
        
        if spawned > 0:
            print(f"[车辆生成] 时段: {time_period}, 生成 {spawned} 辆车, 当前人口: {stats['current_population'] + spawned}/{stats['max_capacity']}")
        
        return spawned
    
    def _optimize_road_network(self) -> bool:
        """
        优先对已有主干路做车道升级。

        当前策略：
        1. 对每条物理道路汇总双向车辆数
        2. 优先升级车辆数较多、且仍是 2 车道的道路
        3. 一次只把一条物理道路提升到 4 车道
        """
        if not self.environment:
            return False

        candidates: list[tuple[float, Edge, int]] = []
        seen_pairs: set[tuple[str, str]] = set()
        for edge in self.environment.road_network.edges.values():
            pair_key = tuple(sorted((edge.from_node.node_id, edge.to_node.node_id)))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            reverse_edge = self.environment.road_network.find_edge(edge.to_node, edge.from_node)
            current_lanes = max(len(edge.lanes), len(reverse_edge.lanes) if reverse_edge else 0)
            if current_lanes >= 4:
                continue

            vehicle_count = sum(len(lane.vehicles) for lane in edge.lanes)
            if reverse_edge:
                vehicle_count += sum(len(lane.vehicles) for lane in reverse_edge.lanes)

            if vehicle_count <= 0:
                continue

            score = vehicle_count * 1000 + edge.length
            candidates.append((score, edge, current_lanes))

        if not candidates:
            return False

        candidates.sort(key=lambda item: item[0], reverse=True)
        _, target_edge, current_lanes = candidates[0]
        if current_lanes >= 4:
            return False

        upgraded = self.environment.upgrade_edge_lanes_dynamically(
            from_node=target_edge.from_node,
            to_node=target_edge.to_node,
            new_num_lanes=4,
            bidirectional=True
        )
        if upgraded:
            print(
                f"[路网优化] 主干路拓宽 {target_edge.from_node.node_id} <-> "
                f"{target_edge.to_node.node_id}: {current_lanes} -> 4 车道"
            )
        return upgraded
    
    def _can_remove_without_disconnecting(self, from_node, to_node, edge_id_to_skip) -> bool:
        """检查冷垹闄よ竟否庢是否︿细新紑网络。"""
        if not self.environment:
            return False
        
        network = self.environment.road_network
        
        # 优跨敤BFS检查与粠from_node显惁过樿能划拌揪to_node
        visited = set()
        queue = [from_node.node_id]
        visited.add(from_node.node_id)
        
        while queue:
            current_id = queue.pop(0)
            if current_id == to_node.node_id:
                return True  # 过樻有鍏朵粬路緞
            
            current = network.nodes.get(current_id)
            if not current:
                continue
            
            # 检查否墍最夐偦鎺ヨ竟：进烦过囪删除鐨勮竟：?
            for edge in list(current.outgoing_edges) + list(current.incoming_edges):
                if edge.edge_id == edge_id_to_skip:
                    continue
                neighbor = edge.to_node if edge.from_node == current else edge.from_node
                if neighbor.node_id not in visited:
                    visited.add(neighbor.node_id)
                    queue.append(neighbor.node_id)
        
        return False  # 娌℃有鍏朵粬路緞：优不能藉垹闄?
    
    def _are_edges_parallel_and_close(self, edge1, edge2, angle_threshold=15, dist_threshold=80) -> bool:
        """检查与袱条¤竟显惁过们技骞宠涓旇窛绂诲緢过戙"""
        # 计算边?鐨勬式否戝悜采?
        dx1 = edge1.to_node.position.x - edge1.from_node.position.x
        dy1 = edge1.to_node.position.y - edge1.from_node.position.y
        len1 = math.sqrt(dx1**2 + dy1**2)
        if len1 < 1:
            return False
        
        # 计算边?鐨勬式否戝悜采?
        dx2 = edge2.to_node.position.x - edge2.from_node.position.x
        dy2 = edge2.to_node.position.y - edge2.from_node.position.y
        len2 = math.sqrt(dx2**2 + dy2**2)
        if len2 < 1:
            return False
        
        # 检查否是否度钩琛岋紙点界Н鎺ヨ繎1我?1：?
        cos_angle = abs((dx1*dx2 + dy1*dy2) / (len1 * len2))
        if cos_angle < 0.95:  # 方掑害最т于绾?8密?
            return False
        
        # 检查ヨ窛绂伙紙口栬竟1鐨勪中点方埌边?鐨勮窛绂伙級
        mid1_x = (edge1.from_node.position.x + edge1.to_node.position.x) / 2
        mid1_y = (edge1.from_node.position.y + edge1.to_node.position.y) / 2
        
        # 计算涓偣划拌竟2鐨勮窛绂?
        dist = self._point_to_segment_distance(
            mid1_x, mid1_y,
            edge2.from_node.position.x, edge2.from_node.position.y,
            edge2.to_node.position.x, edge2.to_node.position.y
        )
        
        return dist < dist_threshold
    
    def _point_to_segment_distance(self, px, py, x1, y1, x2, y2) -> float:
        """计算点方埌绾条鐨勮窛绂汇"""
        dx = x2 - x1
        dy = y2 - y1
        
        if dx == 0 and dy == 0:
            return math.sqrt((px - x1)**2 + (py - y1)**2)
        
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        
        return math.sqrt((px - proj_x)**2 + (py - proj_y)**2)
    
    def update(self, dt: float) -> None:
        """更新规划能体能优撶姸性併"""
        if not self.environment:
            return
            
        current_time = self.environment.current_time
        
        # 定避湡自动用拟垚杞﹁辆
        self.auto_spawn_timer += dt
        if self.auto_spawn_timer >= self.spawn_interval:
            self.auto_spawn_timer = 0.0
            spawned = self._auto_spawn_vehicles()
            if spawned > 0:
                stats = self.get_city_stats()
                print(f"[人口增长] 新增 {spawned} 名通勤者，"
                      f"当前人哄口: {stats['current_population']}/{stats['max_capacity']}")
        
        # 定避湡决策略显惁需要扩展开?
        check_interval = 5
        if int(current_time) % check_interval == 0 and int(current_time) > 0:
            if not hasattr(self, '_last_expansion_check') or self._last_expansion_check != int(current_time):
                self._last_expansion_check = int(current_time)
                stats = self.get_city_stats()
                
                # 检查车辆人口密度
                vehicle_density_trigger = stats['density'] >= self.expansion_threshold
                
                # 检查区域人口压力
                zone_population_trigger = self._check_zone_population_pressure()
                
                if vehicle_density_trigger or zone_population_trigger:
                    reason = "车辆密度高" if vehicle_density_trigger else "区域人口压力大"
                    print(f"[路网规划] 触发扩展: {reason}")
                    decision = self.decide()
                    if decision:
                        success = self.act(decision)
                        if success:
                            print(f"[路网规划] 城市路网已扩展，当前节点数: "
                                  f"{len(self.environment.road_network.nodes)}")
        
        # 定避湡优化避撹矾网络：堝垹闄や綆鏁优于路級
        optimize_interval = 15  # 姣?5绉掓查与一娆?
        if int(current_time) % optimize_interval == 0 and int(current_time) > 5:
            if not hasattr(self, '_last_optimize_check') or self._last_optimize_check != int(current_time):
                self._last_optimize_check = int(current_time)
                optimized = self._optimize_road_network()
                if optimized:
                    print(f"[路网优化] 已优化道路网络，当前边数: "
                          f"{len(self.environment.road_network.edges)}")
    
    def _check_zone_population_pressure(self) -> bool:
        """
        检查区域人口压力，如果区域人口接近容量上限则触发道路扩展。
        
        Returns:
            如果区域人口压力超过阈值则返回True
        """
        zoning_agent = self._get_zoning_agent()
        if not zoning_agent:
            return False
        
        zm = zoning_agent.zone_manager
        total_pop = zm.get_total_population()
        
        # 计算总容量
        total_capacity = sum(
            zone.max_population 
            for zone in zm.zones.values()
        )
        
        if total_capacity == 0:
            return False
        
        # 人口使用率
        utilization = total_pop / total_capacity
        
        # 如果区域人口使用率超过75%，触发道路扩展
        if utilization > 0.75:
            print(f"[路网规划] 区域人口压力高: {utilization*100:.1f}% ({total_pop}/{total_capacity})，需要扩展道路")
            return True
        
        return False
    
    def get_status(self) -> dict[str, Any]:
        """获取规划能体能优撶姸性併"""
        time_period = self._get_time_of_day()
        
        # 获取区域统计
        zone_stats = {}
        zoning_agent = self._get_zoning_agent()
        if zoning_agent:
            zm = zoning_agent.zone_manager
            total_pop = zm.get_total_population()
            total_capacity = sum(zone.max_population for zone in zm.zones.values())
            population_pressure = total_pop / total_capacity if total_capacity > 0 else 0
            
            zone_stats = {
                'total_zones': len(zm.zones),
                'total_population': total_pop,
                'total_capacity': total_capacity,
                'population_pressure': round(population_pressure, 2),
                'by_type': {}
            }
            from city.urban_planning.zone import ZoneType
            for zt in ZoneType:
                count = len(zm.get_zones_by_type(zt))
                if count > 0:
                    zone_stats['by_type'][zt.name] = count
        
        return {
            'agent_id': self.agent_id,
            'agent_type': 'PopulationCityPlanner',
            'city_stats': self.get_city_stats(),
            'expansion_count': len(self.expansion_history),
            'total_spawns': self.total_spawns,
            'last_expansion_time': self.last_expansion_time,
            'population_per_node': self.population_per_node,
            'expansion_threshold': self.expansion_threshold,
            'last_decision': self.last_decision,
            'city_stage': self._get_city_stage(),
            'time_of_day': time_period,
            'time_display': {
                'morning_rush': '早高峰 (7-9点)',
                'daytime': '白天 (9-17点)',
                'evening_rush': '晚高峰 (17-19点)',
                'night': '夜间 (19-7点)'
            }.get(time_period, time_period),
            'zone_stats': zone_stats
        }
    
    def _get_city_stage(self) -> str:
        """标方嵁节点数量判断城市口戝展闃态。"""
        if not self.environment:
            return 'initial'
        node_count = len(self.environment.road_network.nodes)
        if node_count >= self.stage_thresholds['mature']:
            return 'mature'
        elif node_count >= self.stage_thresholds['developing']:
            return 'developing'
        return 'initial'


# 淇濈暀鏃х被否尖互渚垮吋定?
PlanningAgent = PopulationCityPlanner



