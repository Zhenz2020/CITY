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
from city.llm.text_normalizer import normalize_decision_text_fields, normalize_reason_text
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
        zoning_candidates = self._collect_zoning_candidates()
        if not zoning_candidates:
            return None
        
        # 使用LLM选择最佳位置和功能类型
        if self.use_llm:
            decision = self._llm_select_location_and_type(zoning_candidates)
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
        decision = self._rule_select_location_and_type(zoning_candidates)
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

    def _collect_zoning_candidates(
        self,
        max_zone_types: int = 4,
        max_candidates_per_type: int = 3,
        max_candidates: int = 10
    ) -> list[dict[str, Any]]:
        """Collect block-first candidates for the next zoning decision."""
        network_info = self._get_network_info()
        bounds = network_info.get('bounds')
        if not bounds:
            return []

        zone_types = self._prioritize_zone_types(max_zone_types=max_zone_types)
        if not zone_types:
            return []

        all_candidates: list[dict[str, Any]] = []
        for zone_type in zone_types:
            type_candidates = self._build_block_candidates_for_type(
                zone_type=zone_type,
                max_candidates=max_candidates_per_type,
            )
            if not type_candidates:
                fallback = self._build_fallback_candidate(zone_type, bounds)
                if fallback:
                    type_candidates.append(fallback)
            all_candidates.extend(type_candidates)

        unique_candidates: list[dict[str, Any]] = []
        seen: set[tuple[str, int, int, int, int]] = set()
        for candidate in all_candidates:
            key = (
                candidate['zone_type'].name,
                round(candidate['center'].x),
                round(candidate['center'].y),
                round(candidate['width']),
                round(candidate['height']),
            )
            if key in seen:
                continue
            seen.add(key)
            unique_candidates.append(candidate)

        priority_rank = {'high': 0, 'medium': 1, 'low': 2}
        unique_candidates.sort(
            key=lambda candidate: (
                priority_rank.get(candidate.get('priority', 'medium'), 1),
                -candidate.get('score', 0.0),
                -candidate.get('fill_ratio', 0.0),
                0 if candidate.get('is_block_fill') else 1,
            )
        )
        return unique_candidates[:max_candidates]

    def _prioritize_zone_types(self, max_zone_types: int = 4) -> list[ZoneType]:
        """Pick a small set of zone types for the next planning round."""
        needs = self._analyze_zoning_needs()
        priority_rank = {'high': 0, 'medium': 1, 'low': 2}
        ranked_types: list[tuple[int, int, int, ZoneType]] = []

        for type_name, need in needs.items():
            try:
                zone_type = ZoneType[type_name]
            except KeyError:
                continue

            gap = int(need.get('needed', 0)) - int(need.get('current', 0))
            ranked_types.append(
                (
                    priority_rank.get(need.get('priority', 'medium'), 1),
                    -gap,
                    zone_type.priority,
                    zone_type,
                )
            )

        ranked_types.sort()
        selected = [zone_type for _, _, _, zone_type in ranked_types]

        fallback_order = [
            ZoneType.RESIDENTIAL,
            ZoneType.COMMERCIAL,
            ZoneType.PARK,
            ZoneType.OFFICE,
            ZoneType.SCHOOL,
            ZoneType.HOSPITAL,
            ZoneType.INDUSTRIAL,
        ]
        for zone_type in fallback_order:
            if zone_type not in selected:
                selected.append(zone_type)

        return selected[:max_zone_types]

    def _build_block_candidates_for_type(
        self,
        zone_type: ZoneType,
        max_candidates: int = 3
    ) -> list[dict[str, Any]]:
        """Generate candidates that fill road-enclosed blocks for one zone type."""
        blocks = self.zoning_planner._detect_road_blocks()
        if not blocks:
            return []

        need_info = self._analyze_zoning_needs().get(zone_type.name, {})
        candidates: list[dict[str, Any]] = []
        for block in blocks:
            fitted = self._fit_block_dimensions(zone_type, block['width'], block['height'])
            if not fitted:
                continue

            center = block['center']
            width = fitted['width']
            height = fitted['height']
            evaluation = self.zoning_planner.evaluate_location(zone_type, center, width, height)
            if not evaluation.get('is_suitable', False):
                continue

            block_score = self._score_block_for_zone_type(zone_type, block)
            score = evaluation.get('total_score', 0.0) * 0.75 + block_score * 0.25
            candidates.append({
                'zone_type': zone_type,
                'center': center,
                'width': width,
                'height': height,
                'score': score,
                'priority': need_info.get('priority', 'medium'),
                'need_reason': need_info.get('reason', 'Balanced land-use growth'),
                'evaluation': evaluation,
                'llm_evaluation': None,
                'candidate_source': 'road_block',
                'is_block_fill': True,
                'fill_ratio': fitted['fill_ratio'],
                'block_area': block['area'],
                'bounds': block.get('bounds'),
            })

        candidates.sort(
            key=lambda candidate: (
                -candidate.get('score', 0.0),
                -candidate.get('fill_ratio', 0.0),
            )
        )
        return candidates[:max_candidates]

    def _build_fallback_candidate(
        self,
        zone_type: ZoneType,
        bounds: dict[str, float],
        attempts: int = 8
    ) -> dict[str, Any] | None:
        """Build a bounded fallback candidate when no enclosed block is usable."""
        need_info = self._analyze_zoning_needs().get(zone_type.name, {})
        limits = self._get_zone_size_limits(zone_type)
        best_candidate: dict[str, Any] | None = None

        for _ in range(attempts):
            center = self.zoning_planner._generate_candidate_location(
                zone_type,
                bounds['min_x'],
                bounds['max_x'],
                bounds['min_y'],
                bounds['max_y'],
            )
            if not center:
                continue

            width = random.uniform(limits['min_width'], limits['max_width'])
            height = random.uniform(limits['min_height'], limits['max_height'])
            if width * height > limits['max_area']:
                scale = math.sqrt(limits['max_area'] / (width * height))
                width *= scale
                height *= scale

            evaluation = self.zoning_planner.evaluate_location(zone_type, center, width, height)
            if not evaluation.get('is_suitable', False):
                continue

            candidate = {
                'zone_type': zone_type,
                'center': center,
                'width': width,
                'height': height,
                'score': evaluation.get('total_score', 0.0),
                'priority': need_info.get('priority', 'medium'),
                'need_reason': need_info.get('reason', 'Balanced land-use growth'),
                'evaluation': evaluation,
                'llm_evaluation': None,
                'candidate_source': 'fallback',
                'is_block_fill': False,
                'fill_ratio': 0.0,
                'block_area': width * height,
                'bounds': None,
            }
            if best_candidate is None or candidate['score'] > best_candidate['score']:
                best_candidate = candidate

        return best_candidate

    def _get_zone_size_limits(self, zone_type: ZoneType) -> dict[str, float]:
        """Return hard caps used to prevent oversized zoning blocks."""
        limits = {
            ZoneType.RESIDENTIAL: {'max_width': 210.0, 'max_height': 190.0, 'max_area': 28000.0},
            ZoneType.COMMERCIAL: {'max_width': 180.0, 'max_height': 170.0, 'max_area': 22000.0},
            ZoneType.INDUSTRIAL: {'max_width': 250.0, 'max_height': 220.0, 'max_area': 42000.0},
            ZoneType.HOSPITAL: {'max_width': 170.0, 'max_height': 170.0, 'max_area': 22000.0},
            ZoneType.SCHOOL: {'max_width': 200.0, 'max_height': 180.0, 'max_area': 26000.0},
            ZoneType.PARK: {'max_width': 220.0, 'max_height': 210.0, 'max_area': 32000.0},
            ZoneType.OFFICE: {'max_width': 180.0, 'max_height': 180.0, 'max_area': 22000.0},
            ZoneType.MIXED_USE: {'max_width': 200.0, 'max_height': 180.0, 'max_area': 26000.0},
            ZoneType.GOVERNMENT: {'max_width': 170.0, 'max_height': 170.0, 'max_area': 20000.0},
            ZoneType.SHOPPING: {'max_width': 190.0, 'max_height': 180.0, 'max_area': 24000.0},
        }.get(zone_type, {'max_width': 180.0, 'max_height': 180.0, 'max_area': 22000.0})

        min_width = max(50.0, min(self.max_zone_size, self.min_zone_size))
        min_height = max(50.0, min(self.max_zone_size, self.min_zone_size * 0.85))
        min_area = max(zone_type.min_size * 0.7, min_width * min_height * 0.8)
        return {
            'min_width': min_width,
            'min_height': min_height,
            'min_area': min_area,
            'max_width': max(limits['max_width'], min_width),
            'max_height': max(limits['max_height'], min_height),
            'max_area': max(limits['max_area'], min_area),
        }

    def _fit_block_dimensions(
        self,
        zone_type: ZoneType,
        block_width: float,
        block_height: float
    ) -> dict[str, float] | None:
        """Fit a zone into a road block while keeping hard size caps."""
        limits = self._get_zone_size_limits(zone_type)
        clearance = min(10.0, block_width * 0.08, block_height * 0.08)
        width = max(0.0, block_width - clearance)
        height = max(0.0, block_height - clearance)

        width = min(width, limits['max_width'])
        height = min(height, limits['max_height'])
        area = width * height
        if area > limits['max_area'] and area > 0:
            scale = math.sqrt(limits['max_area'] / area)
            width *= scale
            height *= scale
            area = width * height

        if width < limits['min_width'] or height < limits['min_height']:
            return None
        if area < limits['min_area']:
            return None

        fill_ratio = area / max(block_width * block_height, 1.0)
        return {
            'width': width,
            'height': height,
            'fill_ratio': fill_ratio,
        }

    def _score_block_for_zone_type(self, zone_type: ZoneType, block: dict[str, Any]) -> float:
        """Score how well a block matches a zone type before the final LLM choice."""
        area = block['area']
        center = block['center']
        network_info = self._get_network_info()
        bounds = network_info.get('bounds') or {}
        city_center_x = (bounds.get('min_x', center.x) + bounds.get('max_x', center.x)) / 2
        city_center_y = (bounds.get('min_y', center.y) + bounds.get('max_y', center.y)) / 2
        max_radius = max(
            bounds.get('max_x', center.x) - bounds.get('min_x', center.x),
            bounds.get('max_y', center.y) - bounds.get('min_y', center.y),
            1.0,
        ) / 2
        center_distance = math.sqrt((center.x - city_center_x) ** 2 + (center.y - city_center_y) ** 2)
        center_score = max(0.0, 1.0 - center_distance / max_radius)
        edge_score = 1.0 - center_score

        if zone_type == ZoneType.RESIDENTIAL:
            target_area = 18000.0
            return max(0.0, 1.0 - abs(area - target_area) / target_area)
        if zone_type == ZoneType.COMMERCIAL:
            return center_score * 0.65 + min(1.0, area / 18000.0) * 0.35
        if zone_type == ZoneType.INDUSTRIAL:
            return edge_score * 0.55 + min(1.0, area / 25000.0) * 0.45
        if zone_type == ZoneType.SCHOOL:
            target_area = 14000.0
            return max(0.0, 1.0 - abs(area - target_area) / target_area)
        if zone_type == ZoneType.HOSPITAL:
            return center_score * 0.45 + min(1.0, area / 20000.0) * 0.55
        if zone_type == ZoneType.PARK:
            return 0.5 + min(0.5, area / 32000.0)
        if zone_type == ZoneType.OFFICE:
            return center_score * 0.6 + min(1.0, area / 16000.0) * 0.4
        return min(1.0, area / 18000.0)
    
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
    
    def _parse_llm_location_response(self, response: str, candidates: list[dict]) -> dict[str, Any] | None:
        """Parse an LLM selection over the prepared zoning candidate list."""
        try:
            start = response.find('{')
            end = response.rfind('}')
            if start == -1 or end == -1:
                return None
            
            result = json.loads(response[start:end+1])
            
            index = int(result.get('selected_index', 0))
            if index < 0 or index >= len(candidates):
                index = 0
            
            selected = candidates[index]
            zone_type = selected['zone_type']
            reason = normalize_reason_text(
                result.get('reason') or selected.get('need_reason') or 'LLM selected best candidate',
                action='create_zone',
                fallback='LLM selected the best zoning candidate.',
            )
            confidence = float(result.get('confidence', selected.get('score', 0.8)))
            
            return {
                'action': 'create_zone',
                'zone_type': zone_type,
                'center': selected['center'],
                'width': selected['width'],
                'height': selected['height'],
                'name': f"{zone_type.name}_{len(self.zone_manager.zones) + 1}",
                'reason': reason,
                'priority': selected.get('priority', 'medium'),
                'confidence': max(0.0, min(1.0, confidence)),
                'is_llm': True,
                'score': selected.get('score', 0.0),
                'evaluation': selected.get('evaluation', {}),
                'llm_evaluation': {
                    'is_approved': True,
                    'score': max(0.0, min(1.0, confidence)),
                    'reasoning': reason,
                },
                'candidate_source': selected.get('candidate_source', 'unknown'),
                'is_block_fill': selected.get('is_block_fill', False),
                'fill_ratio': selected.get('fill_ratio', 0.0),
                'block_area': selected.get('block_area'),
                'bounds': selected.get('bounds'),
            }
            
        except Exception as e:
            print(f"[ZoningAgent] 解析LLM响应失败: {e}")
            return None
    
    def _rule_select_location_and_type(self, candidates: list[dict]) -> dict[str, Any] | None:
        """Select the best prepared candidate without the LLM."""
        if not candidates:
            return None
        
        priority_rank = {'high': 0, 'medium': 1, 'low': 2}
        selected = sorted(
            candidates,
            key=lambda candidate: (
                priority_rank.get(candidate.get('priority', 'medium'), 1),
                -candidate.get('score', 0.0),
                -candidate.get('fill_ratio', 0.0),
                0 if candidate.get('is_block_fill') else 1,
            )
        )[0]
        zone_type = selected['zone_type']
        
        return {
            'action': 'create_zone',
            'zone_type': zone_type,
            'center': selected['center'],
            'width': selected['width'],
            'height': selected['height'],
            'name': f"{zone_type.name}_{len(self.zone_manager.zones) + 1}",
            'reason': selected.get('need_reason', 'Rule-based candidate selection'),
            'priority': selected.get('priority', 'medium'),
            'is_llm': False,
            'score': selected.get('score', 0.0),
            'evaluation': selected.get('evaluation', {}),
            'llm_evaluation': None,
            'candidate_source': selected.get('candidate_source', 'unknown'),
            'is_block_fill': selected.get('is_block_fill', False),
            'fill_ratio': selected.get('fill_ratio', 0.0),
            'block_area': selected.get('block_area'),
            'bounds': selected.get('bounds'),
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
                'reason': 'Establish the first residential district'
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
                'RESIDENTIAL': 'Increase housing capacity',
                'COMMERCIAL': 'Improve commercial support',
                'OFFICE': 'Provide employment capacity',
                'INDUSTRIAL': 'Develop industrial capacity',
                'SCHOOL': 'Expand education services',
                'HOSPITAL': 'Expand medical services',
                'PARK': 'Add green space'
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
                    'reason': 'Expand residential space'
                }
            elif commercial < max(1, residential // 4):
                needs['COMMERCIAL'] = {
                    'current': commercial,
                    'needed': commercial + 1,
                    'priority': 'medium',
                    'reason': 'Add commercial services'
                }
            elif parks < residential // 2:
                needs['PARK'] = {
                    'current': parks,
                    'needed': parks + 1,
                    'priority': 'medium',
                    'reason': 'Add parks and green space'
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
            name = self.zone_manager.next_zone_name(zone_type)
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
            name = zone.name
            decision['name'] = name
            self.total_zones_planned += 1
            
            # 记录历史
            history_entry = {
                'time': self.environment.current_time,
                'zone_id': zone.zone_id,
                'zone_type': zone_type.name,
                'name': name,
                'center': {'x': zone.center.x, 'y': zone.center.y},
                'area': zone.area,
                'population': zone.population,
                'reason': decision.get('reason', ''),
                'score': decision.get('score', 0),
                'candidate_source': decision.get('candidate_source', 'unknown'),
                'is_block_fill': decision.get('is_block_fill', False),
                'fill_ratio': decision.get('fill_ratio', 0.0),
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
        
        # 人口增长
        for zone in self.zone_manager.zones.values():
            if zone.population < zone.target_population:
                zone.grow_population(0.005)
        
        # 检查是否需要基于人口压力触发规划
        population_pressure = self._check_population_pressure()
        should_plan = (
            current_time > 0
            and current_time - self.last_planning_time >= self.planning_interval
            and self._road_network_ready_for_zoning()
        ) or population_pressure
        
        # 按规划间隔批量补充区域，数量由人口与路网状态共同决定
        if should_plan:
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
    
    def _check_population_pressure(self) -> bool:
        """
        检查人口压力，如果人口接近容量上限则触发规划。
        
        Returns:
            如果人口压力超过阈值则返回True
        """
        stats = self.zone_manager.get_statistics()
        total_pop = stats.get('total_population', 0)
        
        # 计算总容量
        total_capacity = sum(
            zone.max_population 
            for zone in self.zone_manager.zones.values()
        )
        
        if total_capacity == 0:
            return False
        
        # 人口使用率
        utilization = total_pop / total_capacity
        
        # 如果人口使用率超过70%，触发规划
        if utilization > 0.7:
            print(f"[ZoningAgent] 人口压力高: {utilization*100:.1f}% ({total_pop}/{total_capacity})，触发规划")
            return True
        
        return False

    def _llm_determine_zone_batch_count(self) -> int | None:
        """使用大模型根据人口与路网状态决定本轮新增区域数。"""
        prompt = ""
        try:
            network_info = self._get_network_info()
            population_stats = self._get_population_stats()
            zone_stats = self.zone_manager.get_statistics()
            planning_agent = self._get_road_planning_agent()
            expansion_count = len(getattr(planning_agent, 'expansion_history', [])) if planning_agent else 0

            prompt = f"""You are the land-use planning controller for the city simulation.
Decide how many new zones should be added in this planning round.

Current state:
- Road nodes: {network_info.get('nodes', 0)}
- Road edges: {network_info.get('edges', 0)}
- Existing zones: {zone_stats.get('total_zones', 0)}
- Total population: {population_stats.get('total_population', 0)}
- Total capacity: {population_stats.get('max_capacity', 0)}
- Road expansion count: {expansion_count}
- Zone statistics: {json.dumps(zone_stats.get('by_type', {}), ensure_ascii=False)}

Decision rules:
1. The number of new zones must match population scale and road-network carrying capacity.
2. If the road network has just expanded and population is growing, multiple zones may be added.
3. If the road network is still weak, population is low, or many zones already exist, remain conservative.
4. The output count must be between 1 and 4.
5. Write the reason in English only.

Return JSON only:
{{
  "count": 1,
  "reason": "short explanation"
}}"""

            llm_manager = self._get_llm_manager()
            if not llm_manager:
                return None

            response = llm_manager.request_sync_decision(prompt, timeout=10.0)
            if not response:
                self._archive_llm_decision("zone_batch_count", prompt, adopted=False, status="empty_response", summary="Zone batch size decision")
                return None

            start = response.find('{')
            end = response.rfind('}')
            if start == -1 or end == -1:
                self._archive_llm_decision("zone_batch_count", prompt, response=response, adopted=False, status="parse_failed", summary="Zone batch size decision")
                return None

            result = normalize_decision_text_fields(json.loads(response[start:end+1]))
            self._archive_llm_decision(
                "zone_batch_count",
                prompt,
                response=response,
                parsed=result,
                adopted=True,
                status="success",
                summary="Zone batch size decision",
            )
            return int(result.get('count', 1))
        except Exception as e:
            self._archive_llm_decision(
                "zone_batch_count",
                prompt,
                adopted=False,
                status="error",
                summary="Zone batch size decision",
                extra={"error": str(e)},
            )
            print(f"[ZoningAgent] LLM区域数量决策失败: {e}")
            return None

    def _llm_select_location_and_type(self, candidates: list[dict]) -> dict[str, Any] | None:
        """Use the LLM to choose from prepared zoning candidates and archive the result."""
        prompt = ""
        try:
            network_info = self._get_network_info()
            total_pop = self.zone_manager.get_total_population()

            zone_stats = {}
            for zt in ZoneType:
                count = len(self.zone_manager.get_zones_by_type(zt))
                if count > 0:
                    zone_stats[zt.name] = count

            prompt_candidates = []
            for index, candidate in enumerate(candidates[:10]):
                prompt_candidates.append({
                    "index": index,
                    "zone_type": candidate["zone_type"].name,
                    "source": candidate.get("candidate_source", "unknown"),
                    "block_fill": candidate.get("is_block_fill", False),
                    "center": {
                        "x": round(candidate["center"].x, 1),
                        "y": round(candidate["center"].y, 1),
                    },
                    "width": round(candidate["width"], 1),
                    "height": round(candidate["height"], 1),
                    "area": round(candidate["width"] * candidate["height"], 1),
                    "fill_ratio": round(candidate.get("fill_ratio", 0.0), 3),
                    "score": round(candidate.get("score", 0.0), 3),
                    "priority": candidate.get("priority", "medium"),
                    "need_reason": candidate.get("need_reason", ""),
                    "advantages": candidate.get("evaluation", {}).get("advantages", [])[:3],
                })

            prompt = f"""You are the land-use planning model for a transport simulation platform.

Current city state:
- Road nodes: {network_info['nodes']}
- Total population: {total_pop}
- Existing zones: {json.dumps(zone_stats, ensure_ascii=False)}

Candidate zoning options:
{json.dumps(prompt_candidates, ensure_ascii=False, indent=2)}

Decision rules:
1. Prefer road-enclosed block-fill candidates when they are spatially reasonable.
2. Do not choose an oversized district just because the original block is large; candidate sizes are already capped.
3. Match the next zone with current city needs and service balance.
4. Higher score and higher fill ratio are better, but city balance still matters.

Return JSON only:
{{
  "selected_index": 0,
  "reason": "short reason",
  "confidence": 0.85
}}"""

            llm_manager = self._get_llm_manager()
            if not llm_manager:
                return None

            response = llm_manager.request_sync_decision(prompt, timeout=10.0)
            if not response:
                self._archive_llm_decision("zone_location_type", prompt, adopted=False, status="empty_response", summary="Zone siting and type decision")
                return None

            decision = self._parse_llm_location_response(response, candidates)
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
                    "candidate_source": decision.get("candidate_source"),
                    "is_block_fill": decision.get("is_block_fill"),
                    "fill_ratio": decision.get("fill_ratio"),
                }
                self._archive_llm_decision(
                    "zone_location_type",
                    prompt,
                    response=response,
                    parsed=parsed,
                    adopted=True,
                    status="success",
                    summary="Zone siting and type decision",
                )
                return decision

            self._archive_llm_decision(
                "zone_location_type",
                prompt,
                response=response,
                adopted=False,
                status="parse_failed",
                summary="Zone siting and type decision",
            )
        except Exception as e:
            self._archive_llm_decision(
                "zone_location_type",
                prompt,
                adopted=False,
                status="error",
                summary="Zone siting and type decision",
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
        
        # 计算人口压力
        zone_stats = self.zone_manager.get_statistics()
        total_pop = zone_stats.get('total_population', 0)
        total_capacity = sum(zone.max_population for zone in self.zone_manager.zones.values())
        population_pressure = total_pop / total_capacity if total_capacity > 0 else 0
        
        return {
            'agent_id': self.agent_id,
            'agent_type': 'ZoningAgent',
            'state': 'planning' if self._check_population_pressure() else 'normal',
            'total_zones': len(self.zone_manager.zones),
            'zone_stats': zone_stats,
            'total_population': total_pop,
            'total_capacity': total_capacity,
            'population_pressure': round(population_pressure, 2),
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
