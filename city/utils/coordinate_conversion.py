"""
2D/3D坐标转换工具。

处理不同坐标系之间的转换。
"""

from __future__ import annotations

from dataclasses import dataclass

from city.utils.vector import Vector2D


@dataclass
class Vector3D:
    """三维向量。"""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    
    def __repr__(self) -> str:
        return f"Vector3D({self.x:.2f}, {self.y:.2f}, {self.z:.2f})"


class CoordinateConverter:
    """
    2D/3D坐标转换器。
    
    常见的坐标系约定：
    
    1. OpenGL/WebGL/Three.js (右手系):
       - X: 右
       - Y: 上
       - Z: 出屏幕（向观察者）
       - 2D->3D: (x, y) -> (x, 0, -y) 或 (x, y, 0)
    
    2. Unity (左手系):
       - X: 右
       - Y: 上
       - Z: 前（远离观察者）
       - 2D->3D: (x, y) -> (x, 0, y)
    
    3. Unreal (左手系):
       - X: 前
       - Y: 右
       - Z: 上
       - 2D->3D: (x, y) -> (y, x, 0) 需要调整
    
    4. Matplotlib (2D):
       - X: 右
       - Y: 下（屏幕坐标系）
       - 注意：matplotlib的Y轴可以配置
    """
    
    @staticmethod
    def to_threejs(pos2d: Vector2D, height: float = 0.0) -> Vector3D:
        """
        转换为 Three.js / WebGL 坐标系。
        
        Three.js 使用右手坐标系：
        - X 向右
        - Y 向上
        - Z 指向屏幕外（朝向观察者）
        
        2D中的 Y 向下（matplotlib惯例）对应 3D 中的 -Z
        """
        return Vector3D(
            x=pos2d.x,
            y=height,
            z=-pos2d.y  # Y轴翻转
        )
    
    @staticmethod
    def from_threejs(pos3d: Vector3D) -> Vector2D:
        """从 Three.js 坐标转换回 2D。"""
        return Vector2D(pos3d.x, -pos3d.z)
    
    @staticmethod
    def to_unity(pos2d: Vector2D, height: float = 0.0) -> Vector3D:
        """
        转换为 Unity 坐标系。
        
        Unity 使用左手坐标系：
        - X 向右
        - Y 向上
        - Z 向前（远离观察者）
        """
        return Vector3D(
            x=pos2d.x,
            y=height,
            z=pos2d.y  # Y直接映射到Z
        )
    
    @staticmethod
    def from_unity(pos3d: Vector3D) -> Vector2D:
        """从 Unity 坐标转换回 2D。"""
        return Vector2D(pos3d.x, pos3d.z)
    
    @staticmethod
    def to_unreal(pos2d: Vector2D, height: float = 0.0) -> Vector3D:
        """
        转换为 Unreal 坐标系。
        
        Unreal 使用左手坐标系：
        - X: 前
        - Y: 右
        - Z: 上
        
        注意：Unreal的X是前向，所以需要交换X和Y
        """
        return Vector3D(
            x=pos2d.y,  # 2D的Y变成Unreal的X（前）
            y=pos2d.x,  # 2D的X变成Unreal的Y（右）
            z=height
        )
    
    @staticmethod
    def from_unreal(pos3d: Vector3D) -> Vector2D:
        """从 Unreal 坐标转换回 2D。"""
        return Vector2D(pos3d.y, pos3d.x)
    
    @staticmethod
    def to_blender(pos2d: Vector2D, height: float = 0.0) -> Vector3D:
        """
        转换为 Blender 坐标系。
        
        Blender 使用右手坐标系：
        - X: 右
        - Y: 后（远离观察者）
        - Z: 上
        """
        return Vector3D(
            x=pos2d.x,
            y=-pos2d.y,  # Y翻转（Blender的Y向后）
            z=height
        )
    
    @staticmethod
    def from_blender(pos3d: Vector3D) -> Vector2D:
        """从 Blender 坐标转换回 2D。"""
        return Vector2D(pos3d.x, -pos3d.y)


def convert_road_network_to_3d(
    network,
    converter_type: str = "threejs",
    height: float = 0.0
) -> list[dict]:
    """
    将整个路网转换为3D坐标。
    
    Args:
        network: RoadNetwork对象
        converter_type: 转换器类型 ("threejs", "unity", "unreal", "blender")
        height: 默认高度
        
    Returns:
        节点列表，每个节点包含3D坐标
    """
    converter = CoordinateConverter()
    
    converters = {
        "threejs": converter.to_threejs,
        "unity": converter.to_unity,
        "unreal": converter.to_unreal,
        "blender": converter.to_blender,
    }
    
    if converter_type not in converters:
        raise ValueError(f"Unknown converter: {converter_type}")
    
    convert_func = converters[converter_type]
    
    result = []
    for node_id, node in network.nodes.items():
        pos3d = convert_func(node.position, height)
        result.append({
            "id": node_id,
            "name": node.name,
            "position_2d": node.position,
            "position_3d": pos3d,
            "is_intersection": node.is_intersection
        })
    
    return result


# 示例用法
if __name__ == "__main__":
    # 测试坐标转换
    pos2d = Vector2D(100, 200)
    
    converter = CoordinateConverter()
    
    print(f"原始2D坐标: {pos2d}")
    print(f"Three.js: {converter.to_threejs(pos2d)}")
    print(f"Unity:    {converter.to_unity(pos2d)}")
    print(f"Unreal:   {converter.to_unreal(pos2d)}")
    print(f"Blender:  {converter.to_blender(pos2d)}")
