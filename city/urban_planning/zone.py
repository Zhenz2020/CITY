"""
城市功能区域模块。

定义城市中的功能区域类型和区域类。
"""

from __future__ import annotations

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from city.utils.vector import Vector2D

if TYPE_CHECKING:
    from city.environment.road_network import Node


class ZoneType(Enum):
    """城市功能区域类型。"""
    
    RESIDENTIAL = auto()      # 住宅区
    COMMERCIAL = auto()       # 商业区
    INDUSTRIAL = auto()       # 工业区
    HOSPITAL = auto()         # 医院
    SCHOOL = auto()           # 学校
    PARK = auto()             # 公园/绿地
    OFFICE = auto()           # 办公区
    MIXED_USE = auto()        # 混合用途
    GOVERNMENT = auto()       # 政府机构
    SHOPPING = auto()         # 购物中心
    
    # 颜色映射 (用于可视化)
    @property
    def color(self) -> str:
        """获取区域类型的显示颜色。"""
        colors = {
            ZoneType.RESIDENTIAL: '#E3F2FD',    # 浅蓝 - 住宅
            ZoneType.COMMERCIAL: '#FFE0B2',     # 浅橙 - 商业
            ZoneType.INDUSTRIAL: '#CFD8DC',     # 灰蓝 - 工业
            ZoneType.HOSPITAL: '#FFCDD2',       # 浅红 - 医院
            ZoneType.SCHOOL: '#C8E6C9',         # 浅绿 - 学校
            ZoneType.PARK: '#B9F6CA',           # 薄荷绿 - 公园
            ZoneType.OFFICE: '#D1C4E9',         # 浅紫 - 办公
            ZoneType.MIXED_USE: '#F8BBD9',      # 粉色 - 混合
            ZoneType.GOVERNMENT: '#B2DFDB',     # 青绿 - 政府
            ZoneType.SHOPPING: '#FFECB3',       # 浅黄 - 购物
        }
        return colors.get(self, '#F5F5F5')
    
    @property
    def border_color(self) -> str:
        """获取区域类型的边框颜色。"""
        borders = {
            ZoneType.RESIDENTIAL: '#1976D2',    # 深蓝
            ZoneType.COMMERCIAL: '#F57C00',     # 深橙
            ZoneType.INDUSTRIAL: '#455A64',     # 深灰
            ZoneType.HOSPITAL: '#D32F2F',       # 深红
            ZoneType.SCHOOL: '#388E3C',         # 深绿
            ZoneType.PARK: '#2E7D32',           # 深绿
            ZoneType.OFFICE: '#512DA8',         # 深紫
            ZoneType.MIXED_USE: '#C2185B',      # 深粉
            ZoneType.GOVERNMENT: '#00796B',     # 深青
            ZoneType.SHOPPING: '#FFA000',       # 深黄
        }
        return borders.get(self, '#757575')
    
    @property
    def display_name(self) -> str:
        """获取区域类型的中文显示名称。"""
        names = {
            ZoneType.RESIDENTIAL: '住宅区',
            ZoneType.COMMERCIAL: '商业区',
            ZoneType.INDUSTRIAL: '工业区',
            ZoneType.HOSPITAL: '医院',
            ZoneType.SCHOOL: '学校',
            ZoneType.PARK: '公园',
            ZoneType.OFFICE: '办公区',
            ZoneType.MIXED_USE: '混合区',
            ZoneType.GOVERNMENT: '政府',
            ZoneType.SHOPPING: '购物中心',
        }
        return names.get(self, '未知')
    
    @property
    def priority(self) -> int:
        """获取区域优先级（用于规划顺序）。"""
        priorities = {
            ZoneType.RESIDENTIAL: 1,     # 高优先级
            ZoneType.SCHOOL: 2,
            ZoneType.HOSPITAL: 3,
            ZoneType.COMMERCIAL: 4,
            ZoneType.SHOPPING: 5,
            ZoneType.OFFICE: 6,
            ZoneType.INDUSTRIAL: 7,
            ZoneType.GOVERNMENT: 8,
            ZoneType.MIXED_USE: 9,
            ZoneType.PARK: 10,           # 低优先级但重要
        }
        return priorities.get(self, 5)
    
    @property
    def min_size(self) -> float:
        """获取区域最小尺寸（平方米）。"""
        sizes = {
            ZoneType.RESIDENTIAL: 5000,   # 100m x 50m
            ZoneType.COMMERCIAL: 3000,    # 60m x 50m
            ZoneType.INDUSTRIAL: 10000,   # 200m x 50m
            ZoneType.HOSPITAL: 4000,      # 80m x 50m
            ZoneType.SCHOOL: 6000,        # 120m x 50m
            ZoneType.PARK: 2000,          # 40m x 50m
            ZoneType.OFFICE: 4000,        # 80m x 50m
            ZoneType.MIXED_USE: 6000,     # 120m x 50m
            ZoneType.GOVERNMENT: 3000,    # 60m x 50m
            ZoneType.SHOPPING: 5000,      # 100m x 50m
        }
        return sizes.get(self, 3000)
    
    @property
    def population_capacity(self) -> int:
        """获取区域人口容量（每1000平方米）。"""
        capacities = {
            ZoneType.RESIDENTIAL: 50,     # 高密度住宅
            ZoneType.COMMERCIAL: 20,      # 商业
            ZoneType.INDUSTRIAL: 10,      # 工业
            ZoneType.HOSPITAL: 30,        # 医院（工作人员+患者）
            ZoneType.SCHOOL: 100,         # 学校（学生+教职工）
            ZoneType.PARK: 5,             # 公园
            ZoneType.OFFICE: 40,          # 办公
            ZoneType.MIXED_USE: 35,       # 混合
            ZoneType.GOVERNMENT: 25,      # 政府
            ZoneType.SHOPPING: 25,        # 购物
        }
        return capacities.get(self, 20)


