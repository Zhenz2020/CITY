"""
真正的生长式城市扩展 - 仿照 procedural_city_generation 的多分支生长。

从多个前沿节点同时生长，产生自然的路网分支和交叉。
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from city.utils.vector import Vector2D

if TYPE_CHECKING:
    from city.simulation.environment import SimulationEnvironment
    from city.environment.road_network import Node, RoadNetwork


@dataclass
class GrowthNode:
    """生长节点 - 用于生长过程中的临时表示。"""
    position: Vector2D
    node_id: str | None = None  # 如果已转换为真实节点
    parent: GrowthNode | None = None
    children: list[GrowthNode] = field(default_factory=list)
    
    # 生长状态
    is_active: bool = True  # 是否仍在生长前沿
    generation: int = 0  # 代数
    
    # 道路属性
    is_major_road: bool = True  # 主干道 vs 支路
    road_direction: Vector2D | None = None  # 当前行进方向
    
    def add_child(self, child: GrowthNode) -> None:
        """添加子节点。"""
        self.children.append(child)
        child.parent = self
        child.generation = self.generation + 1


@dataclass
class GrowthConfig:
    """生长配置参数 - 仿照 procedural_city_generation。"""
    
    # 迭代控制
    iterations_per_expansion: int = 3  # 每次扩展的迭代次数
    max_front_size: int = 8  # 最大前沿节点数
    
    # 分支概率
    branch_prob: float = 0.35  # 分支概率
    continue_prob: float = 0.75  # 继续延伸概率
    
    # Grid 参数
    grid_straight_prob: float = 0.90  # 直行概率
    grid_turn_prob: float = 0.30  # 转弯概率（产生分支）
    grid_angle: float = 90.0  # 正交转弯角度
    
    # Organic 参数  
    organic_deviation: float = 25.0  # 直行时角度偏差
    organic_branch_angles: tuple[float, float] = (60.0, 120.0)  # 分支角度范围
    
    # Radial 参数
    radial_ring_prob: float = 0.25  # 环形路概率
    
    # 道路长度
    segment_length_min: float = 180.0
    segment_length_max: float = 280.0
    
    # 约束
    min_node_spacing: float = 100.0  # 节点最小间距
    snap_distance: float = 60.0  # 吸附到现有节点的距离
    boundary_margin: float = 50.0  # 边界余量


class ProceduralGrowthExpansion:
    """
    生长式城市扩展器。
    
    仿照 procedural_city_generation，从当前路网边界生长出新的路网分支，
    形成自然的城市路网结构。
    """
    
    def __init__(
        self,
        environment: SimulationEnvironment,
        config: GrowthConfig | None = None
    ):
        self.env = environment
        self.config = config or GrowthConfig()
        self.network: RoadNetwork = environment.road_network
        
        # 生长状态
        self.front: list[GrowthNode] = []  # 当前生长前沿
        self.all_growth_nodes: list[GrowthNode] = []  # 所有生长节点
        self.iteration: int = 0
        
    def _get_network_boundary(self) -> tuple[float, float, float, float]:
        """获取当前网络的边界。"""
        if not self.network.nodes:
            return (-500, -500, 500, 500)
        
        xs = [n.position.x for n in self.network.nodes.values()]
        ys = [n.position.y for n in self.network.nodes.values()]
        return (min(xs), min(ys), max(xs), max(ys))
    
    def _get_outward_direction(self, pos: Vector2D) -> Vector2D:
        """获取从中心向外的方向。"""
        center = self._get_network_center()
        direction = pos - center
        length = direction.magnitude()
        if length < 0.001:
            # 随机方向
            angle = random.uniform(0, 2 * math.pi)
            return Vector2D(math.cos(angle), math.sin(angle))
        return Vector2D(direction.x / length, direction.y / length)
    
    def _get_network_center(self) -> Vector2D:
        """获取当前网络的中心。"""
        if not self.network.nodes:
            return Vector2D(0, 0)
        xs = [n.position.x for n in self.network.nodes.values()]
        ys = [n.position.y for n in self.network.nodes.values()]
        return Vector2D(sum(xs) / len(xs), sum(ys) / len(ys))
    
    def _initialize_front(self) -> None:
        """初始化生长前沿 - 从当前网络边界节点开始。"""
        self.front = []
        self.all_growth_nodes = []
        
        # 找到边界节点作为初始前沿
        boundary_nodes = self._find_boundary_nodes()
        
        for node in boundary_nodes:
            # 为每个边界节点创建生长节点
            growth_node = GrowthNode(
                position=node.position,
                node_id=node.node_id,
                is_active=True,
                generation=0
            )
            
            # 确定初始生长方向（向外）
            outward = self._get_outward_direction(node.position)
            # 添加随机扰动
            angle = random.uniform(-30, 30)
            growth_node.road_direction = self._rotate_vector(outward, angle)
            
            self.front.append(growth_node)
            self.all_growth_nodes.append(growth_node)
        
        print(f"[生长扩展] 初始化前沿: {len(self.front)} 个节点")
    
    def _find_boundary_nodes(self) -> list[Node]:
        """找到网络边界上的节点。"""
        if not self.network.nodes:
            return []
        
        # 计算边界
        min_x, min_y, max_x, max_y = self._get_network_boundary()
        margin = (max_x - min_x + max_y - min_y) / 4 * 0.15  # 15% 边界区域
        
        boundary_nodes = []
        for node in self.network.nodes.values():
            # 如果节点在边界附近
            is_boundary = (
                node.position.x < min_x + margin or
                node.position.x > max_x - margin or
                node.position.y < min_y + margin or
                node.position.y > max_y - margin
            )
            if is_boundary:
                boundary_nodes.append(node)
        
        # 如果没有边界节点，使用所有节点
        if not boundary_nodes:
            boundary_nodes = list(self.network.nodes.values())
        
        # 限制数量
        if len(boundary_nodes) > self.config.max_front_size:
            # 均匀采样
            step = len(boundary_nodes) // self.config.max_front_size
            boundary_nodes = boundary_nodes[::step][:self.config.max_front_size]
        
        return boundary_nodes
    
    def _rotate_vector(self, vec: Vector2D, angle_deg: float) -> Vector2D:
        """旋转向量。"""
        angle_rad = math.radians(angle_deg)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        return Vector2D(
            vec.x * cos_a - vec.y * sin_a,
            vec.x * sin_a + vec.y * cos_a
        )
    
    def _generate_suggestions(self, node: GrowthNode) -> list[GrowthNode]:
        """
        生成生长建议 - 仿照 procedural_city_generation 的生长规则。
        
        返回多个可能的子节点（产生分支）。
        """
        suggestions = []
        config = self.config
        
        if not node.is_active:
            return suggestions
        
        # 获取当前行进方向
        if node.road_direction is None:
            node.road_direction = self._get_outward_direction(node.position)
        
        base_dir = node.road_direction
        
        # 1. 直行延伸（主干道）
        if random.random() < config.continue_prob:
            # 添加轻微随机偏差
            angle = random.uniform(-config.organic_deviation, config.organic_deviation)
            new_dir = self._rotate_vector(base_dir, angle)
            length = random.uniform(config.segment_length_min, config.segment_length_max)
            
            new_pos = node.position + new_dir * length
            child = GrowthNode(
                position=new_pos,
                is_major_road=node.is_major_road,
                road_direction=new_dir
            )
            node.add_child(child)
            suggestions.append(child)
        
        # 2. 分支（产生新的生长方向）
        if random.random() < config.branch_prob:
            # 左右分支
            for turn in [-1, 1]:
                if random.random() < config.grid_turn_prob:
                    # Grid 风格：90度转弯
                    branch_angle = config.grid_angle * turn
                    branch_dir = self._rotate_vector(base_dir, branch_angle)
                    length = random.uniform(config.segment_length_min * 0.7, 
                                          config.segment_length_max * 0.9)
                    
                    new_pos = node.position + branch_dir * length
                    child = GrowthNode(
                        position=new_pos,
                        is_major_road=False,  # 支路
                        road_direction=branch_dir
                    )
                    node.add_child(child)
                    suggestions.append(child)
        
        # 3. Organic 风格分支（随机角度）
        if random.random() < config.branch_prob * 0.5:
            min_angle, max_angle = config.organic_branch_angles
            branch_angle = random.choice([-1, 1]) * random.uniform(min_angle, max_angle)
            branch_dir = self._rotate_vector(base_dir, branch_angle)
            length = random.uniform(config.segment_length_min * 0.6, 
                                  config.segment_length_max * 0.8)
            
            new_pos = node.position + branch_dir * length
            child = GrowthNode(
                position=new_pos,
                is_major_road=False,
                road_direction=branch_dir
            )
            node.add_child(child)
            suggestions.append(child)
        
        return suggestions
    
    def _is_valid_position(self, pos: Vector2D) -> bool:
        """检查位置是否有效。"""
        # 边界检查
        min_x, min_y, max_x, max_y = self._get_network_boundary()
        margin = self.config.boundary_margin
        
        # 扩展边界限制（向外生长）
        if pos.x < min_x - 400 or pos.x > max_x + 400:
            return False
        if pos.y < min_y - 400 or pos.y > max_y + 400:
            return False
        
        return True
    
    def _find_nearby_node(self, pos: Vector2D) -> Node | None:
        """查找附近的现有节点。"""
        for node in self.network.nodes.values():
            if pos.distance_to(node.position) < self.config.snap_distance:
                return node
        return None
    
    def _check_node_spacing(self, pos: Vector2D, exclude: GrowthNode | None = None) -> bool:
        """检查节点间距。"""
        # 检查与真实节点的距离
        for node in self.network.nodes.values():
            if pos.distance_to(node.position) < self.config.min_node_spacing * 0.7:
                return False
        
        # 检查与其他生长节点的距离
        for gn in self.all_growth_nodes:
            if gn is exclude:
                continue
            if pos.distance_to(gn.position) < self.config.min_node_spacing:
                return False
        
        return True
    
    def grow(self) -> list[Node]:
        """
        执行一轮生长扩展。
        
        Returns:
            新创建的真实节点列表
        """
        if not self.front:
            self._initialize_front()
        
        new_real_nodes: list[Node] = []
        
        # 迭代生长
        for iteration in range(self.config.iterations_per_expansion):
            self.iteration += 1
            new_front: list[GrowthNode] = []
            
            for node in self.front:
                if not node.is_active:
                    continue
                
                # 生成生长建议
                suggestions = self._generate_suggestions(node)
                
                for suggested in suggestions:
                    # 验证位置
                    if not self._is_valid_position(suggested.position):
                        continue
                    
                    # 检查节点间距
                    if not self._check_node_spacing(suggested.position, exclude=node):
                        # 尝试吸附到现有节点
                        nearby = self._find_nearby_node(suggested.position)
                        if nearby:
                            # 连接但不创建新节点
                            self._create_connection(node, nearby)
                        continue
                    
                    # 创建真实节点
                    real_node = self._create_real_node(suggested)
                    if real_node:
                        new_real_nodes.append(real_node)
                        suggested.node_id = real_node.node_id
                        new_front.append(suggested)
                        self.all_growth_nodes.append(suggested)
                
                # 当前节点完成生长
                node.is_active = False
            
            # 更新前沿
            self.front = new_front
            
            # 限制前沿大小
            if len(self.front) > self.config.max_front_size:
                # 优先保留离中心远的节点（向外生长）
                center = self._get_network_center()
                self.front.sort(
                    key=lambda n: n.position.distance_to(center),
                    reverse=True
                )
                self.front = self.front[:self.config.max_front_size]
            
            if not self.front:
                break
        
        print(f"[生长扩展] 完成 {self.iteration} 轮迭代，新增 {len(new_real_nodes)} 个节点")
        return new_real_nodes
    
    def _create_real_node(self, growth_node: GrowthNode) -> Node | None:
        """将生长节点转换为真实节点。"""
        from city.environment.road_network import Node
        
        # 创建真实节点
        node = Node(
            position=growth_node.position,
            name=f"growth_{self.iteration}_{len(self.network.nodes)}",
            is_intersection=len(growth_node.children) > 1 or 
                          (growth_node.parent and len(growth_node.children) > 0)
        )
        
        self.network.add_node(node)
        
        # 连接到父节点
        if growth_node.parent and growth_node.parent.node_id:
            parent_node = self.network.nodes.get(growth_node.parent.node_id)
            if parent_node:
                self._create_connection_between(parent_node, node)
        
        return node
    
    def _create_connection(self, from_growth: GrowthNode, to_real: Node) -> None:
        """创建生长节点到真实节点的连接。"""
        if from_growth.node_id:
            from_real = self.network.nodes.get(from_growth.node_id)
            if from_real:
                self._create_connection_between(from_real, to_real)
    
    def _create_connection_between(self, from_node: Node, to_node: Node) -> None:
        """在两个真实节点之间创建连接。"""
        # 检查是否已有连接
        if self.network.has_edge_between(from_node, to_node):
            return
        
        # 检查距离
        dist = from_node.position.distance_to(to_node.position)
        if dist < 50:  # 太近的忽略
            return
        
        # 创建边
        self.network.create_edge(from_node, to_node, num_lanes=2, bidirectional=True)


def expand_city_procedurally(
    environment: SimulationEnvironment,
    expansion_size: str = "medium",  # small, medium, large
) -> list[Node]:
    """
    使用生长算法扩展城市路网。
    
    Args:
        environment: 仿真环境
        expansion_size: 扩展规模
        
    Returns:
        新创建的节点列表
    """
    # 根据规模选择配置
    configs = {
        "small": GrowthConfig(
            iterations_per_expansion=2,
            max_front_size=4,
            branch_prob=0.25
        ),
        "medium": GrowthConfig(
            iterations_per_expansion=3,
            max_front_size=6,
            branch_prob=0.35
        ),
        "large": GrowthConfig(
            iterations_per_expansion=5,
            max_front_size=10,
            branch_prob=0.45
        )
    }
    
    config = configs.get(expansion_size, configs["medium"])
    
    # 创建扩展器并生长
    expander = ProceduralGrowthExpansion(environment, config)
    new_nodes = expander.grow()
    
    return new_nodes
