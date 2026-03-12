"""
城市规划可视化器。

扩展TrafficVisualizer以支持功能区域渲染。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

# 尝试导入matplotlib
try:
    import matplotlib
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    from matplotlib.patches import Rectangle, FancyBboxPatch
    from matplotlib.collections import PatchCollection
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

if TYPE_CHECKING:
    from city.simulation.environment import SimulationEnvironment
    from city.urban_planning.zoning_agent import ZoningAgent


class ZoningVisualizer:
    """
    城市规划可视化器。
    
    专门用于展示城市功能区域规划的可视化器。
    
    Attributes:
        environment: 仿真环境
        zoning_agent: 城市规划智能体
        fig: matplotlib图形对象
        ax: matplotlib坐标轴对象
    """
    
    def __init__(
        self,
        environment: SimulationEnvironment,
        zoning_agent: ZoningAgent | None = None,
        figsize: tuple[int, int] = (14, 12),
        show_labels: bool = True,
        show_stats: bool = True,
        zone_alpha: float = 0.6
    ) -> None:
        if not MATPLOTLIB_AVAILABLE:
            raise ImportError("matplotlib 未安装，无法创建可视化器")
        
        self.environment = environment
        self.zoning_agent = zoning_agent
        self.figsize = figsize
        self.show_labels = show_labels
        self.show_stats = show_stats
        self.zone_alpha = zone_alpha
        
        # 图形对象
        self.fig: Any = None
        self.ax: Any = None
        self.stats_text: Any = None
        self.legend: Any = None
        
        # 缓存绘制的对象
        self._zone_patches: dict[str, Any] = {}
        self._zone_labels: dict[str, Any] = {}
        
        # 初始化图形
        self._init_figure()
    
    def _init_figure(self) -> None:
        """初始化matplotlib图形。"""
        plt.ion()
        self.fig, self.ax = plt.subplots(figsize=self.figsize)
        self.ax.set_aspect('equal')
        self.ax.grid(True, alpha=0.3, linestyle='--')
        self.ax.set_xlabel('X (m)', fontsize=11)
        self.ax.set_ylabel('Y (m)', fontsize=11)
        
        # 绘制道路网络
        self._draw_road_network()
        
        # 添加统计信息文本框
        if self.show_stats:
            self.stats_text = self.ax.text(
                0.02, 0.98, '',
                transform=self.ax.transAxes,
                fontsize=9,
                verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.9)
            )
        
        # 添加图例
        self._add_legend()
        
        # 设置标题
        self._update_title()
        
        plt.tight_layout()
        plt.show(block=False)
    
    def _draw_road_network(self) -> None:
        """绘制道路网络。"""
        if not self.environment.road_network:
            return
        
        network = self.environment.road_network
        all_positions = []
        
        # 绘制路段（在区域下方）
        for edge in network.edges.values():
            x1, y1 = edge.from_node.position.x, edge.from_node.position.y
            x2, y2 = edge.to_node.position.x, edge.to_node.position.y
            
            linewidth = 3 + len(edge.lanes) * 1.5
            
            self.ax.plot(
                [x1, x2], [y1, y2],
                '#607D8B',  # 蓝灰色道路
                linewidth=linewidth,
                solid_capstyle='round',
                zorder=1,
                alpha=0.8
            )
            
            # 车道分隔线
            if len(edge.lanes) > 1:
                self.ax.plot(
                    [x1, x2], [y1, y2],
                    'white',
                    linewidth=1,
                    linestyle='--',
                    alpha=0.6,
                    zorder=2
                )
            
            all_positions.extend([(x1, y1), (x2, y2)])
        
        # 绘制节点
        for node in network.nodes.values():
            x, y = node.position.x, node.position.y
            
            if node.is_intersection:
                circle = plt.Circle(
                    (x, y), 6,
                    facecolor='white',
                    edgecolor='#37474F',
                    linewidth=2,
                    zorder=3
                )
                self.ax.add_patch(circle)
            else:
                self.ax.plot(x, y, 'o', color='#37474F', markersize=4, zorder=3)
            
            if self.show_labels:
                self.ax.text(
                    x, y - 12, node.name,
                    ha='center', va='top',
                    fontsize=7, color='#263238', fontweight='bold'
                )
            
            all_positions.append((x, y))
        
        # 设置坐标轴范围
        if all_positions:
            xs, ys = zip(*all_positions)
            margin = 100
            self.ax.set_xlim(min(xs) - margin, max(xs) + margin)
            self.ax.set_ylim(min(ys) - margin, max(ys) + margin)
    
    def _add_legend(self) -> None:
        """添加区域类型图例。"""
        from city.urban_planning.zone import ZoneType
        
        legend_elements = []
        for zone_type in ZoneType:
            patch = patches.Patch(
                facecolor=zone_type.color,
                edgecolor=zone_type.border_color,
                linewidth=2,
                label=zone_type.display_name,
                alpha=self.zone_alpha
            )
            legend_elements.append(patch)
        
        self.legend = self.ax.legend(
            handles=legend_elements,
            loc='upper right',
            fontsize=9,
            title='区域类型',
            title_fontsize=10,
            framealpha=0.9
        )
    
    def _update_title(self) -> None:
        """更新标题。"""
        title = "城市规划仿真 - 功能区域布局"
        if self.zoning_agent:
            stats = self.zoning_agent.zone_manager.get_statistics()
            title += f"\n区域数: {stats['total_zones']} | 总人口: {stats['total_population']}"
        self.ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
    
    def _draw_zones(self) -> None:
        """绘制功能区域。"""
        if not self.zoning_agent:
            return
        
        current_zone_ids = set()
        
        for zone in self.zoning_agent.zone_manager.zones.values():
            zone_id = zone.zone_id
            current_zone_ids.add(zone_id)
            
            min_x, min_y, max_x, max_y = zone.bounds
            width = max_x - min_x
            height = max_y - min_y
            
            if zone_id in self._zone_patches:
                # 更新现有区域
                patch = self._zone_patches[zone_id]
                patch.set_bounds(min_x, min_y, width, height)
            else:
                # 创建新区域
                rect = FancyBboxPatch(
                    (min_x, min_y),
                    width, height,
                    boxstyle="round,pad=2",
                    facecolor=zone.zone_type.color,
                    edgecolor=zone.zone_type.border_color,
                    linewidth=2,
                    alpha=self.zone_alpha,
                    zorder=0
                )
                self.ax.add_patch(rect)
                self._zone_patches[zone_id] = rect
                
                # 添加区域标签
                if self.show_labels:
                    label = self.ax.text(
                        zone.center.x, zone.center.y,
                        f"{zone.name}\n({zone.population}/{zone.max_population})",
                        ha='center', va='center',
                        fontsize=7,
                        color=zone.zone_type.border_color,
                        fontweight='bold',
                        zorder=4
                    )
                    self._zone_labels[zone_id] = label
            
            # 更新标签
            if zone_id in self._zone_labels:
                label = self._zone_labels[zone_id]
                label.set_text(f"{zone.name}\n({zone.population}/{zone.max_population})")
        
        # 移除已删除的区域
        removed_ids = set(self._zone_patches.keys()) - current_zone_ids
        for zone_id in removed_ids:
            patch = self._zone_patches.pop(zone_id, None)
            if patch:
                patch.remove()
            label = self._zone_labels.pop(zone_id, None)
            if label:
                label.remove()
    
    def _update_stats(self) -> None:
        """更新统计信息。"""
        if not self.show_stats or not self.stats_text:
            return
        
        if not self.zoning_agent:
            return
        
        stats = self.zoning_agent.zone_manager.get_statistics()
        
        # 构建统计字符串
        stats_str = (
            f"仿真时间: {self.environment.current_time:.1f}s\n"
            f"总区域数: {stats['total_zones']}\n"
            f"总人口: {stats['total_population']}\n"
            f"总规划面积: {stats['total_area']:.0f}m²\n"
            f"--- 各类型统计 ---\n"
        )
        
        # 添加各类型统计
        from city.urban_planning.zone import ZoneType
        for zone_type in ZoneType:
            if zone_type.name in stats['by_type']:
                type_stats = stats['by_type'][zone_type.name]
                stats_str += (
                    f"{zone_type.display_name}: {type_stats['count']}个, "
                    f"人口{type_stats['total_population']}\n"
                )
        
        self.stats_text.set_text(stats_str)
    
    def render(self, block: bool = False, pause: float = 0.01) -> None:
        """
        渲染一帧。
        
        Args:
            block: 是否阻塞等待用户输入
            pause: 暂停时间（秒）
        """
        if not MATPLOTLIB_AVAILABLE:
            return
        
        # 更新动态元素
        self._draw_zones()
        self._update_stats()
        self._update_title()
        
        # 刷新显示
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()
        if pause > 0:
            plt.pause(pause)
    
    def save_frame(self, filename: str) -> None:
        """保存当前帧为图片。"""
        if not MATPLOTLIB_AVAILABLE:
            return
        self.fig.savefig(filename, dpi=150, bbox_inches='tight')
    
    def close(self) -> None:
        """关闭可视化窗口。"""
        if not MATPLOTLIB_AVAILABLE:
            return
        plt.ioff()
        plt.close(self.fig)


class IntegratedCityVisualizer:
    """
    集成城市可视化器。
    
    同时显示道路网络、功能区域和交通仿真。
    """
    
    def __init__(
        self,
        environment: SimulationEnvironment,
        zoning_agent: ZoningAgent | None = None,
        figsize: tuple[int, int] = (16, 12),
        enable_zones: bool = True,
        enable_traffic: bool = True
    ) -> None:
        if not MATPLOTLIB_AVAILABLE:
            raise ImportError("matplotlib 未安装")
        
        self.environment = environment
        self.zoning_agent = zoning_agent
        self.figsize = figsize
        self.enable_zones = enable_zones
        self.enable_traffic = enable_traffic
        
        # 创建图形和子图
        plt.ion()
        self.fig = plt.figure(figsize=figsize)
        
        # 创建子图布局
        if enable_zones and enable_traffic:
            # 左右布局
            self.ax_zones = self.fig.add_subplot(121)
            self.ax_traffic = self.fig.add_subplot(122)
        else:
            # 单一视图
            self.ax_zones = self.fig.add_subplot(111) if enable_zones else None
            self.ax_traffic = self.fig.add_subplot(111) if enable_traffic else None
        
        # 初始化视图
        if self.ax_zones:
            self._init_zones_view()
        if self.ax_traffic:
            self._init_traffic_view()
        
        plt.tight_layout()
        plt.show(block=False)
    
    def _init_zones_view(self) -> None:
        """初始化区域视图。"""
        self.ax_zones.set_aspect('equal')
        self.ax_zones.grid(True, alpha=0.3)
        self.ax_zones.set_title('城市规划 - 功能区域', fontsize=12, fontweight='bold')
        self.ax_zones.set_xlabel('X (m)')
        self.ax_zones.set_ylabel('Y (m)')
        
        # 添加图例
        from city.urban_planning.zone import ZoneType
        legend_elements = []
        for zone_type in ZoneType:
            patch = patches.Patch(
                facecolor=zone_type.color,
                edgecolor=zone_type.border_color,
                linewidth=2,
                label=zone_type.display_name,
                alpha=0.6
            )
            legend_elements.append(patch)
        
        self.ax_zones.legend(
            handles=legend_elements,
            loc='upper right',
            fontsize=8,
            title='区域类型'
        )
    
    def _init_traffic_view(self) -> None:
        """初始化交通视图。"""
        self.ax_traffic.set_aspect('equal')
        self.ax_traffic.grid(True, alpha=0.3)
        self.ax_traffic.set_title('交通仿真', fontsize=12, fontweight='bold')
        self.ax_traffic.set_xlabel('X (m)')
        self.ax_traffic.set_ylabel('Y (m)')
    
    def render(self, pause: float = 0.01) -> None:
        """渲染一帧。"""
        # 更新区域视图
        if self.ax_zones and self.zoning_agent:
            self.ax_zones.clear()
            self._init_zones_view()
            self._draw_zones_on_axis(self.ax_zones)
            self._draw_road_network_on_axis(self.ax_zones, alpha=0.5)
        
        # 更新交通视图
        if self.ax_traffic:
            self.ax_traffic.clear()
            self._init_traffic_view()
            self._draw_road_network_on_axis(self.ax_traffic)
            self._draw_vehicles_on_axis(self.ax_traffic)
        
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()
        if pause > 0:
            plt.pause(pause)
    
    def _draw_zones_on_axis(self, ax: Any) -> None:
        """在指定轴上绘制区域。"""
        if not self.zoning_agent:
            return
        
        for zone in self.zoning_agent.zone_manager.zones.values():
            min_x, min_y, max_x, max_y = zone.bounds
            width = max_x - min_x
            height = max_y - min_y
            
            rect = FancyBboxPatch(
                (min_x, min_y),
                width, height,
                boxstyle="round,pad=2",
                facecolor=zone.zone_type.color,
                edgecolor=zone.zone_type.border_color,
                linewidth=2,
                alpha=0.6,
                zorder=0
            )
            ax.add_patch(rect)
            
            # 添加标签
            ax.text(
                zone.center.x, zone.center.y,
                zone.zone_type.display_name,
                ha='center', va='center',
                fontsize=7,
                color=zone.zone_type.border_color,
                fontweight='bold',
                zorder=1
            )
    
    def _draw_road_network_on_axis(self, ax: Any, alpha: float = 1.0) -> None:
        """在指定轴上绘制道路网络。"""
        if not self.environment.road_network:
            return
        
        network = self.environment.road_network
        all_positions = []
        
        for edge in network.edges.values():
            x1, y1 = edge.from_node.position.x, edge.from_node.position.y
            x2, y2 = edge.to_node.position.x, edge.to_node.position.y
            
            ax.plot(
                [x1, x2], [y1, y2],
                '#607D8B',
                linewidth=2,
                solid_capstyle='round',
                zorder=2,
                alpha=alpha
            )
            all_positions.extend([(x1, y1), (x2, y2)])
        
        for node in network.nodes.values():
            x, y = node.position.x, node.position.y
            circle = plt.Circle(
                (x, y), 5,
                facecolor='white',
                edgecolor='#37474F',
                linewidth=1.5,
                zorder=3,
                alpha=alpha
            )
            ax.add_patch(circle)
            all_positions.append((x, y))
        
        if all_positions:
            xs, ys = zip(*all_positions)
            margin = 80
            ax.set_xlim(min(xs) - margin, max(xs) + margin)
            ax.set_ylim(min(ys) - margin, max(ys) + margin)
    
    def _draw_vehicles_on_axis(self, ax: Any) -> None:
        """在指定轴上绘制车辆。"""
        import math
        from matplotlib.patches import FancyBboxPatch
        
        for vehicle in self.environment.vehicles.values():
            x, y = vehicle.position.x, vehicle.position.y
            angle = math.degrees(vehicle.direction.angle())
            
            rect = FancyBboxPatch(
                (x - vehicle.length/2, y - vehicle.width/2),
                vehicle.length, vehicle.width,
                boxstyle="round,pad=0.02",
                facecolor='#3498db',
                edgecolor='black',
                linewidth=1,
                zorder=4
            )
            
            from matplotlib.transforms import Affine2D
            ts = ax.transData
            tr = Affine2D().rotate_deg_around(x, y, angle)
            rect.set_transform(tr + ts)
            ax.add_patch(rect)
    
    def save_frame(self, filename: str) -> None:
        """保存当前帧。"""
        self.fig.savefig(filename, dpi=150, bbox_inches='tight')
    
    def close(self) -> None:
        """关闭可视化。"""
        plt.ioff()
        plt.close(self.fig)