@dataclass
class ZoneRequirement:
    """区域规划需求。"""
    
    zone_type: ZoneType
    min_area: float = 0.0
    preferred_location: Vector2D | None = None
    max_distance_to_road: float = 100.0  # 最大距离道路的距离
    noise_sensitive: bool = False        # 是否对噪音敏感
    requires_services: list[str] = field(default_factory=list)  # 需要的服务
    
    def __post_init__(self):
        if self.min_area <= 0:
            self.min_area = self.zone_type.min_size


class Zone:
    """
    城市功能区域。
    
    表示城市中的一个功能区域，具有位置、大小、类型等属性。
    
    Attributes:
        zone_id: 区域唯一标识
        zone_type: 区域类型
        center: 中心位置
        width: 宽度
        height: 高度
        population: 当前人口
        max_population: 最大人口容量
        buildings: 建筑列表
        connected_nodes: 连接的节点（用于交通）
        development_level: 开发程度 (0.0 - 1.0)
    """
    
    _zone_counter = 0
    
    def __init__(
        self,
        zone_type: ZoneType,
        center: Vector2D,
        width: float,
        height: float,
        name: str | None = None,
        connected_nodes: list[Node] | None = None
    ):
        Zone._zone_counter += 1
        self.zone_id = f"zone_{Zone._zone_counter}"
        self.zone_type = zone_type
        self.center = center
        self.width = width
        self.height = height
        self.name = name or f"{zone_type.display_name}_{Zone._zone_counter}"
        
        # 人口管理
        area = width * height
        self.max_population = int(area / 1000 * zone_type.population_capacity)
        self.population = 0
        self.target_population = 0  # 目标人口（用于逐步填充）
        
        # 开发状态
        self.development_level = 0.0
        self.buildings: list[dict[str, Any]] = []
        self.services: list[str] = []
        
        # 连接性
        self.connected_nodes = connected_nodes or []
        
        # 规划信息
        self.planning_time: float | None = None
        self.planned_by: str = ""
        self.planning_reason: str = ""
        
    @property
    def area(self) -> float:
        """获取区域面积。"""
        return self.width * self.height
    
    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """
        获取区域边界 (min_x, min_y, max_x, max_y)。
        """
        half_width = self.width / 2
        half_height = self.height / 2
        return (
            self.center.x - half_width,
            self.center.y - half_height,
            self.center.x + half_width,
            self.center.y + half_height
        )
    
    @property
    def corners(self) -> list[Vector2D]:
        """获取四个角点坐标。"""
        min_x, min_y, max_x, max_y = self.bounds
        return [
            Vector2D(min_x, min_y),
            Vector2D(max_x, min_y),
            Vector2D(max_x, max_y),
            Vector2D(min_x, max_y)
        ]
    
    def contains_point(self, point: Vector2D) -> bool:
        """检查点是否在区域内。"""
        min_x, min_y, max_x, max_y = self.bounds
        return min_x <= point.x <= max_x and min_y <= point.y <= max_y
    
    def intersects_with(self, other: Zone, buffer: float = 5.0) -> bool:
        """
        检查是否与其他区域相交。
        
        Args:
            other: 另一个区域
            buffer: 缓冲距离（防止区域过于接近）
        """
        min_x1, min_y1, max_x1, max_y1 = self.bounds
        min_x2, min_y2, max_x2, max_y2 = other.bounds
        
        # 扩展缓冲
        min_x1 -= buffer
        min_y1 -= buffer
        max_x1 += buffer
        max_y1 += buffer
        
        return not (
            max_x1 < min_x2 or max_x2 < min_x1 or
            max_y1 < min_y2 or max_y2 < min_y1
        )
    
    def distance_to_node(self, node: Node) -> float:
        """计算到节点的距离。"""
        return self.center.distance_to(node.position)
    
    def distance_to_zone(self, other: Zone) -> float:
        """计算到另一个区域的中心距离。"""
        return self.center.distance_to(other.center)
    
    def add_building(self, building_type: str, size: float) -> None:
        """添加建筑。"""
        self.buildings.append({
            'type': building_type,
            'size': size,
            'built_at': None  # 将在仿真中设置
        })
        self._update_development()
    
    def add_service(self, service: str) -> None:
        """添加服务设施。"""
        if service not in self.services:
            self.services.append(service)
    
    def set_population(self, population: int) -> None:
        """设置人口数量。"""
        self.population = max(0, min(population, self.max_population))
        self._update_development()
    
    def grow_population(self, growth_rate: float = 0.01) -> int:
        """
        人口增长。
        
        Returns:
            新增人口数
        """
        if self.population < self.target_population:
            growth = max(1, int(self.max_population * growth_rate))
            old_pop = self.population
            self.population = min(self.population + growth, self.target_population)
            return self.population - old_pop
        return 0
    
    def _update_development(self) -> None:
        """更新开发程度。"""
        # 基于人口和建筑计算开发程度
        pop_ratio = self.population / max(1, self.max_population)
        building_ratio = min(1.0, len(self.buildings) / 10)  # 假设10个建筑为满
        self.development_level = (pop_ratio + building_ratio) / 2
    
    def connect_to_node(self, node: Node) -> None:
        """连接到道路节点。"""
        if node not in self.connected_nodes:
            self.connected_nodes.append(node)
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典表示。"""
        return {
            'zone_id': self.zone_id,
            'zone_type': self.zone_type.name,
            'zone_type_display': self.zone_type.display_name,
            'name': self.name,
            'center': {'x': self.center.x, 'y': self.center.y},
            'width': self.width,
            'height': self.height,
            'area': self.area,
            'color': self.zone_type.color,
            'border_color': self.zone_type.border_color,
            'population': self.population,
            'max_population': self.max_population,
            'development_level': self.development_level,
            'buildings_count': len(self.buildings),
            'services': self.services,
            'connected_nodes': [n.node_id for n in self.connected_nodes],
            'bounds': self.bounds,
            'planning_time': self.planning_time,
            'planning_reason': self.planning_reason
        }
    
    def __repr__(self) -> str:
        return f"Zone({self.name}, {self.zone_type.display_name}, pop:{self.population}/{self.max_population})"


class ZoneManager:
    """
    区域管理器。
    
    管理城市中所有功能区域。
    """
    
    def __init__(self):
        self.zones: dict[str, Zone] = {}
        self._zones_by_type: dict[ZoneType, list[Zone]] = {}
        
    def add_zone(self, zone: Zone) -> None:
        """添加区域。"""
        self.zones[zone.zone_id] = zone
        
        if zone.zone_type not in self._zones_by_type:
            self._zones_by_type[zone.zone_type] = []
        self._zones_by_type[zone.zone_type].append(zone)
    
    def remove_zone(self, zone_id: str) -> Zone | None:
        """移除区域。"""
        zone = self.zones.pop(zone_id, None)
        if zone and zone.zone_type in self._zones_by_type:
            self._zones_by_type[zone.zone_type].remove(zone)
        return zone
    
    def get_zone(self, zone_id: str) -> Zone | None:
        """获取区域。"""
        return self.zones.get(zone_id)
    
    def get_zones_by_type(self, zone_type: ZoneType) -> list[Zone]:
        """获取指定类型的所有区域。"""
        return self._zones_by_type.get(zone_type, []).copy()
    
    def find_zones_at(self, point: Vector2D) -> list[Zone]:
        """查找包含该点的所有区域。"""
        return [z for z in self.zones.values() if z.contains_point(point)]
    
    def find_nearest_zone(self, point: Vector2D, zone_type: ZoneType | None = None) -> Zone | None:
        """查找最近的区域。"""
        zones = (self.zones.values() if zone_type is None 
                else self._zones_by_type.get(zone_type, []))
        
        if not zones:
            return None
        
        return min(zones, key=lambda z: z.center.distance_to(point))
    
    def check_overlap(self, new_zone: Zone, exclude_id: str | None = None) -> list[Zone]:
        """检查新区域与哪些现有区域重叠。"""
        overlapping = []
        for zone in self.zones.values():
            if exclude_id and zone.zone_id == exclude_id:
                continue
            if zone.intersects_with(new_zone):
                overlapping.append(zone)
        return overlapping
    
    def get_total_population(self) -> int:
        """获取总人口。"""
        return sum(z.population for z in self.zones.values())
    
    def get_total_area(self) -> float:
        """获取总规划面积。"""
        return sum(z.area for z in self.zones.values())
    
    def get_statistics(self) -> dict[str, Any]:
        """获取统计信息。"""
        stats = {
            'total_zones': len(self.zones),
            'total_population': self.get_total_population(),
            'total_area': self.get_total_area(),
            'by_type': {}
        }
        
        for zone_type, zones in self._zones_by_type.items():
            stats['by_type'][zone_type.name] = {
                'count': len(zones),
                'total_area': sum(z.area for z in zones),
                'total_population': sum(z.population for z in zones)
            }
        
        return stats
    
    def to_list(self) -> list[dict[str, Any]]:
        """转换为列表。"""
        return [z.to_dict() for z in self.zones.values()]
