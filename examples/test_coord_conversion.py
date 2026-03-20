"""
测试坐标转换。
"""

import sys
sys.path.insert(0, 'd:\\项目\\CITY')

from city.utils.coordinate_conversion import CoordinateConverter
from city.utils.vector import Vector2D

print('=== 坐标转换示例 ===')

converter = CoordinateConverter()

# 测试几个不同的2D坐标
test_points = [
    ("东", Vector2D(100, 0)),
    ("北(屏幕下)", Vector2D(0, 100)),
    ("东南", Vector2D(100, 100)),
    ("西南", Vector2D(-100, 100)),
]

for name, pos2d in test_points:
    print(f'\n{name} 2D: ({pos2d.x:4.0f}, {pos2d.y:4.0f})')
    
    threejs = converter.to_threejs(pos2d)
    unity = converter.to_unity(pos2d)
    
    print(f'  -> Three.js: ({threejs.x:4.0f}, {threejs.y:4.0f}, {threejs.z:4.0f})')
    print(f'  -> Unity:    ({unity.x:4.0f}, {unity.y:4.0f}, {unity.z:4.0f})')

print('\n=== 提示 ===')
print('如果你的3D中道路方向反了，尝试使用不同的转换函数。')
print('最常见的问题是 Y 轴方向，尝试取反 Y 或交换 X/Y。')
