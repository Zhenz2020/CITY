"""
城市规划智能体 (Zoning Agent)。

基于LLM的城市功能区域规划智能体，负责规划住宅、商业、医院、学校等功能区域。
"""

from __future__ import annotations

import json
import random
from typing import TYPE_CHECKING, Any

from city.agents.base import AgentType, BaseAgent
from city.urban_planning.zone import Zone, ZoneType, ZoneRequirement, ZoneManager
from city.utils.vector import Vector2D

if TYPE_CHECKING:
    from city.simulation.environment import SimulationEnvironment
    from city.environment.road_network import Node


class ZoningAgent(BaseAgent):
    """
    城市规划智能体。
    
    基于LLM驱动的城市功能区域规划智能体，能够：
    1. 分析当前城市状态和需求
    2. 使用LLM决策区域类型和位置
    3. 规划住宅区、商业区、医院、学校等功能区域
    4. 确保区域布局合理（避免冲突、满足服务半径等）
    
    Attributes:
        zone_manager: 区域管理器
        use_llm: 是否使用LLM进行决策
        planning_interval: 规划间隔（秒）
        max_zones: 最大区域数量
        min_zone_size: 最小区域尺寸
        max_zone_size: 最大区域尺寸
    """
    
    def __init__(
        self,
        environment: SimulationEnvironment | None = None,
        use_llm: bool = True,
        planning_interval: float = 20.0,
        max_zones: int = 30,
        min_zone_size: float = 50.0,
        max_zone_size: float = 200.0,
        buffer_distance: float = 20.0
    ):
        super().__init__(AgentType.TRAFFIC_PLANNER, environment, use_llm)
        
        self.zone_manager = ZoneManager()
        self.planning_interval = planning_interval
        self.max_zones = max_zones
        self.min_zone_size = min_zone_size
        self.max_zone_size = max_zone_size
        self.buffer_distance = buffer_distance
        
        # 状态
        self.last_planning_time = 0.0
        self.planning_history: list[dict[str, Any]] = []
        self.pending_requirements: list[ZoneRequirement] = []
        
        # 规划策略
        self.zone_priorities = [
            ZoneType.RESIDENTIAL,  # 先规划住宅
            ZoneType.SCHOOL,       # 然后学校
            ZoneType.COMMERCIAL,   # 然后商业
            ZoneType.HOSPITAL,     # 然后医院
            ZoneType.PARK,         # 然后公园
            ZoneType.OFFICE,       # 然后办公
            ZoneType.SHOPPING,     # 购物
            ZoneType.INDUSTRIAL,   # 工业
            ZoneType.GOVERNMENT,   # 政府
            ZoneType.MIXED_USE,    # 混合
        ]
        
        # LLM决策记录
        self.last_decision: dict[str, Any] | None = None
        
    def perceive(self) -> dict[str, Any]:
        """感知城市状态。"""
        perception = {
            'current_time': self.environment.current_time if self.environment else 0,
            'total_zones': len(self.zone_manager.zones),
            'zones_by_type': {},
            'network_info': self._get_network_info(),
            'city_stats': self._get_city_stats(),
            'population_stats': self._get_population_stats()
        }
        
        # 统计各类型区域
        for zone_type in ZoneType:
            zones = self.zone_manager.get_zones_by_type(zone_type)
            if zones:
                perception['zones_by_type'][zone_type.name] = {
                    'count': len(zones),
                    'total_area': sum(z.area for z in zones),
                    'total_population': sum(z.population for z in zones)
                }
        
        return perception
    
    def _get_network_info(self) -> dict[str, Any]:
        """获取道路网络信息。"""
        if not self.environment:
            return {}
        
        network = self.environment.road_network
        nodes = list(network.nodes.values())
        
        if not nodes:
            return {'nodes': 0, 'bounds': None}
        
        # 计算网络边界
        positions = [n.position for n in nodes]
        min_x = min(p.x for p in positions)
        max_x = max(p.x for p in positions)
        min_y = min(p.y for p in positions)
        max_y = max(p.y for p in positions)
        
        # 找到中心区域和边缘区域
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        
        return {
            'nodes': len(nodes),
            'edges': len(network.edges),
            'bounds': {'min_x': min_x, 'max_x': max_x, 'min_y': min_y, 'max_y': max_y},
            'center': {'x': center_x, 'y': center_y},
            'width': max_x - min_x,
            'height': max_y - min_y
        }
    
    def _get_city_stats(self) -> dict[str, Any]:
        """获取城市统计信息。"""
        stats = self.zone_manager.get_statistics()
        stats['can_add_more'] = stats['total_zones'] < self.max_zones
        stats['max_zones'] = self.max_zones
        return stats
    
    def _get_population_stats(self) -> dict[str, Any]:
        """获取人口统计信息。"""
        total_pop = self.zone_manager.get_total_population()
        
        # 计算需要的服务
        needed_services = self._analyze_service_needs()
        
        return {
            'total_population': total_pop,
            'needed_services': needed_services
        }
    
    def _analyze_service_needs(self) -> dict[str, Any]:
        """分析城市服务需求。"""
        needs = {}
        
        # 基于人口计算所需服务
        total_pop = self.zone_manager.get_total_population()
        
        # 学校需求: 每1000人需要1个学校区域
        schools = len(self.zone_manager.get_zones_by_type(ZoneType.SCHOOL))
        needed_schools = max(1, total_pop // 1000)
        if schools < needed_schools:
            needs['SCHOOL'] = {
                'current': schools,
                'needed': needed_schools,
                'priority': 'high'
            }
        
        # 医院需求: 每5000人需要1个医院
        hospitals = len(self.zone_manager.get_zones_by_type(ZoneType.HOSPITAL))
        needed_hospitals = max(1, total_pop // 5000)
        if hospitals < needed_hospitals:
            needs['HOSPITAL'] = {
                'current': hospitals,
                'needed': needed_hospitals,
                'priority': 'high'
            }
        
        # 公园需求: 每个住宅区附近应该有公园
        residential = len(self.zone_manager.get_zones_by_type(ZoneType.RESIDENTIAL))
        parks = len(self.zone_manager.get_zones_by_type(ZoneType.PARK))
        if parks < residential * 0.5:
            needs['PARK'] = {
                'current': parks,
                'needed': int(residential * 0.5),
                'priority': 'medium'
            }
        
        # 商业需求
        commercial = len(self.zone_manager.get_zones_by_type(ZoneType.COMMERCIAL))
        if commercial < residential * 0.3:
            needs['COMMERCIAL'] = {
                'current': commercial,
                'needed': int(residential * 0.3),
                'priority': 'medium'
            }
        
        return needs
    
    def decide(self) -> dict[str, Any] | None:
        """
        决策：决定是否需要规划新区域。
        
        Returns:
            规划决策字典，或None表示不规划
        """
        if not self.environment:
            return None
        
        current_time = self.environment.current_time
        
        # 检查规划间隔
        if current_time - self.last_planning_time < self.planning_interval:
            return None
        
        # 检查是否已达最大区域数
        if len(self.zone_manager.zones) >= self.max_zones:
            return None
        
        # 获取感知信息
        perception = self.perceive()
        
        # 分析需求
        needs = perception['population_stats']['needed_services']
        
        # 确定下一个要规划的区域类型
        zone_type = self._determine_next_zone_type(needs)
        if not zone_type:
            return None
        
        # 使用LLM或规则规划
        if self.use_llm:
            plan = self._llm_plan_zone(zone_type, perception)
        else:
            plan = self._rule_plan_zone(zone_type, perception)
        
        if plan:
            self.last_decision = plan
            
        return plan
    
    def _determine_next_zone_type(self, needs: dict[str, Any]) -> ZoneType | None:
        """确定下一个要规划的区域类型。"""
        # 首先满足高优先级需求
        for service, info in needs.items():
            if info.get('priority') == 'high':
                try:
                    return ZoneType[service]
                except KeyError:
                    continue
        
        # 然后满足中优先级需求
        for service, info in needs.items():
            if info.get('priority') == 'medium':
                try:
                    return ZoneType[service]
                except KeyError:
                    continue
        
        # 如果没有紧急需求，按优先级规划
        for zone_type in self.zone_priorities:
            existing = len(self.zone_manager.get_zones_by_type(zone_type))
            # 住宅区可以多一些
            if zone_type == ZoneType.RESIDENTIAL and existing < 5:
                return zone_type
            # 其他类型限制数量
            if existing < 2:
                return zone_type
        
        return None
    
    def _llm_plan_zone(
        self, 
        zone_type: ZoneType, 
        perception: dict[str, Any]
    ) -> dict[str, Any] | None:
        """使用LLM规划区域。"""
        try:
            network_info = perception['network_info']
            bounds = network_info.get('bounds', {})
            
            # 构建现有区域信息
            existing_zones = []
            for zone in self.zone_manager.zones.values():
                existing_zones.append({
                    'id': zone.zone_id,
                    'type': zone.zone_type.name,
                    'type_display': zone.zone_type.display_name,
                    'center': {'x': zone.center.x, 'y': zone.center.y},
                    'width': zone.width,
                    'height': zone.height,
                    'population': zone.population
                })
            
            # 构建提示
            prompt = f"""你是一位城市规划专家。请为城市规划一个新的功能区域。

## 规划目标
区域类型: {zone_type.display_name}
区域重要性: {zone_type.priority}

## 当前城市状态
- 总区域数: {perception['total_zones']}
- 道路网络范围: X[{bounds.get('min_x', 0):.0f}, {bounds.get('max_x', 0):.0f}], Y[{bounds.get('min_y', 0):.0f}, {bounds.get('max_y', 0):.0f}]
- 网络中心: ({network_info.get('center', {}).get('x', 0):.0f}, {network_info.get('center', {}).get('y', 0):.0f})

## 现有区域
{json.dumps(existing_zones[:8], ensure_ascii=False, indent=2)}

## 规划约束
1. **位置**: 区域应靠近道路网络，便于交通接入
2. **大小**: 宽度 {self.min_zone_size:.0f}-{self.max_zone_size:.0f}米, 高度 {self.min_zone_size:.0f}-{self.max_zone_size:.0f}米
3. **不重叠**: 新区域不应与现有区域重叠
4. **合理布局**: 
   - 住宅区应分散布置
   - 商业区宜集中或沿主干道
   - 医院和学校应服务尽可能多的人口
   - 公园应靠近住宅区
   - 工业区应远离住宅区

## 输出格式
请返回JSON格式决策:
{{
    "zone_type": "{zone_type.name}",
    "center_x": 中心x坐标（整数）,
    "center_y": 中心y坐标（整数）,
    "width": 宽度（整数，{self.min_zone_size:.0f}-{self.max_zone_size:.0f}）,
    "height": 高度（整数，{self.min_zone_size:.0f}-{self.max_zone_size:.0f}）,
    "name": "区域名称（中文）",
    "reasoning": "规划理由，包括位置选择和大小决定的说明"
}}
"""
            
            llm_manager = self._get_llm_manager()
            if llm_manager:
                response = llm_manager.request_sync_decision(prompt, timeout=15.0)
                if response:
                    return self._parse_llm_zone_plan(response, zone_type)
                    
        except Exception as e:
            print(f"[城市规划] LLM规划失败: {e}")
        
        # LLM失败，回退到规则
        return self._rule_plan_zone(zone_type, perception)
    
    def _parse_llm_zone_plan(
        self, 
        response: str, 
        default_type: ZoneType
    ) -> dict[str, Any] | None:
        """解析LLM的区域规划响应。"""
        try:
            # 提取JSON
            start = response.find('{')
            end = response.rfind('}')
            if start == -1 or end == -1:
                return None
            
            plan = json.loads(response[start:end+1])
            
            # 验证并提取参数
            center_x = float(plan.get('center_x', 0))
            center_y = float(plan.get('center_y', 0))
            width = max(self.min_zone_size, min(self.max_zone_size, 
                       float(plan.get('width', 100))))
            height = max(self.min_zone_size, min(self.max_zone_size, 
                        float(plan.get('height', 100))))
            
            return {
                'action': 'create_zone',
                'zone_type': default_type,
                'center': Vector2D(center_x, center_y),
                'width': width,
                'height': height,
                'name': plan.get('name', f'{default_type.name}_{len(self.zone_manager.zones)+1}'),
                'reasoning': plan.get('reasoning', 'LLM规划'),
                'is_llm': True
            }
            
        except Exception as e:
            print(f"[城市规划] 解析LLM响应失败: {e}")
            return None
    
    def _rule_plan_zone(
        self, 
        zone_type: ZoneType, 
        perception: dict[str, Any]
    ) -> dict[str, Any] | None:
        """使用规则规划区域。"""
        network_info = perception['network_info']
        bounds = network_info.get('bounds', {})
        
        if not bounds:
            return None
        
        min_x, max_x = bounds['min_x'], bounds['max_x']
        min_y, max_y = bounds['min_y'], bounds['max_y']
        center_x = network_info['center']['x']
        center_y = network_info['center']['y']
        
        # 根据区域类型确定最佳位置
        if zone_type == ZoneType.RESIDENTIAL:
            # 住宅区分散布置
            candidates = self._generate_residential_locations(
                min_x, max_x, min_y, max_y, center_x, center_y
            )
        elif zone_type == ZoneType.COMMERCIAL:
            # 商业区靠近中心或道路
            candidates = self._generate_commercial_locations(
                min_x, max_x, min_y, max_y, center_x, center_y
            )
        elif zone_type == ZoneType.HOSPITAL:
            # 医院靠近中心，服务全城
            candidates = self._generate_central_locations(
                min_x, max_x, min_y, max_y, center_x, center_y
            )
        elif zone_type == ZoneType.SCHOOL:
            # 学校靠近住宅区
            candidates = self._generate_school_locations(
                min_x, max_x, min_y, max_y, center_x, center_y
            )
        elif zone_type == ZoneType.PARK:
            # 公园靠近住宅区
            candidates = self._generate_park_locations(
                min_x, max_x, min_y, max_y, center_x, center_y
            )
        elif zone_type == ZoneType.INDUSTRIAL:
            # 工业区远离住宅区，靠近边缘
            candidates = self._generate_industrial_locations(
                min_x, max_x, min_y, max_y, center_x, center_y
            )
        else:
            # 默认：随机位置
            candidates = self._generate_default_locations(
                min_x, max_x, min_y, max_y
            )
        
        # 选择不重叠的位置
        width = random.uniform(80, 150)
        height = random.uniform(60, 120)
        
        for center in candidates:
            test_zone = Zone(zone_type, center, width, height)
            overlapping = self.zone_manager.check_overlap(test_zone)
            if not overlapping:
                return {
                    'action': 'create_zone',
                    'zone_type': zone_type,
                    'center': center,
                    'width': width,
                    'height': height,
                    'name': f'{zone_type.name}_{len(self.zone_manager.zones)+1}',
                    'reasoning': f'规则规划: 根据{zone_type.display_name}类型选择合适位置',
                    'is_llm': False
                }
        
        # 如果所有候选位置都重叠，尝试缩小尺寸
        width = 60
        height = 50
        for center in candidates[:3]:
            test_zone = Zone(zone_type, center, width, height)
            overlapping = self.zone_manager.check_overlap(test_zone)
            if not overlapping:
                return {
                    'action': 'create_zone',
                    'zone_type': zone_type,
                    'center': center,
                    'width': width,
                    'height': height,
                    'name': f'{zone_type.name}_{len(self.zone_manager.zones)+1}',
                    'reasoning': f'规则规划: 缩小尺寸后找到合适位置',
                    'is_llm': False
                }
        
        return None
    
    def _generate_residential_locations(
        self, min_x, max_x, min_y, max_y, center_x, center_y
    ) -> list[Vector2D]:
        """生成住宅区的候选位置。"""
        candidates = []
        # 在多个位置生成候选点
        for _ in range(5):
            # 倾向于分散布置
            x = random.uniform(min_x + 50, max_x - 50)
            y = random.uniform(min_y + 50, max_y - 50)
            candidates.append(Vector2D(x, y))
        
        # 按距离现有住宅区的距离排序（越远越好）
        existing_res = self.zone_manager.get_zones_by_type(ZoneType.RESIDENTIAL)
        if existing_res:
            candidates.sort(
                key=lambda p: min(p.distance_to(r.center) for r in existing_res),
                reverse=True
            )
        
        return candidates
    
    def _generate_commercial_locations(
        self, min_x, max_x, min_y, max_y, center_x, center_y
    ) -> list[Vector2D]:
        """生成商业区的候选位置。"""
        candidates = []
        # 靠近中心
        candidates.append(Vector2D(center_x, center_y))
        # 几个偏离中心的点
        for _ in range(4):
            x = center_x + random.uniform(-200, 200)
            y = center_y + random.uniform(-200, 200)
            candidates.append(Vector2D(
                max(min_x + 50, min(max_x - 50, x)),
                max(min_y + 50, min(max_y - 50, y))
            ))
        return candidates
    
    def _generate_central_locations(
        self, min_x, max_x, min_y, max_y, center_x, center_y
    ) -> list[Vector2D]:
        """生成中心区域位置（医院等）。"""
        candidates = [Vector2D(center_x, center_y)]
        # 周围几个点
        for angle in [0, 90, 180, 270]:
            rad = angle * 3.14159 / 180
            dist = 100
            x = center_x + dist * cos(rad)
            y = center_y + dist * sin(rad)
            candidates.append(Vector2D(
                max(min_x + 50, min(max_x - 50, x)),
                max(min_y + 50, min(max_y - 50, y))
            ))
        return candidates
    
    def _generate_school_locations(
        self, min_x, max_x, min_y, max_y, center_x, center_y
    ) -> list[Vector2D]:
        """生成学校的候选位置。"""
        candidates = []
        # 优先靠近住宅区
        residential = self.zone_manager.get_zones_by_type(ZoneType.RESIDENTIAL)
        if residential:
            for res in residential[:3]:
                # 在住宅区附近找一个点
                x = res.center.x + random.uniform(-100, 100)
                y = res.center.y + random.uniform(-100, 100)
                candidates.append(Vector2D(
                    max(min_x + 50, min(max_x - 50, x)),
                    max(min_y + 50, min(max_y - 50, y))
                ))
        
        # 补充一些随机点
        while len(candidates) < 5:
            candidates.append(Vector2D(
                random.uniform(min_x + 50, max_x - 50),
                random.uniform(min_y + 50, max_y - 50)
            ))
        
        return candidates
    
    def _generate_park_locations(
        self, min_x, max_x, min_y, max_y, center_x, center_y
    ) -> list[Vector2D]:
        """生成公园的候选位置。"""
        # 类似学校，靠近住宅区
        return self._generate_school_locations(min_x, max_x, min_y, max_y, center_x, center_y)
    
    def _generate_industrial_locations(
        self, min_x, max_x, min_y, max_y, center_x, center_y
    ) -> list[Vector2D]:
        """生成工业区的候选位置。"""
        candidates = []
        # 选择远离中心的边缘位置
        edges = [
            Vector2D(min_x + 100, center_y),  # 左边
            Vector2D(max_x - 100, center_y),  # 右边
            Vector2D(center_x, min_y + 100),  # 下边
            Vector2D(center_x, max_y - 100),  # 上边
        ]
        
        # 选择距离住宅区最远的
        residential = self.zone_manager.get_zones_by_type(ZoneType.RESIDENTIAL)
        if residential:
            edges.sort(
                key=lambda p: min(p.distance_to(r.center) for r in residential),
                reverse=True
            )
        
        return edges
    
    def _generate_default_locations(
        self, min_x, max_x, min_y, max_y
    ) -> list[Vector2D]:
        """生成默认候选位置。"""
        return [
            Vector2D(random.uniform(min_x + 50, max_x - 50),
                    random.uniform(min_y + 50, max_y - 50))
            for _ in range(5)
        ]
    
    def _get_llm_manager(self):
        """获取LLM管理器。"""
        try:
            from city.llm.llm_manager import get_llm_manager
            return get_llm_manager()
        except:
            return None
    
    def act(self, decision: dict[str, Any] | None) -> bool:
        """执行区域规划。"""
        if not decision or not self.environment:
            return False
        
        action = decision.get('action')
        if action != 'create_zone':
            return False
        
        try:
            zone_type = decision['zone_type']
            center = decision['center']
            width = decision['width']
            height = decision['height']
            name = self.zone_manager.next_zone_name(zone_type)
            
            # 创建区域
            zone = Zone(
                zone_type=zone_type,
                center=center,
                width=width,
                height=height,
                name=name
            )
            
            # 检查重叠
            overlapping = self.zone_manager.check_overlap(zone)
            if overlapping:
                print(f"[城市规划] 区域 {name} 与现有区域重叠，调整位置")
                # 尝试稍微调整位置
                for offset_x in [-30, 30, -60, 60]:
                    for offset_y in [-30, 30, -60, 60]:
                        adjusted_center = Vector2D(center.x + offset_x, center.y + offset_y)
                        test_zone = Zone(zone_type, adjusted_center, width, height, name)
                        if not self.zone_manager.check_overlap(test_zone):
                            zone = test_zone
                            break
                    else:
                        continue
                    break
                else:
                    print(f"[城市规划] 无法找到不重叠的位置，跳过")
                    return False
            
            # 连接到最近的节点
            if self.environment.road_network.nodes:
                nearest_node = min(
                    self.environment.road_network.nodes.values(),
                    key=lambda n: zone.distance_to_node(n)
                )
                zone.connect_to_node(nearest_node)
            
            # 添加到管理器
            zone.planning_time = self.environment.current_time
            zone.planned_by = "LLM" if decision.get('is_llm', False) else "Rule"
            zone.planning_reason = decision.get('reasoning', '')
            
            # 设置初始目标人口
            zone.target_population = int(zone.max_population * random.uniform(0.3, 0.7))
            
            self.zone_manager.add_zone(zone)
            name = zone.name
            decision['name'] = name
            self.last_planning_time = self.environment.current_time
            
            # 记录历史
            self.planning_history.append({
                'time': self.environment.current_time,
                'zone_id': zone.zone_id,
                'zone_type': zone_type.name,
                'name': name,
                'center': {'x': center.x, 'y': center.y},
                'area': zone.area,
                'decision': decision
            })
            
            print(f"[城市规划] 新增区域: {name} ({zone_type.display_name}), "
                  f"面积: {zone.area:.0f}m², 预计人口: {zone.target_population}")
            
            return True
            
        except Exception as e:
            print(f"[城市规划] 创建区域失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def update(self, dt: float) -> None:
        """更新规划智能体状态。"""
        if not self.environment:
            return
        
        current_time = self.environment.current_time
        
        # 定期执行规划
        check_interval = 10
        if int(current_time) % check_interval == 0 and int(current_time) > 0:
            if not hasattr(self, '_last_planning_check') or self._last_planning_check != int(current_time):
                self._last_planning_check = int(current_time)
                
                # 检查是否需要规划
                decision = self.decide()
                if decision:
                    success = self.act(decision)
                    if success:
                        stats = self.zone_manager.get_statistics()
                        print(f"[城市规划] 当前共有 {stats['total_zones']} 个区域, "
                              f"总人口: {stats['total_population']}")
        
        # 更新区域人口增长
        for zone in self.zone_manager.zones.values():
            if zone.population < zone.target_population:
                zone.grow_population(0.005)  # 缓慢增长
    
    def get_status(self) -> dict[str, Any]:
        """获取规划智能体状态。"""
        return {
            'agent_id': self.agent_id,
            'total_zones': len(self.zone_manager.zones),
            'zone_stats': self.zone_manager.get_statistics(),
            'planning_history_count': len(self.planning_history),
            'last_planning_time': self.last_planning_time,
            'max_zones': self.max_zones,
            'last_decision': self.last_decision
        }
    
    def get_all_zones(self) -> list[dict[str, Any]]:
        """获取所有区域信息。"""
        return self.zone_manager.to_list()


# 导入math函数
from math import cos, sin
