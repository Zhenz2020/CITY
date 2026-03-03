"""二维向量工具类。"""

from __future__ import annotations

import math
from typing import Union


class Vector2D:
    """二维向量类，用于表示位置和方向。"""

    def __init__(self, x: float = 0.0, y: float = 0.0) -> None:
        self.x = x
        self.y = y

    def __add__(self, other: Vector2D) -> Vector2D:
        return Vector2D(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Vector2D) -> Vector2D:
        return Vector2D(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> Vector2D:
        return Vector2D(self.x * scalar, self.y * scalar)

    def __rmul__(self, scalar: float) -> Vector2D:
        return self * scalar

    def __truediv__(self, scalar: float) -> Vector2D:
        if scalar == 0:
            raise ValueError("不能除以零")
        return Vector2D(self.x / scalar, self.y / scalar)

    def __repr__(self) -> str:
        return f"Vector2D({self.x:.2f}, {self.y:.2f})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Vector2D):
            return False
        return math.isclose(self.x, other.x) and math.isclose(self.y, other.y)

    def magnitude(self) -> float:
        """返回向量的模长。"""
        return math.sqrt(self.x**2 + self.y**2)

    def normalize(self) -> Vector2D:
        """返回单位向量。"""
        mag = self.magnitude()
        if mag == 0:
            return Vector2D(0, 0)
        return self / mag

    def distance_to(self, other: Vector2D) -> float:
        """计算到另一个向量的欧氏距离。"""
        return (self - other).magnitude()

    def dot(self, other: Vector2D) -> float:
        """计算点积。"""
        return self.x * other.x + self.y * other.y

    def angle(self) -> float:
        """返回向量与x轴正方向的夹角（弧度）。"""
        return math.atan2(self.y, self.x)

    def rotate(self, angle: float) -> Vector2D:
        """旋转向量指定角度（弧度）。"""
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        return Vector2D(
            self.x * cos_a - self.y * sin_a,
            self.x * sin_a + self.y * cos_a
        )

    def copy(self) -> Vector2D:
        """返回向量的副本。"""
        return Vector2D(self.x, self.y)

    def to_tuple(self) -> tuple[float, float]:
        """转换为元组。"""
        return (self.x, self.y)

    @staticmethod
    def from_tuple(t: tuple[float, float]) -> Vector2D:
        """从元组创建向量。"""
        return Vector2D(t[0], t[1])

    @staticmethod
    def zero() -> Vector2D:
        """返回零向量。"""
        return Vector2D(0, 0)

    @staticmethod
    def up() -> Vector2D:
        """返回向上单位向量。"""
        return Vector2D(0, 1)

    @staticmethod
    def right() -> Vector2D:
        """返回向右单位向量。"""
        return Vector2D(1, 0)
