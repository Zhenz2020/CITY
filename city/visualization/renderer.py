"""
交通仿真可视化渲染器。

使用 matplotlib 实时渲染交通仿真过程。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
import math

# 尝试导入 matplotlib
try:
    import matplotlib
    matplotlib.use('TkAgg')  # 使用 TkAgg 后端以支持交互
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    from matplotlib.patches import FancyBboxPatch, Circle, Rectangle, FancyArrowPatch
    from matplotlib.collections import LineCollection
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("警告: matplotlib 未安装，可视化功能不可用")
    print("请运行: pip install matplotlib")

if TYPE_CHECKING:
    from city.simulation.environment import SimulationEnvironment
    from city.environment.road_network import RoadNetwork, Node, Edge, Lane
    from city.agents.vehicle import Vehicle
    from city.agents.pedestrian import Pedestrian
    from city.agents.traffic_manager import TrafficManager


class TrafficVisualizer:
    """
    交通仿真可视化器。

    实时渲染道路网络、车辆、行人、交通信号灯等。

    Attributes:
        environment: 仿真环境
        fig: matplotlib 图形对象
        ax: matplotlib 坐标轴对象
        update_interval: 更新间隔（秒）
    """

    # 车辆类型颜色映射
    VEHICLE_COLORS = {
        'CAR': '#3498db',        # 蓝色
        'BUS': '#e74c3c',        # 红色
        'TRUCK': '#f39c12',      # 橙色
        'EMERGENCY': '#9b59b6',  # 紫色
        'MOTORCYCLE': '#2ecc71', # 绿色
        'BICYCLE': '#1abc9c'     # 青色
    }

    # 信号灯颜色
    TRAFFIC_LIGHT_COLORS = {
        'RED': '#e74c3c',
        'YELLOW': '#f1c40f',
        'GREEN': '#2ecc71'
    }

    def __init__(
        self,
        environment: SimulationEnvironment,
        figsize: tuple[int, int] = (12, 10),
        update_interval: float = 0.1,
        show_labels: bool = True,
        show_stats: bool = True
    ) -> None:
        if not MATPLOTLIB_AVAILABLE:
            raise ImportError("matplotlib 未安装，无法创建可视化器")

        self.environment = environment
        self.figsize = figsize
        self.update_interval = update_interval
        self.show_labels = show_labels
        self.show_stats = show_stats

        # 图形对象
        self.fig: Any = None
        self.ax: Any = None
        self.stats_text: Any = None

        # 缓存绘制的对象
        self._vehicle_patches: dict[str, Any] = {}
        self._pedestrian_patches: dict[str, Any] = {}
        self._traffic_light_patches: dict[str, Any] = {}
        self._road_lines: list[Any] = []

        # 初始化图形
        self._init_figure()

    def _init_figure(self) -> None:
        """初始化 matplotlib 图形。"""
        plt.ion()  # 开启交互模式
        self.fig, self.ax = plt.subplots(figsize=self.figsize)
        self.ax.set_aspect('equal')
        self.ax.grid(True, alpha=0.3)
        self.ax.set_xlabel('X (m)')
        self.ax.set_ylabel('Y (m)')

        # 绘制静态道路网络
        self._draw_road_network()

        # 添加统计信息文本框
        if self.show_stats:
            self.stats_text = self.ax.text(
                0.02, 0.98, '',
                transform=self.ax.transAxes,
                fontsize=10,
                verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8)
            )

        # 设置标题
        self._update_title()

        plt.tight_layout()
        plt.show(block=False)

    def _draw_road_network(self) -> None:
        """绘制静态道路网络。"""
        if not self.environment.road_network:
            return

        network = self.environment.road_network

        # 计算网络范围用于设置坐标轴
        all_positions = []

        # 绘制路段
        for edge in network.edges.values():
            x1, y1 = edge.from_node.position.x, edge.from_node.position.y
            x2, y2 = edge.to_node.position.x, edge.to_node.position.y

            # 根据车道数调整线宽
            linewidth = 2 + len(edge.lanes) * 2

            # 绘制道路
            line = self.ax.plot(
                [x1, x2], [y1, y2],
                'gray',
                linewidth=linewidth,
                solid_capstyle='round',
                zorder=1
            )[0]
            self._road_lines.append(line)

            # 绘制车道分隔线
            if len(edge.lanes) > 1:
                self.ax.plot(
                    [x1, x2], [y1, y2],
                    'white',
                    linewidth=1,
                    linestyle='--',
                    alpha=0.7,
                    zorder=2
                )

            all_positions.extend([(x1, y1), (x2, y2)])

        # 绘制节点
        for node in network.nodes.values():
            x, y = node.position.x, node.position.y

            if node.is_intersection:
                # 交叉口用圆形表示
                circle = Circle(
                    (x, y), 8,
                    facecolor='lightgray',
                    edgecolor='black',
                    linewidth=2,
                    zorder=3
                )
                self.ax.add_patch(circle)

                # 如果有交通信号灯，添加信号灯指示器
                if node.traffic_light:
                    self._add_traffic_light_visualization(node)
            else:
                # 普通节点用小圆点表示
                self.ax.plot(x, y, 'ko', markersize=5, zorder=3)

            # 节点标签
            if self.show_labels:
                self.ax.text(
                    x, y - 15, node.name,
                    ha='center', va='top',
                    fontsize=8, color='darkblue'
                )

            all_positions.append((x, y))

        # 设置坐标轴范围
        if all_positions:
            xs, ys = zip(*all_positions)
            margin = 50
            self.ax.set_xlim(min(xs) - margin, max(xs) + margin)
            self.ax.set_ylim(min(ys) - margin, max(ys) + margin)

    def _add_traffic_light_visualization(self, node: Any) -> None:
        """添加信号灯可视化。"""
        x, y = node.position.x, node.position.y

        # 信号灯状态指示器
        light_circle = Circle(
            (x + 12, y + 12), 4,
            facecolor='red',
            edgecolor='black',
            linewidth=1,
            zorder=4
        )
        self.ax.add_patch(light_circle)
        self._traffic_light_patches[node.node_id] = light_circle

    def _update_title(self) -> None:
        """更新标题。"""
        time_str = f"Time: {self.environment.current_time:.1f}s"
        agent_str = f"Agents: {len(self.environment.agents)}"
        title = f"交通仿真 - {time_str} | {agent_str}"
        self.ax.set_title(title, fontsize=14, fontweight='bold')

    def _update_traffic_lights(self) -> None:
        """更新信号灯显示。"""
        for node_id, patch in self._traffic_light_patches.items():
            node = self.environment.road_network.get_node(node_id)
            if node and node.traffic_light:
                color = self.TRAFFIC_LIGHT_COLORS.get(
                    node.traffic_light.state.name, 'gray'
                )
                patch.set_facecolor(color)

    def _draw_vehicles(self) -> None:
        """绘制车辆。"""
        current_vehicle_ids = set()

        for vehicle in self.environment.vehicles.values():
            vehicle_id = vehicle.agent_id
            current_vehicle_ids.add(vehicle_id)

            x, y = vehicle.position.x, vehicle.position.y

            # 根据车辆方向计算旋转角度
            angle = math.degrees(vehicle.direction.angle())

            # 车辆大小
            length = vehicle.length
            width = vehicle.width

            # 车辆颜色
            color = self.VEHICLE_COLORS.get(
                vehicle.vehicle_type.name, '#3498db'
            )

            if vehicle_id in self._vehicle_patches:
                # 更新现有车辆位置
                patch = self._vehicle_patches[vehicle_id]
                # 移除旧patch，创建新patch（因为旋转矩形较复杂）
                patch.remove()

                # 创建新车辆矩形
                rect = FancyBboxPatch(
                    (x - length/2, y - width/2),
                    length, width,
                    boxstyle="round,pad=0.02",
                    facecolor=color,
                    edgecolor='black',
                    linewidth=1,
                    zorder=5
                )
                # 使用变换来旋转
                from matplotlib.transforms import Affine2D
                import numpy as np
                ts = self.ax.transData
                coords = ts.transform((x, y))
                tr = Affine2D().rotate_deg_around(x, y, angle)
                rect.set_transform(tr + ts)

                self.ax.add_patch(rect)
                self._vehicle_patches[vehicle_id] = rect
            else:
                # 创建新车辆矩形
                rect = FancyBboxPatch(
                    (x - length/2, y - width/2),
                    length, width,
                    boxstyle="round,pad=0.02",
                    facecolor=color,
                    edgecolor='black',
                    linewidth=1,
                    zorder=5
                )
                self.ax.add_patch(rect)
                self._vehicle_patches[vehicle_id] = rect

                # 添加方向指示箭头
                arrow_length = length + 2
                dx = arrow_length * math.cos(math.radians(angle))
                dy = arrow_length * math.sin(math.radians(angle))
                arrow = FancyArrowPatch(
                    (x, y), (x + dx, y + dy),
                    arrowstyle='->',
                    mutation_scale=10,
                    color='white',
                    linewidth=1.5,
                    zorder=6
                )
                self.ax.add_patch(arrow)
                self._vehicle_patches[f"{vehicle_id}_arrow"] = arrow

        # 移除已消失的车辆
        removed_ids = set(self._vehicle_patches.keys()) - current_vehicle_ids
        for vid in list(removed_ids):
            if not vid.endswith('_arrow'):
                patch = self._vehicle_patches.pop(vid, None)
                if patch:
                    patch.remove()
                arrow = self._vehicle_patches.pop(f"{vid}_arrow", None)
                if arrow:
                    arrow.remove()

    def _draw_pedestrians(self) -> None:
        """绘制行人。"""
        current_pedestrian_ids = set()

        for pedestrian in self.environment.pedestrians.values():
            ped_id = pedestrian.agent_id
            current_pedestrian_ids.add(ped_id)

            x, y = pedestrian.position.x, pedestrian.position.y

            if ped_id in self._pedestrian_patches:
                # 更新位置
                patch = self._pedestrian_patches[ped_id]
                patch.set_center((x, y))
            else:
                # 创建新行人圆点
                circle = Circle(
                    (x, y), pedestrian.size,
                    facecolor='#e67e22',
                    edgecolor='black',
                    linewidth=1,
                    zorder=5
                )
                self.ax.add_patch(circle)
                self._pedestrian_patches[ped_id] = circle

        # 移除已消失的行人
        removed_ids = set(self._pedestrian_patches.keys()) - current_pedestrian_ids
        for pid in removed_ids:
            patch = self._pedestrian_patches.pop(pid, None)
            if patch:
                patch.remove()

    def _update_stats(self) -> None:
        """更新统计信息。"""
        if not self.show_stats or not self.stats_text:
            return

        stats = self.environment.get_statistics()
        stats_str = (
            f"仿真时间: {self.environment.current_time:.1f}s\n"
            f"活跃车辆: {stats['active_vehicles']}\n"
            f"活跃行人: {stats['active_pedestrians']}\n"
            f"已完成车辆: {stats['total_vehicles_completed']}\n"
            f"完成率: {stats['vehicle_completion_rate']*100:.1f}%\n"
            f"总代理数: {stats['total_agents']}"
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
        self._update_traffic_lights()
        self._draw_vehicles()
        self._draw_pedestrians()
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


class SimulationVisualizer:
    """
    集成可视化器的仿真环境包装器。

    简化可视化仿真的使用。
    """

    def __init__(
        self,
        environment: SimulationEnvironment,
        enable_visualization: bool = True,
        **visualizer_kwargs
    ) -> None:
        self.environment = environment
        self.enable_visualization = enable_visualization and MATPLOTLIB_AVAILABLE
        self.visualizer: TrafficVisualizer | None = None

        if self.enable_visualization:
            self.visualizer = TrafficVisualizer(
                environment,
                **visualizer_kwargs
            )

    def step(self) -> bool:
        """执行一步仿真并更新可视化。"""
        result = self.environment.step()

        if self.visualizer and result:
            self.visualizer.render()

        return result

    def run(self, num_steps: int | None = None) -> None:
        """
        运行仿真并实时可视化。

        Args:
            num_steps: 运行步数，None表示运行到结束
        """
        if not self.enable_visualization:
            # 无可视化模式
            self.environment.run(num_steps)
            return

        self.environment.start()
        steps = 0

        try:
            while self.environment.is_running:
                if num_steps and steps >= num_steps:
                    break

                if not self.step():
                    break

                steps += 1

        except KeyboardInterrupt:
            print("\n仿真被用户中断")

        finally:
            if self.visualizer:
                self.visualizer.close()

    def save_screenshot(self, filename: str) -> None:
        """保存当前视图截图。"""
        if self.visualizer:
            self.visualizer.save_frame(filename)
