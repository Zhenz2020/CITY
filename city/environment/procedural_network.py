"""
仿照 procedural_city_generation 的路网生成器。

基于生长规则（Grid/Organic/Radial）的自然城市路网生成。
"""

from __future__ import annotations

import math
import random
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

from city.environment.road_network import RoadNetwork, Node, Edge
from city.utils.vector import Vector2D

if TYPE_CHECKING:
    from city.simulation.environment import SimulationEnvironment


class GrowthRule(Enum):
    """路网生长规则类型。"""
    GRID = auto()       # 网格状 - 正交道路
    ORGANIC = auto()    # 有机状 - 自然弯曲
    RADIAL = auto()     # 放射状 - 围绕中心


class RoadGrowthConfig:
    """道路生长配置参数。"""
    
    def __init__(
        self,
        # Grid 参数
        grid_forward_prob: float = 0.95,      # 直行概率
        grid_turn_prob: float = 0.25,         # 转弯概率
        grid_length_min: float = 180.0,       # 最小长度
        grid_length_max: float = 250.0,       # 最大长度
        
        # Organic 参数
        organic_forward_prob: float = 0.90,
        organic_turn_prob: float = 0.20,
        organic_length_min: float = 150.0,
        organic_length_max: float = 300.0,
        organic_angle_variation: float = 35.0,  # 角度变化范围
        
        # Radial 参数
        radial_forward_prob: float = 0.95,
        radial_turn_prob: float = 0.15,
        radial_length_min: float = 180.0,
        radial_length_max: float = 280.0,
        
        # 通用参数
        min_node_distance: float = 80.0,      # 节点最小间距
        max_iterations: int = 100,            # 最大迭代次数
        snap_threshold: float = 50.0,         # 吸附阈值
    ):
        self.grid_forward_prob = grid_forward_prob
        self.grid_turn_prob = grid_turn_prob
        self.grid_length_min = grid_length_min
        self.grid_length_max = grid_length_max
        
        self.organic_forward_prob = organic_forward_prob
        self.organic_turn_prob = organic_turn_prob
        self.organic_length_min = organic_length_min
        self.organic_length_max = organic_length_max
        self.organic_angle_variation = organic_angle_variation
        
        self.radial_forward_prob = radial_forward_prob
        self.radial_turn_prob = radial_turn_prob
        self.radial_length_min = radial_length_min
        self.radial_length_max = radial_length_max
        
        self.min_node_distance = min_node_distance
        self.max_iterations = max_iterations
        self.snap_threshold = snap_threshold


class GrowthNode:
    """生长节点，用于路网生成过程中的临时表示。"""
    
    def __init__(self, position: Vector2D, parent: GrowthNode | None = None):
        self.position = position
        self.parent = parent
        self.neighbors: list[GrowthNode] = []
        self.is_seed: bool = False          # 是否为种子点（可产生支路）
        self.is_minor: bool = False         # 是否为小路
        self.iteration: int = 0             # 创建时的迭代次数
        
    def add_neighbor(self, other: GrowthNode) -> None:
        """添加邻居。"""
        if other not in self.neighbors:
            self.neighbors.append(other)
        if self not in other.neighbors:
            other.neighbors.append(self)


