"""
城市规划智能体 (Zoning Agent) - 独立版本

基于现实城市规划原则的功能区域规划智能体，与路网规划智能体协同工作。
负责规划住宅、商业、医院、学校、公园等功能区域。
"""

from __future__ import annotations

import json
import math
import random
from typing import TYPE_CHECKING, Any

from city.agents.base import AgentType, BaseAgent
from city.urban_planning.zone import Zone, ZoneType, ZoneManager
from city.urban_planning.realistic_zoning import RealisticZoningPlanner, ZoningConstraints
from city.utils.vector import Vector2D

if TYPE_CHECKING:
    from city.simulation.environment import SimulationEnvironment


class ZoningAgent(BaseAgent):
    """
    城市规划智能体（独立版本）。
    
    与路网规划智能体协同工作，基于路网状态规划功能区域。
    采用现实城市规划原则：
    - 服务半径约束
    - 区域兼容性
    - 人口密度模型
    - LLM辅助决策
    
    Attributes:
        zone_manager: 功能区域管理器
        zoning_planner: 现实城市规划器
        planning_interval: 规划间隔（秒）
        max_zones: 最大区域数量
    """
    
    def __init__(
        self,
        environment: SimulationEnvironment | None = None,
        use_llm: bool = True,
        planning_interval: float = 15.0,  # 规划间隔
        max_zones: int = 30,
        min_zone_size: float = 60.0,
        max_zone_size: float = 150.0,
        buffer_distance: float = 20.0,
        enable_memory: bool = True
    ):
        super().__init__(AgentType.TRAFFIC_PLANNER, environment, use_llm, enable_memory=enable_memory, memory_capacity=50)
        
        self.planning_interval = planning_interval
        self.max_zones = max_zones
        self.min_zone_size = min_zone_size
        self.max_zone_size = max_zone_size
        self.buffer_distance = buffer_distance
        
        # 状态
        self.last_planning_time = 0.0
        self.planning_history: list[dict[str, Any]] = []
        self.last_decision: dict[str, Any] | None = None
        
        # 缓存批量决策结果，避免短时间内重复请求LLM
        self._cached_batch_count: int | None = None
        self._batch_count_cache_time: float = 0.0
        
        # 区域管理
        self.zone_manager = ZoneManager()
        
        # 现实城市规划器
        self.zoning_planner = RealisticZoningPlanner(
            zone_manager=self.zone_manager,
            environment=environment,
            use_llm=use_llm,
            constraints=ZoningConstraints()
        )
        
        # 统计
        self.total_zones_planned = 0
        self.llm_decision_archive: list[dict[str, Any]] = []
    
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
        """归档区域规划相关的大模型决策文本。"""
        timestamp = self.environment.current_time if self.environment else 0.0
        record = {
            "id": f"{self.agent_id}_{category}_{int(timestamp * 1000)}_{len(self.llm_decision_archive) + 1}",
            "timestamp": timestamp,
            "agent_id": self.agent_id,
            "agent_type": "zoning",
            "category": category,
            "summary": summary or "区域规划决策",
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
    
    def perceive(self) -> dict[str, Any]:
        """感知城市状态。"""
        perception = {
            'current_time': self.environment.current_time if self.environment else 0,
            'total_zones': len(self.zone_manager.zones),
            'zones_by_type': {},
            'network_info': self._get_network_info(),
            'population_stats': self._get_population_stats(),
            'can_add_more': len(self.zone_manager.zones) < self.max_zones
        }
        
        # 统计各类型区域
        for zone_type in ZoneType:
            zones = self.zone_manager.get_zones_by_type(zone_type)
            if zones:
                perception['zones_by_type'][zone_type.name] = {
                    'count': len(zones),
                    'total_population': sum(z.population for z in zones)
                }
        
        return perception
    
    def _get_network_info(self) -> dict[str, Any]:
        """获取道路网络信息。"""
        if not self.environment:
            return {'nodes': 0, 'bounds': None}
        
        network = self.environment.road_network
        nodes = list(network.nodes.values())
        
        if not nodes:
            return {'nodes': 0, 'bounds': None}
        
        positions = [n.position for n in nodes]
        min_x = min(p.x for p in positions)
        max_x = max(p.x for p in positions)
        min_y = min(p.y for p in positions)
        max_y = max(p.y for p in positions)
        
        return {
            'nodes': len(nodes),
            'bounds': {'min_x': min_x, 'max_x': max_x, 'min_y': min_y, 'max_y': max_y},
            'center': {'x': (min_x + max_x) / 2, 'y': (min_y + max_y) / 2}
        }
    
    def _get_population_stats(self) -> dict[str, Any]:
        """获取人口统计。"""
        total_pop = self.zone_manager.get_total_population()
        
        return {
            'total_population': total_pop,
            'max_capacity': sum(z.max_population for z in self.zone_manager.zones.values()),
            'zone_count': len(self.zone_manager.zones)
        }
    
    def _determine_zone_batch_count(self) -> int:
        """决定本轮需要新增多少个区域。
        
        使用缓存机制避免短时间内重复请求LLM。
        """
        if not self.environment:
            return 0

        remaining_capacity = max(0, self.max_zones - len(self.zone_manager.zones))
        if remaining_capacity <= 0:
            return 0
        
        # 检查缓存：如果在 planning_interval 内已经决策过，使用缓存结果
        current_time = self.environment.current_time
        if (self._cached_batch_count is not None and 
            current_time - self._batch_count_cache_time < self.planning_interval):
            return max(1, min(remaining_capacity, self._cached_batch_count))

        if self.use_llm:
            llm_count = self._llm_determine_zone_batch_count()
            if llm_count is not None:
                self._cached_batch_count = llm_count
                self._batch_count_cache_time = current_time
                return max(1, min(remaining_capacity, llm_count))

        count = max(1, min(remaining_capacity, self._rule_determine_zone_batch_count()))
        self._cached_batch_count = count
        self._batch_count_cache_time = current_time
        return count

    def _llm_determine_zone_batch_count(self) -> int | None:
        """使用大模型根据人口与路网状态决定本轮新增区域数。"""
        try:
            network_info = self._get_network_info()
            population_stats = self._get_population_stats()
            zone_stats = self.zone_manager.get_statistics()
            planning_agent = self._get_road_planning_agent()
            expansion_count = len(getattr(planning_agent, 'expansion_history', [])) if planning_agent else 0

            prompt = f"""你是城市规划总控，需要决定这一轮应该新增多少个功能区域。

当前状态：
- 道路节点数: {network_info.get('nodes', 0)}
- 道路边数: {network_info.get('edges', 0)}
- 当前功能区数量: {zone_stats.get('total_zones', 0)}
- 当前总人口: {population_stats.get('total_population', 0)}
- 当前总容量: {population_stats.get('max_capacity', 0)}
- 路网扩展次数: {expansion_count}
- 各类功能区统计: {json.dumps(zone_stats.get('by_type', {}), ensure_ascii=False)}

决策原则：
1. 区域数量必须服从人口规模与道路承载能力，不能盲目增加。
2. 若道路刚扩展且人口在增长，可以一轮增加多个区域。
3. 若道路不足、人口低、现有区域已经较多，则应保守。
4. 输出的 count 必须在 1 到 4 之间。

只输出 JSON：
{{
  "count": 1-4,
  "reason": "简短说明"
}}"""

            llm_manager = self._get_llm_manager()
            if not llm_manager:
                return None

            response = llm_manager.request_sync_decision(prompt, timeout=10.0)
            if not response:
                return None

            start = response.find('{')
            end = response.rfind('}')
            if start == -1 or end == -1:
                return None

            result = json.loads(response[start:end+1])
            return int(result.get('count', 1))
        except Exception as e:
            print(f"[ZoningAgent] LLM区域数量决策失败: {e}")
            return None

    def _rule_determine_zone_batch_count(self) -> int:
        """规则回退：根据人口、路网与现有区域缺口决定本轮新增数量。"""
        network_info = self._get_network_info()
        population_stats = self._get_population_stats()
        zone_count = len(self.zone_manager.zones)
        nodes = network_info.get('nodes', 0)
        edges = network_info.get('edges', 0)
        total_population = population_stats.get('total_population', 0)

        score = 0
        if nodes >= 12:
            score += 1
        if edges >= 24:
            score += 1
        if total_population >= 300:
            score += 1
        if total_population >= 800:
            score += 1
        if zone_count < max(4, nodes // 3):
            score += 1

        if score >= 4:
            return 4
        if score >= 3:
            return 3
        if score >= 2:
            return 2
        return 1

    def decide(self) -> dict[str, Any] | None:
        """
        城市规划决策 - LLM先选位置，再定功能。
        
        流程：
        1. 获取当前城市状态
        2. 使用LLM选择沿道路的位置
        3. 使用LLM决定该位置最适合的功能类型
        4. 创建区域
        
        注意：此方法在BaseAgent.step()中每步都被调用，
        因此需要自行检查planning_interval避免频繁请求LLM。
        """
        # 检查规划间隔，避免频繁请求LLM
        if not self.environment:
            return None
        current_time = self.environment.current_time
        if current_time - self.last_planning_time < self.planning_interval:
            return None
        
        # 检查是否满足规划条件
        network_info = self._get_network_info()
        perception = self.perceive()
        self.record_perception(perception, importance=3.0)
        if self.has_memory():
            self.get_memory().set_working_memory('latest_zoning_state', {
                'total_zones': perception.get('total_zones', 0),
                'can_add_more': perception.get('can_add_more', False),
            })
        if network_info['nodes'] < 4:
            return None
        
        # 检查是否已达最大区域数
        if len(self.zone_manager.zones) >= self.max_zones:
            return None
        
        # 获取道路边缘位置候选点
        road_side_locations = self._get_road_side_locations()
        if not road_side_locations:
            return None
        
        # 使用LLM选择最佳位置和功能类型
        if self.use_llm:
            decision = self._llm_select_location_and_type(road_side_locations)
            if decision:
                self.record_decision(
                    {
                        'action': decision.get('action', 'create_zone'),
                        'zone_type': decision.get('zone_type').name if decision.get('zone_type') else 'UNKNOWN',
                        'source': 'llm',
                    },
                    {'reason': decision.get('reason', '')},
                    importance=6.0
                )
                return decision
        
        # 回退到规则-based选址
        decision = self._rule_select_location_and_type(road_side_locations)
        if decision:
            self.record_decision(
                {
                    'action': decision.get('action', 'create_zone'),
                    'zone_type': decision.get('zone_type').name if decision.get('zone_type') else 'UNKNOWN',
                    'source': 'rule',
                },
                {'reason': decision.get('reason', '')},
                importance=5.0
            )
        return decision
    
    def _get_road_side_locations(self) -> list[dict]:
        """获取道路边缘的候选位置（沿道路布置）。"""
        if not self.environment:
            return []
        
        network = self.environment.road_network
        nodes = list(network.nodes.values())
        
        if len(nodes) < 2:
            return []
        
        locations = []
        road_width = 20  # 道路半宽
        
        # 收集所有道路边的信息
        for edge in network.edges.values():
            from_node = edge.from_node
            to_node = edge.to_node
            
            # 计算道路方向和垂直方向
            dx = to_node.position.x - from_node.position.x
            dy = to_node.position.y - from_node.position.y
            length = math.sqrt(dx*dx + dy*dy)
            
            if length < 1:
                continue
            
            # 垂直方向（归一化）
            perp_x = -dy / length
            perp_y = dx / length
            
            # 在道路两侧生成候选位置 - 增加距离避免重叠
            for offset in [road_width + 60, -(road_width + 60)]:  # 两侧，距离道路60米（增加安全距离）
                # 中点
                mid_x = (from_node.position.x + to_node.position.x) / 2
                mid_y = (from_node.position.y + to_node.position.y) / 2
                
                # 垂直偏移
                loc_x = mid_x + perp_x * offset
                loc_y = mid_y + perp_y * offset
                
                # 确保不与其他区域重叠
                too_close = False
                for zone in self.zone_manager.zones.values():
                    dist = math.sqrt((loc_x - zone.center.x)**2 + (loc_y - zone.center.y)**2)
                    if dist < 150:  # 增加区域间隔到150米
                        too_close = True
                        break
                
                if not too_close:
                    locations.append({
                        'x': loc_x,
                        'y': loc_y,
                        'edge_id': edge.edge_id,
                        'from_node': from_node.node_id,
                        'to_node': to_node.node_id,
                        'side': 'left' if offset > 0 else 'right',
                        'road_orientation': 'horizontal' if abs(dx) > abs(dy) else 'vertical'
                    })
        
        # 去重并限制数量
        seen = set()
        unique_locations = []
        for loc in locations:
            key = (round(loc['x'], -1), round(loc['y'], -1))  # 精确到10米
            if key not in seen:
                seen.add(key)
                unique_locations.append(loc)
        
        return unique_locations[:20]  # 最多20个候选
    
    def _llm_select_location_and_type(self, locations: list[dict]) -> dict[str, Any] | None:
        """使用LLM选择位置和功能类型。"""
        try:
            # 准备城市状态信息
            network_info = self._get_network_info()
            total_pop = self.zone_manager.get_total_population()
            
            # 现有区域统计
            zone_stats = {}
            for zt in ZoneType:
                count = len(self.zone_manager.get_zones_by_type(zt))
                if count > 0:
                    zone_stats[zt.name] = count
            
            # 构建提示
            prompt = f"""你是一位城市规划专家。请为城市选择一个新功能区域的位置和类型。

## 当前城市状态
- 道路节点数: {network_info['nodes']}
- 当前总人口: {total_pop}
- 已有区域: {zone_stats}

## 候选位置（沿道路布置）
{json.dumps(locations[:10], ensure_ascii=False, indent=2)}

## 规划原则
1. **住宅区**: 优先布置在交通便利的道路旁，服务人口
2. **商业区**: 优先布置在交叉口附近或主干道旁，人流量大
3. **学校**: 靠近住宅区，方便学生上学
4. **医院**: 交通便利，服务范围广
5. **公园**: 靠近住宅区，提供休闲空间
6. **工业区**: 可以布置在相对边缘的位置

## 输出格式
请返回JSON格式决策:
{{
    "selected_index": 候选位置索引(0-9),
    "zone_type": "RESIDENTIAL/COMMERCIAL/SCHOOL/HOSPITAL/PARK/INDUSTRIAL/OFFICE",
    "reason": "选择理由",
    "confidence": 置信度(0-1)
}}
"""
            
            llm_manager = self._get_llm_manager()
            if llm_manager:
                response = llm_manager.request_sync_decision(prompt, timeout=10.0)
                if response:
                    return self._parse_llm_location_response(response, locations)
        except Exception as e:
            print(f"[ZoningAgent] LLM选址失败: {e}")
        
        return None
    
    def _parse_llm_location_response(self, response: str, locations: list[dict]) -> dict[str, Any] | None:
        """解析LLM的位置选择响应。"""
        try:
            start = response.find('{')
            end = response.rfind('}')
            if start == -1 or end == -1:
                return None
            
            result = json.loads(response[start:end+1])
            
            index = result.get('selected_index', 0)
            if index < 0 or index >= len(locations):
                index = 0
            
            selected = locations[index]
            zone_type_name = result.get('zone_type', 'RESIDENTIAL')
            
            try:
                zone_type = ZoneType[zone_type_name]
            except KeyError:
                zone_type = ZoneType.RESIDENTIAL
            
            # 根据道路方向确定区域尺寸
            if selected['road_orientation'] == 'horizontal':
                width = random.uniform(80, 150)
                height = random.uniform(60, 100)
            else:
                width = random.uniform(60, 100)
                height = random.uniform(80, 150)
            
            return {
                'action': 'create_zone',
                'zone_type': zone_type,
                'center': Vector2D(selected['x'], selected['y']),
                'width': width,
                'height': height,
                'name': f"{zone_type.display_name}_{len(self.zone_manager.zones) + 1}",
                'reason': result.get('reason', 'LLM规划'),
                'priority': 'high',
                'confidence': result.get('confidence', 0.8),
                'is_llm': True,
                'road_side': selected['side'],
                'edge_id': selected['edge_id']
            }
            
        except Exception as e:
            print(f"[ZoningAgent] 解析LLM响应失败: {e}")
            return None
    
    def _rule_select_location_and_type(self, locations: list[dict]) -> dict[str, Any] | None:
        """使用规则选择位置和功能类型。"""
        if not locations:
            return None
        
        # 分析需求
        needs = self._analyze_zoning_needs()
        if not needs:
            return None
        
        # 选择最高优先级的需求
        priority_order = ['high', 'medium', 'low']
        selected_type = None
        selected_need = None
        
        for priority in priority_order:
            for type_name, need in needs.items():
                if need['priority'] == priority:
                    selected_type = type_name
                    selected_need = need
                    break
            if selected_type:
                break
        
        if not selected_type:
            return None
        
        try:
            zone_type = ZoneType[selected_type]
        except KeyError:
            return None
        
        # 随机选择一个位置
        selected = random.choice(locations)
        
        # 根据道路方向确定区域尺寸
        if selected['road_orientation'] == 'horizontal':
            width = random.uniform(80, 150)
            height = random.uniform(60, 100)
        else:
            width = random.uniform(60, 100)
            height = random.uniform(80, 150)
        
        return {
            'action': 'create_zone',
            'zone_type': zone_type,
            'center': Vector2D(selected['x'], selected['y']),
            'width': width,
            'height': height,
            'name': f"{zone_type.display_name}_{len(self.zone_manager.zones) + 1}",
            'reason': selected_need.get('reason', '规则规划'),
            'priority': selected_need.get('priority', 'medium'),
            'is_llm': False,
            'road_side': selected['side'],
            'edge_id': selected['edge_id']
        }
    
    def _get_llm_manager(self):
        """获取LLM管理器。"""
        try:
            from city.llm.llm_manager import get_llm_manager
            return get_llm_manager()
        except:
            return None
    
    def _analyze_zoning_needs(self) -> dict[str, Any]:
        """分析功能区域规划需求 - 平衡多样化发展。"""
        needs = {}
        
        total_pop = self.zone_manager.get_total_population()
        network_info = self._get_network_info()
        node_count = network_info.get('nodes', 0)
        total_zones = len(self.zone_manager.zones)
        
        # 计算各类区域数量
        residential = len(self.zone_manager.get_zones_by_type(ZoneType.RESIDENTIAL))
        commercial = len(self.zone_manager.get_zones_by_type(ZoneType.COMMERCIAL))
        schools = len(self.zone_manager.get_zones_by_type(ZoneType.SCHOOL))
        hospitals = len(self.zone_manager.get_zones_by_type(ZoneType.HOSPITAL))
        parks = len(self.zone_manager.get_zones_by_type(ZoneType.PARK))
        offices = len(self.zone_manager.get_zones_by_type(ZoneType.OFFICE))
        industrial = len(self.zone_manager.get_zones_by_type(ZoneType.INDUSTRIAL))
        
        # 如果没有区域，第一个建住宅
        if total_zones == 0:
            needs['RESIDENTIAL'] = {
                'current': 0, 'needed': 1, 'priority': 'high',
                'reason': '首个住宅区，奠定基础'
            }
            return needs
        
        # 平衡发展策略：根据当前比例决定下一步建什么
        # 目标比例：住宅40%, 商业15%, 办公10%, 工业5%, 学校10%, 医院5%, 公园15%
        target_ratios = {
            'RESIDENTIAL': 0.40,
            'COMMERCIAL': 0.15,
            'OFFICE': 0.10,
            'INDUSTRIAL': 0.05,
            'SCHOOL': 0.10,
            'HOSPITAL': 0.05,
            'PARK': 0.15
        }
        
        current_counts = {
            'RESIDENTIAL': residential,
            'COMMERCIAL': commercial,
            'OFFICE': offices,
            'INDUSTRIAL': industrial,
            'SCHOOL': schools,
            'HOSPITAL': hospitals,
            'PARK': parks
        }
        
        # 计算缺口最大的类型
        max_gap = 0
        needed_type = None
        
        for zone_type, target_ratio in target_ratios.items():
            # 计算目标数量
            target_count = max(1, int(total_zones * target_ratio))
            current_count = current_counts[zone_type]
            
            # 特殊规则
            if zone_type == 'INDUSTRIAL' and node_count < 9:
                continue  # 工业区需要城市成熟
            if zone_type == 'OFFICE' and node_count < 6:
                continue  # 办公区需要一定规模
            if zone_type == 'HOSPITAL' and residential < 3:
                continue  # 医院需要足够人口
            if zone_type == 'SCHOOL' and residential < 2:
                continue  # 学校需要住宅区
            
            gap = target_count - current_count
            if gap > max_gap:
                max_gap = gap
                needed_type = zone_type
        
        # 如果有明显缺口，优先补充
        if max_gap >= 1 and needed_type:
            reasons = {
                'RESIDENTIAL': '增加居住容量',
                'COMMERCIAL': '完善商业配套',
                'OFFICE': '提供就业机会',
                'INDUSTRIAL': '发展工业功能',
                'SCHOOL': '教育设施配套',
                'HOSPITAL': '医疗服务配套',
                'PARK': '增加绿地空间'
            }
            needs[needed_type] = {
                'current': current_counts[needed_type],
                'needed': current_counts[needed_type] + 1,
                'priority': 'high',
                'reason': reasons.get(needed_type, '平衡发展')
            }
        else:
            # 比例平衡，按需求新增
            if residential < max(2, node_count // 3):
                needs['RESIDENTIAL'] = {
                    'current': residential,
                    'needed': residential + 1,
                    'priority': 'medium',
                    'reason': '扩展居住空间'
                }
            elif commercial < max(1, residential // 4):
                needs['COMMERCIAL'] = {
                    'current': commercial,
                    'needed': commercial + 1,
                    'priority': 'medium',
                    'reason': '增加商业服务'
                }
            elif parks < residential // 2:
                needs['PARK'] = {
                    'current': parks,
                    'needed': parks + 1,
                    'priority': 'medium',
                    'reason': '增加绿地公园'
                }
        
        return needs

    def _get_road_planning_agent(self):
        """获取负责路网扩展的智能体。"""
        if not self.environment:
            return None

        for agent in self.environment.agents.values():
            if agent is self:
                continue
            if hasattr(agent, 'expansion_history') and hasattr(agent, 'last_expansion_time'):
                return agent
        return None

    def _road_network_ready_for_zoning(self) -> bool:
        """控制“先道路、后区域、再循环”的规划节奏。"""
        if not self.environment:
            return False

        network = self.environment.road_network
        if len(network.nodes) < 6 or len(network.edges) < 8:
            return False

        planning_agent = self._get_road_planning_agent()
        if planning_agent is None:
            return True

        expansion_count = len(getattr(planning_agent, 'expansion_history', []))
        zone_count = len(self.zone_manager.zones)

        # 基础路网成形后，允许先规划第一批功能区。
        if zone_count == 0:
            return True

        # 之后遵循“道路扩展带动区域增长”，但允许一轮扩展带动多个功能区逐步补齐。
        if expansion_count * 2 > zone_count:
            last_expansion_time = float(getattr(planning_agent, 'last_expansion_time', 0.0) or 0.0)
            return (self.environment.current_time - last_expansion_time) >= 2.0

        # 当道路已经较成熟但区域仍然偏少时，允许继续补区，避免城市看起来过空。
        if len(network.nodes) >= 10 and zone_count < max(4, len(network.nodes) // 2):
            return True

        return False

    @staticmethod
    def _segment_intersects_rect(
        x1: float, y1: float, x2: float, y2: float,
        min_x: float, min_y: float, max_x: float, max_y: float
    ) -> bool:
        """判断线段是否与矩形相交。"""
        if max(x1, x2) < min_x or min(x1, x2) > max_x or max(y1, y2) < min_y or min(y1, y2) > max_y:
            return False

        if (min_x <= x1 <= max_x and min_y <= y1 <= max_y) or (min_x <= x2 <= max_x and min_y <= y2 <= max_y):
            return True

        def orientation(ax, ay, bx, by, cx, cy) -> float:
            return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)

        def on_segment(ax, ay, bx, by, cx, cy) -> bool:
            return min(ax, bx) <= cx <= max(ax, bx) and min(ay, by) <= cy <= max(ay, by)

        def segments_intersect(ax, ay, bx, by, cx, cy, dx, dy) -> bool:
            o1 = orientation(ax, ay, bx, by, cx, cy)
            o2 = orientation(ax, ay, bx, by, dx, dy)
            o3 = orientation(cx, cy, dx, dy, ax, ay)
            o4 = orientation(cx, cy, dx, dy, bx, by)

            if o1 == 0 and on_segment(ax, ay, bx, by, cx, cy):
                return True
            if o2 == 0 and on_segment(ax, ay, bx, by, dx, dy):
                return True
            if o3 == 0 and on_segment(cx, cy, dx, dy, ax, ay):
                return True
            if o4 == 0 and on_segment(cx, cy, dx, dy, bx, by):
                return True

            return (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0)

        rect_edges = [
            (min_x, min_y, max_x, min_y),
            (max_x, min_y, max_x, max_y),
            (max_x, max_y, min_x, max_y),
            (min_x, max_y, min_x, min_y),
        ]
        return any(segments_intersect(x1, y1, x2, y2, rx1, ry1, rx2, ry2) for rx1, ry1, rx2, ry2 in rect_edges)

    def _is_zone_layout_valid(
        self,
        center: Vector2D,
        width: float,
        height: float,
        zone_type: ZoneType,
        name: str | None = None
    ) -> bool:
        """统一校验区域与道路、现有区域是否冲突。"""
        test_zone = Zone(
            zone_type=zone_type,
            center=center,
            width=width,
            height=height,
            name=name,
        )
        return (
            not self.zone_manager.check_overlap(test_zone)
            and not self._check_road_overlap(test_zone)
        )
    
    def _check_road_overlap(self, zone) -> bool:
        """检查区域是否与道路重叠。"""
        if not self.environment:
            return False
        
        network = self.environment.road_network
        zone_bounds = zone.bounds  # (min_x, min_y, max_x, max_y)
        
        for edge in network.edges.values():
            from_pos = edge.from_node.position
            to_pos = edge.to_node.position
            expanded_buffer = max(18.0, self.buffer_distance)

            if self._segment_intersects_rect(
                from_pos.x,
                from_pos.y,
                to_pos.x,
                to_pos.y,
                zone_bounds[0] - expanded_buffer,
                zone_bounds[1] - expanded_buffer,
                zone_bounds[2] + expanded_buffer,
                zone_bounds[3] + expanded_buffer,
            ):
                return True
            
            # 简单检查：道路端点是否在区域边界内（加缓冲）
            buffer = 15  # 道路半宽缓冲
            
            # 检查道路端点是否与区域重叠
            for pos in [from_pos, to_pos]:
                if (zone_bounds[0] - buffer <= pos.x <= zone_bounds[2] + buffer and
                    zone_bounds[1] - buffer <= pos.y <= zone_bounds[3] + buffer):
                    return True
            
            # 检查区域中心是否太靠近道路
            # 计算点到线段的距离
            dist = self._point_to_segment_distance(
                zone.center.x, zone.center.y,
                from_pos.x, from_pos.y,
                to_pos.x, to_pos.y
            )
            min_size = min(zone.width, zone.height)
            lane_buffer = 3.5 * max(1, len(edge.lanes))
            if dist < lane_buffer + max(buffer, expanded_buffer) + min_size / 4:
                return True
        
        return False
    
    def _point_to_segment_distance(self, px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
        """计算点到线段的距离。"""
        dx = x2 - x1
        dy = y2 - y1
        
        if dx == 0 and dy == 0:
            return math.sqrt((px - x1)**2 + (py - y1)**2)
        
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        
        return math.sqrt((px - proj_x)**2 + (py - proj_y)**2)
    
    def act(self, decision: dict[str, Any] | None) -> bool:
        """执行区域规划。"""
        if not decision or not self.environment:
            return False

        if not self._road_network_ready_for_zoning():
            return False
        
        action = decision.get('action')
        if action != 'create_zone':
            return False
        
        self.record_action(
            'create_zone',
            {
                'zone_type': decision.get('zone_type').name if decision.get('zone_type') else 'UNKNOWN',
                'reason': decision.get('reason', ''),
            },
            importance=5.0
        )
        
        try:
            zone_type = decision['zone_type']
            center = decision['center']
            width = decision['width']
            height = decision['height']
            name = decision.get('name', f'{zone_type.display_name}_新规划')
            evaluation = decision.get('evaluation', {})
            llm_eval = decision.get('llm_evaluation', {})
            
            # 创建区域
            zone = Zone(
                zone_type=zone_type,
                center=center,
                width=width,
                height=height,
                name=name
            )
            
            # 检查与其他区域重叠
            overlapping = self.zone_manager.check_overlap(zone)
            # 检查与道路重叠
            road_overlap = self._check_road_overlap(zone)
            
            if overlapping or road_overlap:
                # 尝试调整位置
                for offset_x in [-40, 40, -80, 80, -120, 120]:
                    for offset_y in [-40, 40, -80, 80, -120, 120]:
                        adjusted_center = Vector2D(center.x + offset_x, center.y + offset_y)
                        test_zone = Zone(zone_type, adjusted_center, width, height, name)
                        
                        # 检查区域重叠和道路重叠
                        if (not self.zone_manager.check_overlap(test_zone) and 
                            not self._check_road_overlap(test_zone)):
                            zone = test_zone
                            print(f"[ZoningAgent] 调整位置 ({offset_x}, {offset_y}) 避免重叠")
                            break
                    else:
                        continue
                    break
                else:
                    print(f"[ZoningAgent] 无法找到不重叠的位置，跳过")
                    return False
            
            # 连接到最近的节点
            network = self.environment.road_network
            if network.nodes:
                nearest_node = min(network.nodes.values(),
                                  key=lambda n: zone.distance_to_node(n))
                zone.connect_to_node(nearest_node)
            
            # 设置规划信息
            zone.planning_time = self.environment.current_time
            zone.planned_by = "ZoningAgent"
            zone.planning_reason = decision.get('reason', '')
            
            # 设置初始人口
            base_pop_ratio = random.uniform(0.3, 0.6)
            if evaluation.get('total_score', 0.5) > 0.8:
                base_pop_ratio = random.uniform(0.5, 0.8)
            zone.target_population = int(zone.max_population * base_pop_ratio)
            zone.population = zone.target_population // 2
            
            # 添加到管理器
            self.zone_manager.add_zone(zone)
            self.total_zones_planned += 1
            
            # 记录历史
            history_entry = {
                'time': self.environment.current_time,
                'zone_id': zone.zone_id,
                'zone_type': zone_type.name,
                'name': name,
                'center': {'x': center.x, 'y': center.y},
                'area': zone.area,
                'population': zone.population,
                'reason': decision.get('reason', ''),
                'score': decision.get('score', 0),
                'evaluation_summary': {
                    'total_score': evaluation.get('total_score', 0),
                    'advantages': evaluation.get('advantages', [])
                }
            }
            
            if llm_eval:
                history_entry['llm_opinion'] = {
                    'approved': llm_eval.get('is_approved', True),
                    'llm_score': llm_eval.get('score', 0),
                    'reasoning': llm_eval.get('reasoning', '')
                }
            
            self.planning_history.append(history_entry)
            self.record_event(
                '新区规划成功',
                {
                    'zone_id': zone.zone_id,
                    'zone_type': zone_type.name,
                    'name': name,
                    'population': zone.population,
                },
                importance=7.0
            )
            
            # 输出
            score_str = f"评分: {decision.get('score', 0):.2f}"
            if llm_eval:
                score_str += f", LLM: {llm_eval.get('score', 0):.2f}"
            
            print(f"[ZoningAgent] 新增区域: {name} ({zone_type.display_name}), "
                  f"{score_str}, 人口: {zone.population}")
            
            if evaluation.get('advantages'):
                print(f"             优点: {', '.join(evaluation['advantages'][:2])}")
            
            self.last_decision = decision
            return True
            
        except Exception as e:
            print(f"[ZoningAgent] 创建区域失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def update(self, dt: float) -> None:
        """更新智能体状态。"""
        if not self.environment:
            return

        current_time = self.environment.current_time

        # 按规划间隔批量补充区域，数量由人口与路网状态共同决定
        if (
            current_time > 0
            and current_time - self.last_planning_time >= self.planning_interval
            and self._road_network_ready_for_zoning()
        ):
            # 立即更新时间戳，防止规划失败后立即重试导致频繁请求LLM
            self.last_planning_time = current_time
            
            batch_count = self._determine_zone_batch_count()
            if batch_count <= 0:
                return
                
            # 城市规划是长期过程，每轮只做一个决策，避免短时间内大量LLM请求
            # 批量规划改为分多轮执行，每轮间隔 planning_interval
            decision = self.decide()
            if decision and self.act(decision):
                stats = self.zone_manager.get_statistics()
                print(
                    f"[ZoningAgent] 新增功能区成功，"
                    f"当前共 {stats['total_zones']} 个区域, 总人口 {stats['total_population']}"
                )
            else:
                print(f"[ZoningAgent] 本轮规划未产生有效区域，等待下一轮")

        for zone in self.zone_manager.zones.values():
            if zone.population < zone.target_population:
                zone.grow_population(0.005)

    def _llm_determine_zone_batch_count(self) -> int | None:
        """使用大模型根据人口与路网状态决定本轮新增区域数。"""
        prompt = ""
        try:
            network_info = self._get_network_info()
            population_stats = self._get_population_stats()
            zone_stats = self.zone_manager.get_statistics()
            planning_agent = self._get_road_planning_agent()
            expansion_count = len(getattr(planning_agent, 'expansion_history', [])) if planning_agent else 0

            prompt = f"""你是城市规划总控，需要决定这一轮应该新增多少个功能区域。
当前状态：
- 道路节点数: {network_info.get('nodes', 0)}
- 道路边数: {network_info.get('edges', 0)}
- 当前功能区数量: {zone_stats.get('total_zones', 0)}
- 当前总人口: {population_stats.get('total_population', 0)}
- 当前总容量: {population_stats.get('max_capacity', 0)}
- 路网扩展次数: {expansion_count}
- 各类功能区统计: {json.dumps(zone_stats.get('by_type', {}), ensure_ascii=False)}

决策原则：
1. 区域数量必须服从人口规模与道路承载能力，不能盲目增加。
2. 若道路刚扩展且人口在增长，可以一轮增加多个区域。
3. 若道路不足、人口低、现有区域已经较多，则应保守。
4. 输出的 count 必须在 1 到 4 之间。
只输出 JSON：
{{
  "count": 1,
  "reason": "简短说明"
}}"""

            llm_manager = self._get_llm_manager()
            if not llm_manager:
                return None

            response = llm_manager.request_sync_decision(prompt, timeout=10.0)
            if not response:
                self._archive_llm_decision("zone_batch_count", prompt, adopted=False, status="empty_response", summary="功能区批量规模决策")
                return None

            start = response.find('{')
            end = response.rfind('}')
            if start == -1 or end == -1:
                self._archive_llm_decision("zone_batch_count", prompt, response=response, adopted=False, status="parse_failed", summary="功能区批量规模决策")
                return None

            result = json.loads(response[start:end+1])
            self._archive_llm_decision(
                "zone_batch_count",
                prompt,
                response=response,
                parsed=result,
                adopted=True,
                status="success",
                summary="功能区批量规模决策",
            )
            return int(result.get('count', 1))
        except Exception as e:
            self._archive_llm_decision(
                "zone_batch_count",
                prompt,
                adopted=False,
                status="error",
                summary="功能区批量规模决策",
                extra={"error": str(e)},
            )
            print(f"[ZoningAgent] LLM区域数量决策失败: {e}")
            return None

    def _llm_select_location_and_type(self, locations: list[dict]) -> dict[str, Any] | None:
        """使用 LLM 选择位置和功能类型，并归档原始文本。"""
        prompt = ""
        try:
            network_info = self._get_network_info()
            total_pop = self.zone_manager.get_total_population()

            zone_stats = {}
            for zt in ZoneType:
                count = len(self.zone_manager.get_zones_by_type(zt))
                if count > 0:
                    zone_stats[zt.name] = count

            prompt = f"""你是一位城市规划专家。请为城市选择一个新功能区域的位置和类型。

当前城市状态：
- 道路节点数: {network_info['nodes']}
- 当前总人口: {total_pop}
- 已有区域: {zone_stats}

候选位置（沿道路布局）：
{json.dumps(locations[:10], ensure_ascii=False, indent=2)}

规划原则：
1. 住宅区优先贴近交通便利的道路，服务人口。
2. 商业区优先靠近交叉口或主干道。
3. 学校靠近住宅区。
4. 医院要求交通便利且覆盖范围广。
5. 公园靠近住宅区。
6. 工业区可布置在相对边缘位置。

只输出 JSON：
{{
  "selected_index": 0,
  "zone_type": "RESIDENTIAL",
  "reason": "选择理由",
  "confidence": 0.8
}}"""

            llm_manager = self._get_llm_manager()
            if not llm_manager:
                return None

            response = llm_manager.request_sync_decision(prompt, timeout=10.0)
            if not response:
                self._archive_llm_decision("zone_location_type", prompt, adopted=False, status="empty_response", summary="功能区选址与类型决策")
                return None

            decision = self._parse_llm_location_response(response, locations)
            if decision:
                parsed = {
                    "zone_type": decision.get("zone_type").name if decision.get("zone_type") else None,
                    "center": {
                        "x": getattr(decision.get("center"), "x", None),
                        "y": getattr(decision.get("center"), "y", None),
                    },
                    "width": decision.get("width"),
                    "height": decision.get("height"),
                    "reason": decision.get("reason"),
                    "confidence": decision.get("confidence"),
                    "edge_id": decision.get("edge_id"),
                }
                self._archive_llm_decision(
                    "zone_location_type",
                    prompt,
                    response=response,
                    parsed=parsed,
                    adopted=True,
                    status="success",
                    summary="功能区选址与类型决策",
                )
                return decision

            self._archive_llm_decision(
                "zone_location_type",
                prompt,
                response=response,
                adopted=False,
                status="parse_failed",
                summary="功能区选址与类型决策",
            )
        except Exception as e:
            self._archive_llm_decision(
                "zone_location_type",
                prompt,
                adopted=False,
                status="error",
                summary="功能区选址与类型决策",
                extra={"error": str(e)},
            )
            print(f"[ZoningAgent] LLM选址失败: {e}")

        return None

    def get_status(self) -> dict[str, Any]:
        """获取智能体状态。"""
        # 处理决策信息，确保可JSON序列化
        last_decision = None
        if self.last_decision:
            last_decision = dict(self.last_decision)
            # 转换ZoneType枚举为字符串
            if 'zone_type' in last_decision and hasattr(last_decision['zone_type'], 'name'):
                last_decision['zone_type'] = last_decision['zone_type'].name
            # 转换center (Vector2D) 为字典
            if 'center' in last_decision and hasattr(last_decision['center'], 'x'):
                center = last_decision['center']
                last_decision['center'] = {'x': float(center.x), 'y': float(center.y)}
        
        return {
            'agent_id': self.agent_id,
            'agent_type': 'ZoningAgent',
            'total_zones': len(self.zone_manager.zones),
            'zone_stats': self.zone_manager.get_statistics(),
            'planning_history_count': len(self.planning_history),
            'total_zones_planned': self.total_zones_planned,
            'last_planning_time': self.last_planning_time,
            'max_zones': self.max_zones,
            'last_decision': last_decision,
            'llm_decision_count': len(self.zoning_planner.llm_decision_history) if self.zoning_planner else 0
        }
    
    def get_zones_data(self) -> list[dict]:
        """获取所有区域数据。"""
        return self.zone_manager.to_list()
