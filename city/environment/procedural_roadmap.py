"""
真正仿照 procedural_city_generation 的路网生成系统。

核心机制：
1. Vertex + neighbours 图结构
2. Front (生长前沿) 迭代生长
3. Check 函数处理相交、吸附、创建交叉口
4. Seed + vertex_queue 支路生成机制
5. KDTree 空间查询加速
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np

from city.utils.vector import Vector2D

if TYPE_CHECKING:
    from city.simulation.environment import SimulationEnvironment
    from city.environment.road_network import Node, RoadNetwork


class ProceduralVertex:
    """
    仿照 procedural_city_generation 的 Vertex 类。
    
    Attributes:
        coords: numpy array [x, y]
        neighbours: 邻居节点列表（双向连接）
        minor_road: 是否小路
        seed: 是否种子节点（可生支路）
    """
    
    def __init__(self, coords: np.ndarray | Vector2D):
        if isinstance(coords, Vector2D):
            self.coords = np.array([coords.x, coords.y], dtype=float)
        else:
            self.coords = np.array(coords, dtype=float)
        
        self.neighbours: list[ProceduralVertex] = []
        self.minor_road: bool = False
        self.seed: bool = False
        self.real_node_id: str | None = None  # 对应真实 RoadNetwork 中的节点
    
    def connection(self, other: ProceduralVertex) -> None:
        """建立双向连接（仿照原版的 connection 方法）。"""
        # 防止自连接
        if other is self:
            return
        
        if other not in self.neighbours:
            self.neighbours.append(other)
        if self not in other.neighbours:
            other.neighbours.append(self)
    
    def __repr__(self) -> str:
        return f"Vertex({self.coords[0]:.1f}, {self.coords[1]:.1f})"


@dataclass
class ProceduralConfig:
    """仿照 roadmap.conf 的配置。"""
    # 边界
    border_x: float = 1000.0
    border_y: float = 1000.0
    
    # 距离约束
    min_distance: float = 100.0  # 节点最小间距
    max_length: float = 300.0    # 最大边长度
    
    # Grid 参数
    gridpForward: float = 95.0   # 直行概率
    gridpTurn: float = 25.0      # 转弯概率
    gridlMin: float = 180.0      # 最小长度
    gridlMax: float = 250.0      # 最大长度
    
    # Organic 参数
    organicpForward: float = 90.0
    organicpTurn: float = 20.0
    organiclMin: float = 150.0
    organiclMax: float = 280.0
    
    # Radial 参数
    radialpForward: float = 95.0
    radialpTurn: float = 15.0
    radiallMin: float = 180.0
    radiallMax: float = 280.0
    
    # Minor road 参数
    minor_road_delay: int = 3    # 支路延迟（迭代次数）
    pSeed: float = 40.0          # 种子产生支路概率
    seedlMin: float = 80.0
    seedlMax: float = 150.0
    
    def get_border(self) -> tuple[float, float]:
        return (self.border_x, self.border_y)


class ProceduralRoadmapGenerator:
    """
    真正仿照 procedural_city_generation 的路网生成器。
    
    核心流程：
    1. 初始化 front（生长前沿）
    2. 迭代执行：
       a. 对每个 front 节点调用 get_suggestion 生成建议
       b. 调用 check 验证建议并处理相交
       c. 更新 front
    3. 处理 vertex_queue（支路延迟生成）
    4. 转换为 RoadNetwork
    """
    
    def __init__(
        self,
        environment: SimulationEnvironment,
        config: ProceduralConfig | None = None
    ):
        self.env = environment
        self.config = config or ProceduralConfig()
        
        # 全局列表（仿照 global_lists）
        self.vertex_list: list[ProceduralVertex] = []  # 所有顶点
        self.vertex_queue: list[tuple[ProceduralVertex, int]] = []  # 延迟队列 [(vertex, age)]
        self.kdtree: Any = None  # KDTree 加速查询
        
        # 生长状态
        self.front: list[ProceduralVertex] = []
        self.iteration_count: int = 0
    
    def _is_valid_position(self, pos: np.ndarray) -> bool:
        """检查位置是否在扩展边界内。"""
        border_x, border_y = self.config.get_border()
        margin = self.config.max_length
        
        # 允许向外扩展一定范围
        min_x, max_x = -border_x - margin, border_x + margin
        min_y, max_y = -border_y - margin, border_y + margin
        
        return (min_x <= pos[0] <= max_x and min_y <= pos[1] <= max_y)
    
    def _update_kdtree(self) -> None:
        """更新 KDTree（每次添加节点后调用）。"""
        if len(self.vertex_list) == 0:
            return
        coords = np.array([v.coords for v in self.vertex_list])
        try:
            from scipy.spatial import cKDTree
            self.kdtree = cKDTree(coords, leafsize=160)
        except ImportError:
            self.kdtree = None
    
    def _find_nearby_vertices(
        self, 
        coords: np.ndarray, 
        max_distance: float | None = None
    ) -> tuple[np.ndarray, list[ProceduralVertex]]:
        """使用 KDTree 查找附近顶点。"""
        max_dist = max_distance or self.config.max_length
        
        if self.kdtree is None or len(self.vertex_list) == 0:
            return np.array([]), []
        
        try:
            distances, indices = self.kdtree.query(
                coords, 
                k=min(10, len(self.vertex_list)),
                distance_upper_bound=max_dist
            )
            
            # 处理单结果情况
            if not isinstance(distances, np.ndarray):
                distances = np.array([distances])
                indices = np.array([indices])
            
            # 过滤无效结果
            valid_mask = indices < len(self.vertex_list)
            distances = distances[valid_mask] if len(valid_mask) > 0 else distances
            indices = indices[valid_mask] if len(valid_mask) > 0 else indices
            
            vertices = [self.vertex_list[i] for i in indices if i < len(self.vertex_list)]
            return distances, vertices
        except Exception:
            # KDTree 失败时返回空
            return np.array([]), []
    
    def initialize_from_network(self) -> None:
        """从现有 RoadNetwork 初始化顶点列表。"""
        network = self.env.road_network
        
        # 创建 ProceduralVertex 映射
        vertex_map: dict[str, ProceduralVertex] = {}
        
        for node_id, node in network.nodes.items():
            pv = ProceduralVertex(node.position)
            pv.real_node_id = node_id
            vertex_map[node_id] = pv
            self.vertex_list.append(pv)
        
        # 建立 neighbours 连接
        for edge in network.edges.values():
            from_id = edge.from_node.node_id
            to_id = edge.to_node.node_id
            if from_id in vertex_map and to_id in vertex_map:
                vertex_map[from_id].connection(vertex_map[to_id])
        
        self._update_kdtree()
        
        # 初始化 front - 使用边界节点
        self._initialize_front()
    
    def _initialize_front(self) -> None:
        """初始化生长前沿 - 选择边界上的节点。"""
        if not self.vertex_list:
            return
        
        # 计算边界
        xs = [v.coords[0] for v in self.vertex_list]
        ys = [v.coords[1] for v in self.vertex_list]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        margin_x = (max_x - min_x) * 0.15
        margin_y = (max_y - min_y) * 0.15
        
        # 选择边界节点
        boundary_vertices = []
        for v in self.vertex_list:
            is_boundary = (
                v.coords[0] < min_x + margin_x or
                v.coords[0] > max_x - margin_x or
                v.coords[1] < min_y + margin_y or
                v.coords[1] > max_y - margin_y
            )
            if is_boundary:
                boundary_vertices.append(v)
        
        # 如果没有边界节点，使用所有节点
        if not boundary_vertices:
            boundary_vertices = self.vertex_list[:]
        
        # 限制 front 大小（仿照原版 pop(0) 和 pop() 逻辑）
        if len(boundary_vertices) > 8:
            # 均匀选择
            step = len(boundary_vertices) // 6
            self.front = boundary_vertices[::step][:6]
        else:
            self.front = boundary_vertices
        
        print(f"[ProceduralRoadmap] 初始化 front: {len(self.front)} 个节点")
    
    def _get_rule(self, vertex: ProceduralVertex) -> tuple[int, Any, float]:
        """
        确定生长规则（仿照 getRule）。
        
        Returns:
            (rule_type, center, population_density)
            rule_type: 0=Grid, 1=Organic, 2=Radial, 3=MinorRoad, 4=Seed
        """
        # 简化版本：基于位置选择规则
        center = np.array([0.0, 0.0])
        
        # 距离中心的距离
        dist_from_center = np.linalg.norm(vertex.coords - center)
        
        # 简单策略：外围用 Grid，中间用 Organic，中心用 Radial
        if dist_from_center < 200:
            return (2, center, 0.8)  # Radial
        elif dist_from_center < 500:
            return (1, center, 0.6)  # Organic
        else:
            return (0, center, 0.4)  # Grid
    
    def _grid_rule(self, vertex: ProceduralVertex, b: float) -> list[ProceduralVertex]:
        """Grid 生长规则（仿照 grid.py）。"""
        cfg = self.config
        suggestions = []
        weiter = True
        
        # 计算 previous_vector（从邻居指向当前节点）
        if not vertex.neighbours:
            # 随机方向
            angle = random.uniform(0, 2 * math.pi)
            previous_vector = np.array([math.cos(angle), math.sin(angle)])
        else:
            # 使用最后一个邻居的方向
            last_neighbour = vertex.neighbours[-1]
            previous_vector = vertex.coords - last_neighbour.coords
            norm = np.linalg.norm(previous_vector)
            if norm > 0:
                previous_vector = previous_vector / norm
        
        # 法向量（90度旋转）
        n = np.array([-previous_vector[1], previous_vector[0]])
        
        # 直行
        length = random.uniform(cfg.gridlMin, cfg.gridlMax)
        if random.randint(0, 100) <= cfg.gridpForward:
            new_coords = vertex.coords + previous_vector * length
            k = ProceduralVertex(new_coords)
            suggestions.append(k)
            weiter = False
        
        # 右转
        if random.randint(0, 100) <= cfg.gridpTurn * b * b:
            new_coords = vertex.coords + n * length
            k = ProceduralVertex(new_coords)
            suggestions.append(k)
            weiter = True
        
        # 左转
        if random.randint(0, 100) <= cfg.gridpTurn * b * b:
            new_coords = vertex.coords - n * length
            k = ProceduralVertex(new_coords)
            suggestions.append(k)
            weiter = True
        
        # Seed!（如果直行停止，成为种子）
        if not weiter:
            vertex.seed = True
            self.vertex_queue.append((vertex, 0))
        
        return suggestions
    
    def _organic_rule(self, vertex: ProceduralVertex, b: float) -> list[ProceduralVertex]:
        """Organic 生长规则（仿照 organic.py）。"""
        cfg = self.config
        suggestions = []
        
        # 计算 previous_vector
        if not vertex.neighbours:
            angle = random.uniform(0, 2 * math.pi)
            previous_vector = np.array([math.cos(angle), math.sin(angle)])
        else:
            last_neighbour = vertex.neighbours[-1]
            previous_vector = vertex.coords - last_neighbour.coords
            norm = np.linalg.norm(previous_vector)
            if norm > 0:
                previous_vector = previous_vector / norm
        
        # 直行（带随机偏差）
        if random.randint(0, 100) <= cfg.organicpForward:
            angle = random.uniform(-30, 30)
            rad = math.radians(angle)
            rot = np.array([[math.cos(rad), -math.sin(rad)],
                           [math.sin(rad), math.cos(rad)]])
            new_dir = rot @ previous_vector
            length = random.uniform(cfg.organiclMin, cfg.organiclMax)
            new_coords = vertex.coords + new_dir * length
            k = ProceduralVertex(new_coords)
            suggestions.append(k)
        
        # 右转（60-120度）
        if random.randint(0, 100) <= b * cfg.organicpTurn:
            angle = random.uniform(60, 120)
            rad = math.radians(angle)
            rot = np.array([[math.cos(rad), -math.sin(rad)],
                           [math.sin(rad), math.cos(rad)]])
            new_dir = rot @ previous_vector
            length = random.uniform(cfg.organiclMin, cfg.organiclMax)
            new_coords = vertex.coords + new_dir * length
            k = ProceduralVertex(new_coords)
            k.minor_road = True
            suggestions.append(k)
        
        # 左转（60-120度）
        if random.randint(0, 100) <= b * cfg.organicpTurn:
            angle = random.uniform(-120, -60)
            rad = math.radians(angle)
            rot = np.array([[math.cos(rad), -math.sin(rad)],
                           [math.sin(rad), math.cos(rad)]])
            new_dir = rot @ previous_vector
            length = random.uniform(cfg.organiclMin, cfg.organiclMax)
            new_coords = vertex.coords + new_dir * length
            k = ProceduralVertex(new_coords)
            k.minor_road = True
            suggestions.append(k)
        
        return suggestions
    
    def _seed_rule(self, vertex: ProceduralVertex, b: float) -> list[ProceduralVertex]:
        """Seed 规则 - 从种子生 minor road（仿照 seed.py）。"""
        cfg = self.config
        suggestions = []
        
        # 需要至少 1-2 个邻居
        if len(vertex.neighbours) < 1:
            return suggestions
        
        # 计算垂直于道路的方向
        v1 = vertex.coords - vertex.neighbours[0].coords
        if len(vertex.neighbours) >= 2:
            v2 = vertex.coords - vertex.neighbours[1].coords
        else:
            v2 = v1
        
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        
        if norm1 > 0:
            v1 = v1 / norm1
            # 垂直向量
            perp1 = np.array([-v1[1], v1[0]])
            
            # 右分支
            if b * b * cfg.pSeed > random.randint(0, 100):
                length = random.uniform(cfg.seedlMin, cfg.seedlMax)
                k = random.uniform(0, 1)
                new_coords = vertex.coords + ((1-k) * perp1 + k * -perp1) * length
                new_vertex = ProceduralVertex(new_coords)
                new_vertex.minor_road = True
                suggestions.append(new_vertex)
        
        return suggestions
    
    def get_suggestion(self, vertex: ProceduralVertex) -> list[ProceduralVertex]:
        """获取生长建议（仿照 getSuggestion）。"""
        rule = self._get_rule(vertex)
        rule_type = rule[0]
        center = rule[1]
        b = rule[2]  # population density factor
        
        if rule_type == 0:
            return self._grid_rule(vertex, b)
        elif rule_type == 1:
            return self._organic_rule(vertex, b)
        elif rule_type == 2:
            # Radial 暂时用 Grid 代替
            return self._grid_rule(vertex, b)
        elif rule_type == 3:
            # Minor road
            return []
        elif rule_type == 4:
            return self._seed_rule(vertex, b)
        
        return []
    
    def _get_intersection(
        self, 
        a: np.ndarray, ab: np.ndarray,
        c: np.ndarray, cd: np.ndarray
    ) -> np.ndarray:
        """计算两条线的交点参数（仿照 get_intersection）。"""
        try:
            # 解方程: a + t*ab = c + u*cd
            # => [ab, -cd] * [t, u]^T = c - a
            A = np.column_stack([ab, -cd])
            solution = np.linalg.solve(A, c - a)
            return solution
        except np.linalg.LinAlgError:
            return np.array([np.inf, np.inf])
    
    def check(
        self,
        suggested: ProceduralVertex,
        neighbour: ProceduralVertex,
        newfront: list[ProceduralVertex]
    ) -> list[ProceduralVertex]:
        """
        检查建议节点（仿照 check.py）。
        
        核心逻辑：
        1. 边界检查
        2. 太近检查（使用 KDTree）
        3. 相交检查（创建交叉口）
        4. 直接添加
        """
        cfg = self.config
        
        # 1. 边界检查
        border_x, border_y = cfg.get_border()
        if (abs(suggested.coords[0]) > border_x - cfg.max_length or
            abs(suggested.coords[1]) > border_y - cfg.max_length):
            return newfront
        
        # 2. 查找附近节点
        distances, near_vertices = self._find_nearby_vertices(suggested.coords)
        
        # 3. 太近检查
        if len(distances) > 0 and distances[0] < cfg.min_distance:
            nearest = near_vertices[0]
            
            # 如果最近的节点不是邻居
            if nearest not in neighbour.neighbours:
                # 查找与附近边的最佳交点
                best_sol = float('inf')
                sol_vertices = None
                
                for k in near_vertices:
                    for n in k.neighbours:
                        if n in near_vertices:
                            sol = self._get_intersection(
                                neighbour.coords,
                                suggested.coords - neighbour.coords,
                                k.coords,
                                n.coords - k.coords
                            )
                            
                            if (sol[0] > 0.00001 and sol[0] < 0.99999 and
                                sol[1] > 0.00001 and sol[1] < 0.99999 and
                                sol[0] < best_sol):
                                best_sol = sol[0]
                                sol_vertices = (n, k)
                
                # 如果找到交点，创建交叉口
                if sol_vertices is not None:
                    n, k = sol_vertices
                    
                    # 断开原有连接
                    if n in k.neighbours:
                        k.neighbours.remove(n)
                    if k in n.neighbours:
                        n.neighbours.remove(k)
                    
                    # 创建新节点（交点）
                    new_coords = neighbour.coords + best_sol * (suggested.coords - neighbour.coords)
                    new_vertex = ProceduralVertex(new_coords)
                    
                    # 建立连接
                    neighbour.connection(new_vertex)
                    k.connection(new_vertex)
                    n.connection(new_vertex)
                    
                    # 添加到全局列表
                    self.vertex_list.append(new_vertex)
                    self._update_kdtree()
                    
                    return newfront
                else:
                    # 没有交点，直接连接
                    nearest.connection(neighbour)
            
            return newfront
        
        # 4. 检查与现有边的相交（但不经过节点）
        best_sol = float('inf')
        sol_vertices = None
        
        for k in near_vertices:
            for n in k.neighbours:
                if n in near_vertices:
                    sol = self._get_intersection(
                        neighbour.coords,
                        suggested.coords - neighbour.coords,
                        k.coords,
                        n.coords - k.coords
                    )
                    
                    # 相交在边内部
                    if (sol[0] > 0.00001 and sol[0] < 1.499999 and
                        sol[1] > 0.00001 and sol[1] < 0.99999 and
                        sol[0] < best_sol):
                        best_sol = sol[0]
                        sol_vertices = (n, k)
        
        # 如果找到交点，在交点处创建节点
        if sol_vertices is not None:
            n, k = sol_vertices
            
            # 断开原有连接
            if n in k.neighbours:
                k.neighbours.remove(n)
            if k in n.neighbours:
                n.neighbours.remove(k)
            
            # 创建交点节点
            new_coords = neighbour.coords + best_sol * (suggested.coords - neighbour.coords)
            new_vertex = ProceduralVertex(new_coords)
            
            # 建立连接
            neighbour.connection(new_vertex)
            k.connection(new_vertex)
            n.connection(new_vertex)
            
            # 添加到全局列表
            self.vertex_list.append(new_vertex)
            self._update_kdtree()
            
            return newfront
        
        # 5. 直接添加（无冲突）
        suggested.connection(neighbour)
        newfront.append(suggested)
        self.vertex_list.append(suggested)
        self._update_kdtree()
        
        return newfront
    
    def iteration(self, front: list[ProceduralVertex]) -> list[ProceduralVertex]:
        """
        单次迭代（仿照 iteration.py）。
        
        1. 对 front 中每个节点生成建议
        2. 检查建议
        3. 处理 vertex_queue
        """
        newfront: list[ProceduralVertex] = []
        
        # 处理 front
        for vertex in front:
            for suggested in self.get_suggestion(vertex):
                newfront = self.check(suggested, vertex, newfront)
        
        # 增加 vertex_queue 中节点的 age
        self.vertex_queue = [(v, age + 1) for v, age in self.vertex_queue]
        
        # 将到达延迟的节点加入 newfront
        delay = self.config.minor_road_delay
        ready_to_add = [(v, age) for v, age in self.vertex_queue if age >= delay]
        self.vertex_queue = [(v, age) for v, age in self.vertex_queue if age < delay]
        
        for v, _ in ready_to_add:
            # 对这些节点应用 seed 规则生 minor road
            seeds = self._seed_rule(v, 1.0)
            for s in seeds:
                newfront = self.check(s, v, newfront)
        
        return newfront
    
    def grow(self, num_iterations: int = 3) -> list[ProceduralVertex]:
        """
        执行多轮生长。
        
        Args:
            num_iterations: 迭代次数
            
        Returns:
            本轮新增的节点列表
        """
        if not self.front:
            self.initialize_from_network()
        
        initial_count = len(self.vertex_list)
        
        for i in range(num_iterations):
            self.iteration_count += 1
            self.front = self.iteration(self.front)
            
            if not self.front:
                break
        
        new_vertices = self.vertex_list[initial_count:]
        print(f"[ProceduralRoadmap] 生长完成: 新增 {len(new_vertices)} 个顶点")
        return new_vertices
    
    def _get_zones_for_road_avoidance(self) -> list:
        """收集当前环境中的功能区域，用于道路避让。"""
        zones = []
        for agent in self.env.agents.values():
            zone_manager = getattr(agent, "zone_manager", None)
            if zone_manager and hasattr(zone_manager, "zones"):
                zones.extend(zone_manager.zones.values())
        return zones

    def _segment_intersects_zone(self, x1: float, y1: float, x2: float, y2: float, zone) -> bool:
        """检查线段是否穿越带道路缓冲的区域边界。"""
        road_buffer = 30.0
        zone_min_x = zone.center.x - zone.width / 2 - road_buffer
        zone_max_x = zone.center.x + zone.width / 2 + road_buffer
        zone_min_y = zone.center.y - zone.height / 2 - road_buffer
        zone_max_y = zone.center.y + zone.height / 2 + road_buffer

        if (x1 < zone_min_x and x2 < zone_min_x) or (x1 > zone_max_x and x2 > zone_max_x):
            return False
        if (y1 < zone_min_y and y2 < zone_min_y) or (y1 > zone_max_y and y2 > zone_max_y):
            return False

        dx = x2 - x1
        dy = y2 - y1
        p = [-dx, dx, -dy, dy]
        q = [x1 - zone_min_x, zone_max_x - x1, y1 - zone_min_y, zone_max_y - y1]
        u1 = 0.0
        u2 = 1.0

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

    def _edge_blocked_by_zone(self, from_node, to_node, zones: list):
        """返回道路候选边穿越的第一个区域；如果安全则返回 None。"""
        for zone in zones:
            if self._segment_intersects_zone(
                from_node.position.x,
                from_node.position.y,
                to_node.position.x,
                to_node.position.y,
                zone,
            ):
                return zone
        return None

    def to_road_network(self) -> None:
        """将 ProceduralVertex 转换为 RoadNetwork。"""
        network = self.env.road_network
        vertex_to_node: dict[int, str] = {}
        
        # 创建或更新节点
        for pv in self.vertex_list:
            if pv.real_node_id and pv.real_node_id in network.nodes:
                # 更新现有节点
                node = network.nodes[pv.real_node_id]
                node.position = Vector2D(pv.coords[0], pv.coords[1])
                vertex_to_node[id(pv)] = pv.real_node_id
            else:
                # 创建新节点
                from city.environment.road_network import Node
                node = Node(
                    position=Vector2D(pv.coords[0], pv.coords[1]),
                    name=f"proc_{len(network.nodes)}"
                )
                network.add_node(node)
                pv.real_node_id = node.node_id
                vertex_to_node[id(pv)] = node.node_id
        
        # 创建边（基于 neighbours）
        created_edges: set[tuple[str, str]] = set()
        zones = self._get_zones_for_road_avoidance()
        
        for pv in self.vertex_list:
            from_id = vertex_to_node.get(id(pv))
            if not from_id:
                continue
            from_node = network.nodes.get(from_id)
            if not from_node:
                continue
            
            for neighbour_pv in pv.neighbours:
                to_id = vertex_to_node.get(id(neighbour_pv))
                if not to_id:
                    continue
                
                # 避免重复边
                edge_key = tuple(sorted([from_id, to_id]))
                if edge_key in created_edges:
                    continue
                created_edges.add(edge_key)
                
                to_node = network.nodes.get(to_id)
                if to_node and not network.has_edge_between(from_node, to_node):
                    blocking_zone = self._edge_blocked_by_zone(from_node, to_node, zones)
                    if blocking_zone:
                        print(
                            f"[ProceduralRoadmap] 跳过穿越区域的道路: "
                            f"{from_id} -> {to_id} ({blocking_zone.name})"
                        )
                        continue
                    network.create_edge(from_node, to_node, num_lanes=2, bidirectional=True)


def expand_with_procedural_roadmap(
    environment: SimulationEnvironment,
    num_iterations: int = 3
) -> int:
    """
    使用真正仿 procedural_city_generation 的方式扩展路网。
    
    Args:
        environment: 仿真环境
        num_iterations: 生长迭代次数
        
    Returns:
        新增节点数量
    """
    generator = ProceduralRoadmapGenerator(environment)
    new_vertices = generator.grow(num_iterations)
    generator.to_road_network()
    
    return len(new_vertices)