class ProceduralRoadGenerator:
    """
    仿照 procedural_city_generation 的路网生成器。
    
    使用生长规则（Grid/Organic/Radial）从初始种子生成自然城市路网。
    """
    
    def __init__(
        self,
        config: RoadGrowthConfig | None = None,
        default_rule: GrowthRule = GrowthRule.GRID,
        city_center: Vector2D | None = None,
        boundary: tuple[float, float, float, float] = (-1000, -1000, 1000, 1000)
    ):
        self.config = config or RoadGrowthConfig()
        self.default_rule = default_rule
        self.city_center = city_center or Vector2D(0, 0)
        self.boundary = boundary  # (min_x, min_y, max_x, max_y)
        
        # 生长状态
        self.front: list[GrowthNode] = []      # 当前生长前沿
        self.all_nodes: list[GrowthNode] = []  # 所有节点
        self.iteration: int = 0
        
    def _is_in_boundary(self, pos: Vector2D) -> bool:
        """检查位置是否在边界内。"""
        min_x, min_y, max_x, max_y = self.boundary
        return min_x <= pos.x <= max_x and min_y <= pos.y <= max_y
    
    def _is_too_close(self, pos: Vector2D, exclude: GrowthNode | None = None) -> bool:
        """检查位置是否离现有节点太近。"""
        for node in self.all_nodes:
            if node is exclude:
                continue
            if pos.distance_to(node.position) < self.config.min_node_distance:
                return True
        return False
    
    def _find_nearby_node(self, pos: Vector2D, threshold: float | None = None) -> GrowthNode | None:
        """查找附近的现有节点。"""
        threshold = threshold or self.config.snap_threshold
        for node in self.all_nodes:
            if pos.distance_to(node.position) < threshold:
                return node
        return None
    
    def _get_direction(self, node: GrowthNode) -> Vector2D:
        """获取节点的生长方向（从父节点指向当前节点）。"""
        if node.parent is None:
            # 初始节点，随机方向
            angle = random.uniform(0, 2 * math.pi)
            return Vector2D(math.cos(angle), math.sin(angle))
        
        dir_vec = node.position - node.parent.position
        length = dir_vec.magnitude()
        if length < 0.001:
            return Vector2D(1, 0)
        return Vector2D(dir_vec.x / length, dir_vec.y / length)
    
    def _rotate_vector(self, vec: Vector2D, angle_deg: float) -> Vector2D:
        """旋转向量（角度制）。"""
        angle_rad = math.radians(angle_deg)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        return Vector2D(
            vec.x * cos_a - vec.y * sin_a,
            vec.x * sin_a + vec.y * cos_a
        )
    
    def _get_rule_at_position(self, pos: Vector2D) -> GrowthRule:
        """根据位置获取生长规则（可扩展为基于图片）。"""
        # 简单策略：根据距离中心的距离选择规则
        dist_to_center = pos.distance_to(self.city_center)
        
        # 中心区域使用放射状，外围使用网格状
        if dist_to_center < 300:
            return GrowthRule.RADIAL
        elif random.random() < 0.3:
            return GrowthRule.ORGANIC
        else:
            return GrowthRule.GRID
    
    def _generate_grid_suggestions(self, node: GrowthNode) -> list[GrowthNode]:
        """生成网格状生长建议。"""
        suggestions = []
        direction = self._get_direction(node)
        config = self.config
        
        # 直行
        if random.random() < config.grid_forward_prob:
            length = random.uniform(config.grid_length_min, config.grid_length_max)
            new_pos = node.position + direction * length
            if self._is_in_boundary(new_pos):
                suggestions.append(GrowthNode(new_pos, node))
        
        # 右转 (90度)
        if random.random() < config.grid_turn_prob:
            length = random.uniform(config.grid_length_min, config.grid_length_max)
            right_dir = self._rotate_vector(direction, 90)
            new_pos = node.position + right_dir * length
            if self._is_in_boundary(new_pos):
                new_node = GrowthNode(new_pos, node)
                new_node.is_seed = True  # 转弯点成为种子
                suggestions.append(new_node)
        
        # 左转 (90度)
        if random.random() < config.grid_turn_prob:
            length = random.uniform(config.grid_length_min, config.grid_length_max)
            left_dir = self._rotate_vector(direction, -90)
            new_pos = node.position + left_dir * length
            if self._is_in_boundary(new_pos):
                new_node = GrowthNode(new_pos, node)
                new_node.is_seed = True
                suggestions.append(new_node)
        
        return suggestions
    
    def _generate_organic_suggestions(self, node: GrowthNode) -> list[GrowthNode]:
        """生成有机状生长建议。"""
        suggestions = []
        direction = self._get_direction(node)
        config = self.config
        
        # 直行（带随机角度变化）
        if random.random() < config.organic_forward_prob:
            angle = random.uniform(-config.organic_angle_variation, config.organic_angle_variation)
            new_dir = self._rotate_vector(direction, angle)
            length = random.uniform(config.organic_length_min, config.organic_length_max)
            new_pos = node.position + new_dir * length
            if self._is_in_boundary(new_pos):
                suggestions.append(GrowthNode(new_pos, node))
        
        # 右转 (60-120度随机)
        if random.random() < config.organic_turn_prob:
            angle = random.uniform(60, 120)
            new_dir = self._rotate_vector(direction, angle)
            length = random.uniform(config.organic_length_min, config.organic_length_max)
            new_pos = node.position + new_dir * length
            if self._is_in_boundary(new_pos):
                new_node = GrowthNode(new_pos, node)
                new_node.is_seed = True
                suggestions.append(new_node)
        
        # 左转 (60-120度随机)
        if random.random() < config.organic_turn_prob:
            angle = random.uniform(-120, -60)
            new_dir = self._rotate_vector(direction, angle)
            length = random.uniform(config.organic_length_min, config.organic_length_max)
            new_pos = node.position + new_dir * length
            if self._is_in_boundary(new_pos):
                new_node = GrowthNode(new_pos, node)
                new_node.is_seed = True
                suggestions.append(new_node)
        
        return suggestions
    
    def _generate_radial_suggestions(self, node: GrowthNode) -> list[GrowthNode]:
        """生成放射状生长建议。"""
        suggestions = []
        config = self.config
        
        # 计算径向方向（从中心指向当前节点）
        radial_dir = node.position - self.city_center
        radial_length = radial_dir.magnitude()
        if radial_length < 0.001:
            radial_dir = Vector2D(1, 0)
        else:
            radial_dir = Vector2D(radial_dir.x / radial_length, radial_dir.y / radial_length)
        
        # 获取当前行进方向
        prev_dir = self._get_direction(node)
        
        # 根据与径向的夹角调整方向
        angle_to_radial = math.degrees(math.atan2(
            prev_dir.x * radial_dir.y - prev_dir.y * radial_dir.x,
            prev_dir.x * radial_dir.x + prev_dir.y * radial_dir.y
        ))
        
        # 调整为与径向平行或垂直
        if 45 <= abs(angle_to_radial) < 135:
            # 接近垂直，转为平行
            adjustment = 90 if angle_to_radial > 0 else -90
            base_dir = self._rotate_vector(prev_dir, adjustment)
        else:
            base_dir = prev_dir
        
        # 直行
        if random.random() < config.radial_forward_prob:
            length = random.uniform(config.radial_length_min, config.radial_length_max)
            new_pos = node.position + base_dir * length
            if self._is_in_boundary(new_pos):
                suggestions.append(GrowthNode(new_pos, node))
        
        # 右转 (90度，产生环形路)
        if random.random() < config.radial_turn_prob:
            length = random.uniform(config.radial_length_min, config.radial_length_max)
            new_dir = self._rotate_vector(base_dir, 90)
            new_pos = node.position + new_dir * length
            if self._is_in_boundary(new_pos):
                new_node = GrowthNode(new_pos, node)
                new_node.is_seed = True
                suggestions.append(new_node)
        
        # 左转
        if random.random() < config.radial_turn_prob:
            length = random.uniform(config.radial_length_min, config.radial_length_max)
            new_dir = self._rotate_vector(base_dir, -90)
            new_pos = node.position + new_dir * length
            if self._is_in_boundary(new_pos):
                new_node = GrowthNode(new_pos, node)
                new_node.is_seed = True
                suggestions.append(new_node)
        
        return suggestions
    
    def _generate_suggestions(self, node: GrowthNode) -> list[GrowthNode]:
        """根据规则生成生长建议。"""
        rule = self._get_rule_at_position(node.position)
        
        if rule == GrowthRule.GRID:
            return self._generate_grid_suggestions(node)
        elif rule == GrowthRule.ORGANIC:
            return self._generate_organic_suggestions(node)
        elif rule == GrowthRule.RADIAL:
            return self._generate_radial_suggestions(node)
        
        return []
    
    def _check_and_connect(self, new_node: GrowthNode, parent: GrowthNode, new_front: list[GrowthNode]) -> list[GrowthNode]:
        """检查新节点并建立连接。"""
        # 检查是否太近
        if self._is_too_close(new_node.position, exclude=parent):
            # 尝试吸附到附近节点
            nearby = self._find_nearby_node(new_node.position)
            if nearby and nearby is not parent:
                parent.add_neighbor(nearby)
            return new_front
        
        # 检查是否可以吸附到现有节点
        nearby = self._find_nearby_node(new_node.position)
        if nearby:
            parent.add_neighbor(nearby)
            return new_front
        
        # 添加为新节点
        parent.add_neighbor(new_node)
        self.all_nodes.append(new_node)
        new_node.iteration = self.iteration
        new_front.append(new_node)
        
        return new_front
    
    def generate(
        self,
        num_seed_points: int = 4,
        iterations: int | None = None
    ) -> RoadNetwork:
        """
        生成路网。
        
        Args:
            num_seed_points: 初始种子点数量（十字形布局）
            iterations: 迭代次数，None 使用配置值
            
        Returns:
            生成的道路网络
        """
        iterations = iterations or self.config.max_iterations
        
        # 创建初始种子点（十字形布局，类似 procedural_city_generation）
        self._create_initial_seeds(num_seed_points)
        
        # 迭代生长
        for i in range(iterations):
            if not self.front:
                break
            
            self.iteration = i
            new_front: list[GrowthNode] = []
            
            for node in self.front:
                suggestions = self._generate_suggestions(node)
                for suggested_node in suggestions:
                    new_front = self._check_and_connect(suggested_node, node, new_front)
            
            self.front = new_front
        
        # 转换为 RoadNetwork
        return self._build_road_network()
    
    def _create_initial_seeds(self, num_directions: int = 4) -> None:
        """创建初始种子点（十字形或放射形）。"""
        self.all_nodes = []
        self.front = []
        
        # 基础间距
        base_distance = 200.0
        
        # 创建十字形初始种子（4个方向）
        directions = [
            Vector2D(1, 0),   # 东
            Vector2D(-1, 0),  # 西
            Vector2D(0, 1),   # 南
            Vector2D(0, -1),  # 北
        ]
        
        for i, direction in enumerate(directions[:num_directions]):
            # 每个方向创建2个种子点
            for j in range(1, 3):
                pos = self.city_center + direction * (base_distance * j)
                node = GrowthNode(pos)
                node.is_seed = True
                
                # 连接相邻种子点
                if j > 1:
                    prev_pos = self.city_center + direction * (base_distance * (j - 1))
                    for existing in self.all_nodes:
                        if existing.position.distance_to(prev_pos) < 10:
                            node.parent = existing
                            node.add_neighbor(existing)
                            break
                
                self.all_nodes.append(node)
                self.front.append(node)
    
    def _build_road_network(self) -> RoadNetwork:
        """将生长节点转换为 RoadNetwork。"""
        network = RoadNetwork("procedural_city")
        
        # 创建节点映射
        node_map: dict[int, Node] = {}
        
        for growth_node in self.all_nodes:
            node = Node(
                position=growth_node.position,
                is_intersection=len(growth_node.neighbors) > 2
            )
            network.add_node(node)
            node_map[id(growth_node)] = node
        
        # 创建边
        created_edges: set[tuple[int, int]] = set()
        
        for growth_node in self.all_nodes:
            from_node = node_map.get(id(growth_node))
            if not from_node:
                continue
            
            for neighbor in growth_node.neighbors:
                to_node = node_map.get(id(neighbor))
                if not to_node:
                    continue
                
                # 避免重复边
                edge_key = tuple(sorted([id(growth_node), id(neighbor)]))
                if edge_key in created_edges:
                    continue
                created_edges.add(edge_key)
                
                # 创建双向边
                network.create_edge(from_node, to_node, num_lanes=2, bidirectional=True)
        
        return network


def create_procedural_network(
    city_center: Vector2D | None = None,
    boundary_size: float = 1000.0,
    iterations: int = 50,
    rule: GrowthRule = GrowthRule.GRID
) -> RoadNetwork:
    """
    创建仿 procedural_city_generation 风格的路网。
    
    Args:
        city_center: 城市中心位置
        boundary_size: 边界大小
        iterations: 生长迭代次数
        rule: 默认生长规则
        
    Returns:
        生成的道路网络
    """
    half_size = boundary_size / 2
    boundary = (-half_size, -half_size, half_size, half_size)
    
    config = RoadGrowthConfig(
        max_iterations=iterations,
        min_node_distance=100.0,
        snap_threshold=60.0
    )
    
    generator = ProceduralRoadGenerator(
        config=config,
        default_rule=rule,
        city_center=city_center or Vector2D(0, 0),
        boundary=boundary
    )
    
    return generator.generate(iterations=iterations)
