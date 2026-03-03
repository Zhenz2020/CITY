"""
向量工具类测试。
"""

import sys
sys.path.insert(0, '..')

import math
from city.utils.vector import Vector2D


def test_vector_creation():
    """测试向量创建。"""
    v1 = Vector2D(3, 4)
    assert v1.x == 3
    assert v1.y == 4
    print("[PASS] 向量创建测试通过")


def test_vector_operations():
    """测试向量运算。"""
    v1 = Vector2D(1, 2)
    v2 = Vector2D(3, 4)

    # 加法
    v3 = v1 + v2
    assert v3.x == 4
    assert v3.y == 6

    # 减法
    v4 = v2 - v1
    assert v4.x == 2
    assert v4.y == 2

    # 数乘
    v5 = v1 * 2
    assert v5.x == 2
    assert v5.y == 4

    print("[PASS] 向量运算测试通过")


def test_vector_magnitude():
    """测试向量模长。"""
    v = Vector2D(3, 4)
    assert v.magnitude() == 5.0

    v2 = Vector2D(0, 0)
    assert v2.magnitude() == 0.0

    print("[PASS] 向量模长测试通过")


def test_vector_normalize():
    """测试向量归一化。"""
    v = Vector2D(3, 4)
    normalized = v.normalize()
    assert abs(normalized.magnitude() - 1.0) < 1e-10
    print("[PASS] 向量归一化测试通过")


def test_vector_distance():
    """测试向量距离。"""
    v1 = Vector2D(0, 0)
    v2 = Vector2D(3, 4)
    assert v1.distance_to(v2) == 5.0
    print("[PASS] 向量距离测试通过")


def test_vector_rotate():
    """测试向量旋转。"""
    v = Vector2D(1, 0)
    rotated = v.rotate(math.pi / 2)  # 旋转90度
    assert abs(rotated.x) < 1e-10
    assert abs(rotated.y - 1.0) < 1e-10
    print("[PASS] 向量旋转测试通过")


def run_all_tests():
    """运行所有测试。"""
    print("=" * 50)
    print("向量工具类测试")
    print("=" * 50)

    test_vector_creation()
    test_vector_operations()
    test_vector_magnitude()
    test_vector_normalize()
    test_vector_distance()
    test_vector_rotate()

    print("=" * 50)
    print("所有测试通过!")
    print("=" * 50)


if __name__ == "__main__":
    run_all_tests()
