"""
现实城市规划模块 (Realistic Urban Planning)

基于真实城市规划原则的功能区域规划系统，包含：
1. 服务半径约束 - 学校、医院等设施的服务范围
2. 区域兼容性 - 不同区域类型之间的相邻关系
3. 距离约束 - 最小/最大距离限制
4. 人口密度模型 - 基于区域类型的人口分布
5. LLM辅助决策 - 智能评估选址合理性
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from city.urban_planning.zone import Zone, ZoneType, ZoneManager
from city.utils.vector import Vector2D

if TYPE_CHECKING:
    from city.simulation.environment import SimulationEnvironment


@dataclass
class ZoningConstraints:
    """区域规划约束配置。"""
    
    # 服务半径（米）- 设施能服务的最大距离
    service_radius: dict[ZoneType, float] = None
    
    # 最小间距（米）- 同类型设施之间的最小距离
    min_spacing: dict[ZoneType, float] = None
    
    # 区域兼容性矩阵 - 哪些区域可以相邻
    compatibility: dict[ZoneType, list[ZoneType]] = None
    
    # 最小缓冲距离（米）- 与 incompatible 区域的最小距离
    buffer_distance: dict[ZoneType, float] = None
    
    def __post_init__(self):
        if self.service_radius is None:
            self.service_radius = {
                ZoneType.SCHOOL: 500,      # 学校服务半径500米
                ZoneType.HOSPITAL: 2000,   # 医院服务半径2公里
                ZoneType.PARK: 800,        # 公园服务半径800米
                ZoneType.COMMERCIAL: 1000, # 商业区服务半径1公里
            }
        
        if self.min_spacing is None:
            self.min_spacing = {
                ZoneType.SCHOOL: 300,      # 学校之间至少300米
                ZoneType.HOSPITAL: 1000,   # 医院之间至少1公里
                ZoneType.PARK: 200,        # 公园之间至少200米
                ZoneType.COMMERCIAL: 150,  # 商业区之间至少150米
            }
        
        if self.compatibility is None:
            # 定义每种区域类型兼容的邻居类型
            self.compatibility = {
                ZoneType.RESIDENTIAL: [
                    ZoneType.COMMERCIAL, ZoneType.PARK, ZoneType.SCHOOL,
                    ZoneType.OFFICE, ZoneType.SHOPPING, ZoneType.MIXED_USE
                ],
                ZoneType.COMMERCIAL: [
                    ZoneType.RESIDENTIAL, ZoneType.OFFICE, ZoneType.SHOPPING,
                    ZoneType.MIXED_USE, ZoneType.PARK
                ],
                ZoneType.INDUSTRIAL: [
                    ZoneType.COMMERCIAL, ZoneType.OFFICE, ZoneType.GOVERNMENT
                ],
                ZoneType.HOSPITAL: [
                    ZoneType.RESIDENTIAL, ZoneType.PARK, ZoneType.COMMERCIAL
                ],
                ZoneType.SCHOOL: [
                    ZoneType.RESIDENTIAL, ZoneType.PARK
                ],
                ZoneType.PARK: [
                    ZoneType.RESIDENTIAL, ZoneType.COMMERCIAL, ZoneType.SCHOOL,
                    ZoneType.HOSPITAL, ZoneType.OFFICE
                ],
                ZoneType.OFFICE: [
                    ZoneType.COMMERCIAL, ZoneType.RESIDENTIAL, ZoneType.INDUSTRIAL,
                    ZoneType.PARK
                ],
                ZoneType.MIXED_USE: [
                    ZoneType.RESIDENTIAL, ZoneType.COMMERCIAL, ZoneType.PARK
                ],
                ZoneType.GOVERNMENT: [
                    ZoneType.COMMERCIAL, ZoneType.OFFICE, ZoneType.RESIDENTIAL
                ],
                ZoneType.SHOPPING: [
                    ZoneType.RESIDENTIAL, ZoneType.COMMERCIAL, ZoneType.PARK
                ],
            }
        
        if self.buffer_distance is None:
            self.buffer_distance = {
                ZoneType.INDUSTRIAL: 300,   # 工业区与其他区域至少300米
                ZoneType.HOSPITAL: 100,     # 医院与其他区域至少100米
            }


class RealisticZoningPlanner:
    """
    现实城市规划器。
    
    基于真实城市规划原则，提供智能的区域规划功能。
    """
    
    def __init__(
        self,
        zone_manager: ZoneManager,
        environment: SimulationEnvironment | None = None,
        use_llm: bool = True,
        constraints: ZoningConstraints | None = None
    ):
        self.zone_manager = zone_manager
        self.environment = environment
        self.use_llm = use_llm
        self.constraints = constraints or ZoningConstraints()
        
        # LLM决策记录
        self.last_llm_decision: dict[str, Any] | None = None
        self.llm_decision_history: list[dict[str, Any]] = []
    
    def evaluate_location(
        self,
        zone_type: ZoneType,
        center: Vector2D,
        width: float,
        height: float
    ) -> dict[str, Any]:
        """
        评估一个位置的适宜性。
        
        Returns:
            评估结果，包含分数和详细分析
        """
        test_zone = Zone(zone_type, center, width, height)
        scores = {}
        issues = []
        advantages = []
        
        # 1. 检查区域重叠
        overlapping = self.zone_manager.check_overlap(test_zone)
        if overlapping:
            scores['overlap'] = 0.0
            issues.append(f"与 {len(overlapping)} 个现有区域重叠")
        else:
            scores['overlap'] = 1.0
        
        # 2. 检查与道路的重叠（关键约束）
        road_overlap = self._check_road_overlap(test_zone)
        if road_overlap:
            scores['road_overlap'] = 0.0
            issues.append("与道路重叠")
        else:
            scores['road_overlap'] = 1.0
            # 检查距离道路的适当距离（不能太近也不能太远）
            road_distance_score = self._evaluate_road_distance(center)
            scores['road_distance'] = road_distance_score
            if road_distance_score < 0.3:
                issues.append("距离道路太近")
            elif road_distance_score > 0.8:
                advantages.append("道路距离适中")
        
        # 3. 检查区域兼容性
        compatibility_score = self._evaluate_compatibility(test_zone)
        scores['compatibility'] = compatibility_score
        if compatibility_score < 0.5:
            issues.append("与周边区域类型不兼容")
        elif compatibility_score > 0.8:
            advantages.append("与周边区域类型高度兼容")
        
        # 4. 检查服务半径覆盖
        service_score = self._evaluate_service_coverage(zone_type, center)
        scores['service_coverage'] = service_score
        if service_score < 0.3:
            issues.append("服务覆盖不足")
        elif service_score > 0.8:
            advantages.append("服务覆盖良好")
        
        # 5. 检查最小间距
        spacing_score = self._evaluate_spacing(zone_type, center)
        scores['spacing'] = spacing_score
        if spacing_score < 0.5:
            issues.append("距离同类型设施太近")
        
        # 6. 检查道路可达性
        accessibility_score = self._evaluate_accessibility(center)
        scores['accessibility'] = accessibility_score
        if accessibility_score > 0.8:
            advantages.append("道路可达性良好")
        
        # 6. 特定类型评估
        if zone_type == ZoneType.RESIDENTIAL:
            # 住宅区应靠近公园和学校
            nearby_parks = self._count_nearby_zones(center, ZoneType.PARK, 400)
            nearby_schools = self._count_nearby_zones(center, ZoneType.SCHOOL, 500)
            if nearby_parks > 0:
                scores['nearby_parks'] = 1.0
                advantages.append(f"附近有 {nearby_parks} 个公园")
            else:
                scores['nearby_parks'] = 0.5
            
            if nearby_schools > 0:
                scores['nearby_schools'] = 1.0
                advantages.append(f"附近有 {nearby_schools} 所学校")
            else:
                scores['nearby_schools'] = 0.5
        
        elif zone_type == ZoneType.COMMERCIAL:
            # 商业区应靠近住宅区
            nearby_residential = self._count_nearby_zones(center, ZoneType.RESIDENTIAL, 300)
            if nearby_residential > 0:
                scores['nearby_customers'] = min(1.0, nearby_residential * 0.3)
                advantages.append(f"附近有 {nearby_residential} 个住宅区")
            else:
                scores['nearby_customers'] = 0.3
                issues.append("附近缺乏住宅客群")
        
        # 计算总分
        total_score = sum(scores.values()) / len(scores) if scores else 0.0
        
        # 判断是否适宜（不能有任何重叠，包括区域和道路）
        is_suitable = (total_score >= 0.6 and 
                      not overlapping and 
                      not road_overlap and
                      scores.get('road_distance', 1.0) > 0.3)  # 距离道路不能太近
        
        return {
            'total_score': total_score,
            'scores': scores,
            'issues': issues,
            'advantages': advantages,
            'is_suitable': is_suitable
        }
    
    def _evaluate_compatibility(self, zone: Zone) -> float:
        """评估区域与周边环境的兼容性。"""
        compatible_types = self.constraints.compatibility.get(zone.zone_type, [])
        
        nearby_zones = []
        for other in self.zone_manager.zones.values():
            dist = zone.distance_to_zone(other)
            if dist < 200:  # 200米内的区域
                nearby_zones.append(other)
        
        if not nearby_zones:
            return 0.8  # 没有邻居，默认较好
        
        compatible_count = sum(
            1 for nz in nearby_zones 
            if nz.zone_type in compatible_types or nz.zone_type == zone.zone_type
        )
        
        return compatible_count / len(nearby_zones)
    
    def _check_road_overlap(self, zone: Zone) -> bool:
        """
        检查区域是否与道路重叠。
        
        区域边界应与道路保持一定距离，不能重叠。
        """
        if not self.environment or not self.environment.road_network.edges:
            return False
        
        # 获取区域边界
        min_x, min_y, max_x, max_y = zone.bounds
        
        # 检查每条道路边
        for edge in self.environment.road_network.edges.values():
            from_pos = edge.from_node.position
            to_pos = edge.to_node.position
            
            # 计算道路线段的边界框
            road_min_x = min(from_pos.x, to_pos.x)
            road_max_x = max(from_pos.x, to_pos.x)
            road_min_y = min(from_pos.y, to_pos.y)
            road_max_y = max(from_pos.y, to_pos.y)
            
            # 添加道路宽度缓冲（假设每条车道3.5米，双向共2车道）
            road_width = 7.0  # 2车道 * 3.5米
            
            # 扩展道路边界框以考虑宽度
            road_min_x -= road_width / 2
            road_max_x += road_width / 2
            road_min_y -= road_width / 2
            road_max_y += road_width / 2
            
            # 检查边界框是否重叠
            if (min_x < road_max_x and max_x > road_min_x and
                min_y < road_max_y and max_y > road_min_y):
                
                # 边界框重叠，进行更精确的线段-矩形碰撞检测
                if self._line_intersects_rect(from_pos, to_pos, min_x, min_y, max_x, max_y):
                    return True
        
        return False
    
    def _line_intersects_rect(self, p1: Vector2D, p2: Vector2D, 
                              min_x: float, min_y: float, 
                              max_x: float, max_y: float) -> bool:
        """检查线段是否与矩形相交。"""
        # 使用Cohen-Sutherland算法的思想进行线段裁剪检测
        
        def get_outcode(x, y):
            code = 0
            if x < min_x:
                code |= 1  # 左边
            elif x > max_x:
                code |= 2  # 右边
            if y < min_y:
                code |= 4  # 下边
            elif y > max_y:
                code |= 8  # 上边
            return code
        
        code1 = get_outcode(p1.x, p1.y)
        code2 = get_outcode(p2.x, p2.y)
        
        # 完全在矩形外部
        if code1 & code2 != 0:
            return False
        
        # 完全在矩形内部或跨越边界
        if code1 == 0 or code2 == 0 or (code1 & code2) == 0:
            return True
        
        return False
    
    def _evaluate_road_distance(self, center: Vector2D) -> float:
        """
        评估距离道路的适当距离。
        
        - 距离道路太近（<15米）：噪音、安全问题，扣分
        - 距离道路适中（15-100米）：理想距离，满分
        - 距离道路太远（>200米）：可达性差，扣分
        """
        if not self.environment or not self.environment.road_network.edges:
            return 0.5
        
        # 找到最近的道路距离
        min_distance = float('inf')
        
        for edge in self.environment.road_network.edges.values():
            from_pos = edge.from_node.position
            to_pos = edge.to_node.position
            
            # 计算点到线段的距离
            dist = self._point_to_segment_distance(center, from_pos, to_pos)
            min_distance = min(min_distance, dist)
        
        if min_distance == float('inf'):
            return 0.5
        
        # 评分逻辑
        if min_distance < 15:  # 太近，噪音和安全问题
            return min_distance / 15.0 * 0.3  # 0-0.3分
        elif min_distance <= 100:  # 理想距离
            return 0.8 + (min_distance - 15) / 85.0 * 0.2  # 0.8-1.0分
        elif min_distance <= 200:  # 稍远，但可接受
            return 1.0 - (min_distance - 100) / 100.0 * 0.3  # 0.7-1.0分
        else:  # 太远，可达性差
            return max(0.3, 0.7 - (min_distance - 200) / 100.0 * 0.4)  # 逐渐降低
    
    def _point_to_segment_distance(self, p: Vector2D, a: Vector2D, b: Vector2D) -> float:
        """计算点到线段的距离。"""
        # 向量 AP
        ap_x = p.x - a.x
        ap_y = p.y - a.y
        
        # 向量 AB
        ab_x = b.x - a.x
        ab_y = b.y - a.y
        
        # AB的长度的平方
        ab_len_sq = ab_x * ab_x + ab_y * ab_y
        
        if ab_len_sq == 0:  # A和B重合
            return math.sqrt(ap_x * ap_x + ap_y * ap_y)
        
        # 计算投影参数 t
        t = max(0, min(1, (ap_x * ab_x + ap_y * ab_y) / ab_len_sq))
        
        # 投影点坐标
        proj_x = a.x + t * ab_x
        proj_y = a.y + t * ab_y
        
        # 计算距离
        dx = p.x - proj_x
        dy = p.y - proj_y
        return math.sqrt(dx * dx + dy * dy)
    
    def _evaluate_service_coverage(self, zone_type: ZoneType, center: Vector2D) -> float:
        """评估服务半径覆盖情况。"""
        if zone_type not in self.constraints.service_radius:
            return 0.8  # 无特殊要求
        
        radius = self.constraints.service_radius[zone_type]
        
        # 计算在该半径内的住宅数量
        residential_zones = self.zone_manager.get_zones_by_type(ZoneType.RESIDENTIAL)
        covered_residential = 0
        total_residential_pop = 0
        covered_pop = 0
        
        for res in residential_zones:
            dist = center.distance_to(res.center)
            total_residential_pop += res.population
            if dist <= radius:
                covered_residential += 1
                covered_pop += res.population
        
        if total_residential_pop == 0:
            return 0.5
        
        # 覆盖率分数
        coverage_ratio = covered_pop / total_residential_pop
        return min(1.0, coverage_ratio * 2)  # 覆盖50%人口即得满分
    
    def _evaluate_spacing(self, zone_type: ZoneType, center: Vector2D) -> float:
        """评估与同类型设施的间距。"""
        if zone_type not in self.constraints.min_spacing:
            return 1.0
        
        min_dist = self.constraints.min_spacing[zone_type]
        same_type_zones = self.zone_manager.get_zones_by_type(zone_type)
        
        if not same_type_zones:
            return 1.0
        
        for zone in same_type_zones:
            dist = center.distance_to(zone.center)
            if dist < min_dist:
                return dist / min_dist  # 距离越近分数越低
        
        return 1.0
    
    def _evaluate_accessibility(self, center: Vector2D) -> float:
        """评估道路可达性。"""
        if not self.environment or not self.environment.road_network.nodes:
            return 0.5
        
        # 找到最近的节点
        nearest_dist = float('inf')
        for node in self.environment.road_network.nodes.values():
            dist = center.distance_to(node.position)
            nearest_dist = min(nearest_dist, dist)
        
        # 距离道路越近越好，超过100米开始扣分
        if nearest_dist <= 50:
            return 1.0
        elif nearest_dist <= 100:
            return 0.8
        elif nearest_dist <= 200:
            return 0.5
        else:
            return 0.2
    
    def _count_nearby_zones(
        self, 
        center: Vector2D, 
        zone_type: ZoneType, 
        radius: float
    ) -> int:
        """计算指定半径内某类型区域的数量。"""
        zones = self.zone_manager.get_zones_by_type(zone_type)
        count = 0
        for zone in zones:
            if center.distance_to(zone.center) <= radius:
                count += 1
        return count
    
    def llm_evaluate_location(
        self,
        zone_type: ZoneType,
        center: Vector2D,
        width: float,
        height: float,
        evaluation: dict[str, Any]
    ) -> dict[str, Any] | None:
        """
        使用LLM评估选址合理性。
        
        Args:
            zone_type: 区域类型
            center: 中心位置
            width, height: 尺寸
            evaluation: 基础评估结果
        
        Returns:
            LLM的评估意见
        """
        if not self.use_llm:
            return None
        
        try:
            # 收集周边信息
            nearby_info = self._collect_nearby_info(center)
            
            prompt = f"""你是一位资深城市规划专家。请评估以下选址方案是否合理。

## 选址方案
- 区域类型: {zone_type.display_name}
- 位置: ({center.x:.0f}, {center.y:.0f})
- 尺寸: {width:.0f}m x {height:.0f}m
- 面积: {width * height:.0f}m²

## 自动评估结果
- 综合评分: {evaluation['total_score']:.2f}/1.0
- 兼容性评分: {evaluation['scores'].get('compatibility', 0):.2f}
- 服务覆盖评分: {evaluation['scores'].get('service_coverage', 0):.2f}
- 道路可达性: {evaluation['scores'].get('accessibility', 0):.2f}

## 优点
{chr(10).join(['- ' + adv for adv in evaluation.get('advantages', [])]) if evaluation.get('advantages') else '- 暂无'}

## 问题
{chr(10).join(['- ' + issue for issue in evaluation.get('issues', [])]) if evaluation.get('issues') else '- 暂无'}

## 周边情况
- 200米内区域: {nearby_info['zones_200m']}
- 500米内住宅区: {nearby_info['residential_500m']} 个
- 最近道路节点: {nearby_info['nearest_road']:.0f}m

## 输出格式
请返回JSON格式评估:
{{
    "is_approved": true/false,  // 是否批准此选址
    "score": 0.0-1.0,          // 你的评分
    "reasoning": "详细评估理由",
    "suggestions": "改进建议（如有）",
    "urban_planning_principles": "应用的城市规划原则"
}}
"""
            
            llm_manager = self._get_llm_manager()
            if llm_manager:
                response = llm_manager.request_sync_decision(prompt, timeout=10.0)
                if response:
                    # 解析JSON
                    start = response.find('{')
                    end = response.rfind('}')
                    if start != -1 and end != -1:
                        result = json.loads(response[start:end+1])
                        self.last_llm_decision = {
                            'zone_type': zone_type.name,
                            'center': {'x': center.x, 'y': center.y},
                            'evaluation': result,
                            'timestamp': self.environment.current_time if self.environment else 0
                        }
                        self.llm_decision_history.append(self.last_llm_decision)
                        return result
        
        except Exception as e:
            print(f"[LLM评估] 失败: {e}")
        
        return None
    
    def _collect_nearby_info(self, center: Vector2D) -> dict[str, Any]:
        """收集选址周边的详细信息。"""
        info = {
            'zones_200m': [],
            'residential_500m': 0,
            'nearest_road': float('inf')
        }
        
        # 200米内的区域
        for zone in self.zone_manager.zones.values():
            dist = center.distance_to(zone.center)
            if dist <= 200:
                info['zones_200m'].append(f"{zone.zone_type.display_name}({dist:.0f}m)")
        
        # 500米内的住宅区
        info['residential_500m'] = self._count_nearby_zones(
            center, ZoneType.RESIDENTIAL, 500
        )
        
        # 最近道路
        if self.environment and self.environment.road_network.nodes:
            info['nearest_road'] = min(
                center.distance_to(n.position)
                for n in self.environment.road_network.nodes.values()
            )
        
        info['zones_200m'] = ', '.join(info['zones_200m']) if info['zones_200m'] else '无'
        return info
    
    def find_optimal_location(
        self,
        zone_type: ZoneType,
        min_x: float,
        max_x: float,
        min_y: float,
        max_y: float,
        num_candidates: int = 10
    ) -> dict[str, Any] | None:
        """
        寻找最优选址。
        
        优先寻找被道路包围的区块并填满，如果没有合适的区块则回退到随机生成。
        """
        # 首先尝试寻找道路区块来填充
        block = self.find_block_for_zone(zone_type)
        
        if block:
            # 使用区块填充
            evaluation = self.evaluate_location(
                zone_type, block['center'], block['width'], block['height']
            )
            
            if evaluation['is_suitable']:
                print(f"[Zoning] Found road block for {zone_type.display_name}: "
                      f"{block['width']:.0f}x{block['height']:.0f}m, "
                      f"area {block['area']:.0f}m2")
                
                result = {
                    'center': block['center'],
                    'width': block['width'],
                    'height': block['height'],
                    'score': evaluation['total_score'],
                    'evaluation': evaluation,
                    'llm_evaluation': None,
                    'is_block_fill': True  # 标记为区块填充
                }
                
                # 可选：LLM评估区块选址
                if self.use_llm:
                    llm_result = self.llm_evaluate_location(
                        zone_type, block['center'], block['width'], block['height'],
                        evaluation
                    )
                    if llm_result and llm_result.get('is_approved', True):
                        result['llm_evaluation'] = llm_result
                        result['score'] = result['score'] * 0.7 + llm_result.get('score', 0.5) * 0.3
                
                return result
        
        # 没有找到合适的区块，回退到随机生成候选位置
        print(f"[Zoning] No suitable block for {zone_type.display_name}, using random location")
        
        candidates = []
        
        # 基于区域类型生成候选位置
        for _ in range(num_candidates):
            center = self._generate_candidate_location(
                zone_type, min_x, max_x, min_y, max_y
            )
            if center:
                width = random.uniform(80, 140)
                height = random.uniform(60, 120)
                
                # 评估
                evaluation = self.evaluate_location(zone_type, center, width, height)
                
                if evaluation['is_suitable']:
                    candidates.append({
                        'center': center,
                        'width': width,
                        'height': height,
                        'evaluation': evaluation
                    })
        
        if not candidates:
            return None
        
        # 按评分排序
        candidates.sort(key=lambda x: x['evaluation']['total_score'], reverse=True)
        
        # 对前3名进行LLM评估（如果启用）
        if self.use_llm:
            for candidate in candidates[:3]:
                llm_result = self.llm_evaluate_location(
                    zone_type,
                    candidate['center'],
                    candidate['width'],
                    candidate['height'],
                    candidate['evaluation']
                )
                if llm_result:
                    # 结合LLM评分
                    combined_score = (
                        candidate['evaluation']['total_score'] * 0.6 +
                        llm_result.get('score', 0.5) * 0.4
                    )
                    candidate['evaluation']['total_score'] = combined_score
                    candidate['llm_evaluation'] = llm_result
        
        # 返回最优解
        best = candidates[0]
        return {
            'center': best['center'],
            'width': best['width'],
            'height': best['height'],
            'score': best['evaluation']['total_score'],
            'evaluation': best['evaluation'],
            'llm_evaluation': best.get('llm_evaluation'),
            'is_block_fill': False
        }
    
    def _generate_candidate_location(
        self,
        zone_type: ZoneType,
        min_x: float,
        max_x: float,
        min_y: float,
        max_y: float
    ) -> Vector2D | None:
        """生成候选位置。"""
        candidates = []
        
        if zone_type == ZoneType.RESIDENTIAL:
            # 住宅区：分散布置
            for _ in range(3):
                x = random.uniform(min_x + 100, max_x - 100)
                y = random.uniform(min_y + 100, max_y - 100)
                candidates.append(Vector2D(x, y))
        
        elif zone_type == ZoneType.COMMERCIAL:
            # 商业区：靠近住宅区
            residential = self.zone_manager.get_zones_by_type(ZoneType.RESIDENTIAL)
            if residential:
                for res in residential[-3:]:
                    candidates.append(res.center + Vector2D(
                        random.uniform(-150, 150),
                        random.uniform(-150, 150)
                    ))
            else:
                center_x = (min_x + max_x) / 2
                center_y = (min_y + max_y) / 2
                candidates.append(Vector2D(center_x, center_y))
        
        elif zone_type == ZoneType.SCHOOL:
            # 学校：靠近住宅区但有一定距离
            residential = self.zone_manager.get_zones_by_type(ZoneType.RESIDENTIAL)
            if residential:
                for res in residential[-3:]:
                    # 300-500米范围内
                    angle = random.uniform(0, 2 * math.pi)
                    dist = random.uniform(300, 500)
                    candidates.append(res.center + Vector2D(
                        math.cos(angle) * dist,
                        math.sin(angle) * dist
                    ))
            else:
                center_x = (min_x + max_x) / 2
                center_y = (min_y + max_y) / 2
                candidates.append(Vector2D(center_x, center_y))
        
        elif zone_type == ZoneType.HOSPITAL:
            # 医院：中心位置，交通便利
            center_x = (min_x + max_x) / 2
            center_y = (min_y + max_y) / 2
            candidates = [
                Vector2D(center_x + random.uniform(-200, 200), center_y + random.uniform(-200, 200))
                for _ in range(3)
            ]
        
        elif zone_type == ZoneType.PARK:
            # 公园：靠近住宅区
            residential = self.zone_manager.get_zones_by_type(ZoneType.RESIDENTIAL)
            if residential:
                for res in residential[-2:]:
                    candidates.append(res.center + Vector2D(
                        random.uniform(-100, 100),
                        random.uniform(-100, 100)
                    ))
            else:
                center_x = (min_x + max_x) / 2
                center_y = (min_y + max_y) / 2
                candidates.append(Vector2D(center_x, center_y))
        
        elif zone_type == ZoneType.INDUSTRIAL:
            # 工业区：边缘位置
            candidates = [
                Vector2D(min_x + 150, (min_y + max_y) / 2),
                Vector2D(max_x - 150, (min_y + max_y) / 2),
                Vector2D((min_x + max_x) / 2, min_y + 150),
                Vector2D((min_x + max_x) / 2, max_y - 150)
            ]
        
        else:
            center_x = (min_x + max_x) / 2
            center_y = (min_y + max_y) / 2
            candidates.append(Vector2D(center_x, center_y))
        
        # 随机返回一个候选
        return random.choice(candidates) if candidates else None
    
    def _detect_road_blocks(self) -> list[dict]:
        """
        检测道路网络形成的区块（被道路包围的矩形区域）。
        
        对于正交网格道路，只检测相邻道路之间的基本网格单元。
        返回按面积排序的区块列表，每个区块包含中心和尺寸信息。
        """
        if not self.environment:
            return []
        
        network = self.environment.road_network
        nodes = list(network.nodes.values())
        
        if len(nodes) < 4:
            return []
        
        # 收集所有节点的X和Y坐标
        x_coords = sorted(set(n.position.x for n in nodes))
        y_coords = sorted(set(n.position.y for n in nodes))
        
        blocks = []
        road_width = 20  # 单条道路宽度约20米（考虑双向车道）
        
        # 查找水平道路（Y坐标相同的节点对）
        horizontal_roads = []  # (y, min_x, max_x)
        for y in y_coords:
            x_at_y = sorted([n.position.x for n in nodes if abs(n.position.y - y) < 10])
            if len(x_at_y) >= 2:
                horizontal_roads.append((y, x_at_y[0], x_at_y[-1]))
        
        # 查找垂直道路（X坐标相同的节点对）
        vertical_roads = []  # (x, min_y, max_y)
        for x in x_coords:
            y_at_x = sorted([n.position.y for n in nodes if abs(n.position.x - x) < 10])
            if len(y_at_x) >= 2:
                vertical_roads.append((x, y_at_x[0], y_at_x[-1]))
        
        # 只检测相邻道路之间的区块（基本网格单元）
        horizontal_roads.sort(key=lambda r: r[0])  # 按Y排序
        vertical_roads.sort(key=lambda r: r[0])    # 按X排序
        
        for i in range(len(horizontal_roads) - 1):
            y1 = horizontal_roads[i][0]      # 上道路
            y2 = horizontal_roads[i + 1][0]  # 下道路
            
            # 距离太近的跳过
            if abs(y2 - y1) < 80:
                continue
                
            for j in range(len(vertical_roads) - 1):
                x1 = vertical_roads[j][0]      # 左道路
                x2 = vertical_roads[j + 1][0]  # 右道路
                
                # 距离太近的跳过
                if abs(x2 - x1) < 80:
                    continue
                
                # 创建区块（减去道路宽度）
                inner_width = abs(x2 - x1) - road_width * 2
                inner_height = abs(y2 - y1) - road_width * 2
                
                if inner_width < 50 or inner_height < 50:
                    continue
                
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2
                
                block = {
                    'center': Vector2D(center_x, center_y),
                    'width': inner_width,
                    'height': inner_height,
                    'area': inner_width * inner_height,
                    'bounds': (x1 + road_width, y1 + road_width, 
                              x2 - road_width, y2 - road_width)
                }
                
                if not self._is_block_covered(block):
                    blocks.append(block)
        
        # 按面积排序，优先填充大面积区块
        blocks.sort(key=lambda b: b['area'], reverse=True)
        
        return blocks
    
    def _verify_and_create_block(
        self, x1: float, x2: float, y1: float, y2: float,
        horizontal_roads: list, vertical_roads: list, road_width: float
    ) -> dict | None:
        """验证并创建一个区块。"""
        min_x, max_x = min(x1, x2), max(x1, x2)
        min_y, max_y = min(y1, y2), max(y1, y2)
        
        # 检查四条边是否都有道路
        has_top = any(abs(r[0] - min_y) < 20 for r in horizontal_roads)
        has_bottom = any(abs(r[0] - max_y) < 20 for r in horizontal_roads)
        has_left = any(abs(r[0] - min_x) < 20 for r in vertical_roads)
        has_right = any(abs(r[0] - max_x) < 20 for r in vertical_roads)
        
        if not (has_top and has_bottom and has_left and has_right):
            return None
        
        # 计算区块内部尺寸（减去道路宽度）
        inner_width = max_x - min_x - road_width * 2
        inner_height = max_y - min_y - road_width * 2
        
        if inner_width < 50 or inner_height < 50:
            return None
        
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        
        return {
            'center': Vector2D(center_x, center_y),
            'width': inner_width,
            'height': inner_height,
            'area': inner_width * inner_height,
            'bounds': (min_x + road_width, min_y + road_width, 
                      max_x - road_width, max_y - road_width)
        }
    
    def _is_block_covered(self, block: dict) -> bool:
        """检查区块是否已被现有区域覆盖。"""
        block_center = block['center']
        block_half_w = block['width'] / 2
        block_half_h = block['height'] / 2
        
        # zones 是 dict[str, Zone]，需要使用 .values()
        for zone in self.zone_manager.zones.values():
            zone_half_w = zone.width / 2
            zone_half_h = zone.height / 2
            
            # 检查是否重叠（中心距离小于半宽/半高之和）
            dx = abs(zone.center.x - block_center.x)
            dy = abs(zone.center.y - block_center.y)
            
            if dx < (block_half_w + zone_half_w) * 0.8 and \
               dy < (block_half_h + zone_half_h) * 0.8:
                return True
        
        return False
    
    def find_block_for_zone(self, zone_type: ZoneType) -> dict | None:
        """
        为指定区域类型寻找合适的道路区块。
        
        根据区域类型的特点选择最佳区块：
        - 住宅区：中等大小区块
        - 商业区：靠近中心的大区块
        - 学校：中等大小，靠近住宅区
        - 工业区：边缘的大区块
        """
        blocks = self._detect_road_blocks()
        
        if not blocks:
            return None
        
        scored_blocks = []
        
        for block in blocks:
            score = 0.0
            area = block['area']
            
            # 根据区域类型评分
            if zone_type == ZoneType.RESIDENTIAL:
                # 住宅区：适合各种面积，优先5000-50000平方米
                if 5000 <= area <= 50000:
                    score = 1.0
                elif area < 5000:
                    score = 0.5 + area / 10000  # 小地块也可以建住宅
                else:
                    score = max(0.3, 1.0 - (area - 50000) / 50000)
            
            elif zone_type == ZoneType.COMMERCIAL:
                # 商业区：适合中等以上面积，优先靠近中心
                center = block['center']
                network_info = self._get_network_info()
                if network_info:
                    cx = (network_info['bounds']['min_x'] + network_info['bounds']['max_x']) / 2
                    cy = (network_info['bounds']['min_y'] + network_info['bounds']['max_y']) / 2
                    dist_to_center = math.sqrt((center.x - cx)**2 + (center.y - cy)**2)
                    max_dist = max(network_info['bounds']['max_x'] - network_info['bounds']['min_x'],
                                 network_info['bounds']['max_y'] - network_info['bounds']['min_y']) / 2
                    center_score = max(0, 1.0 - dist_to_center / max_dist)
                    area_score = min(1.0, area / 10000)
                    score = center_score * 0.6 + area_score * 0.4
                else:
                    score = min(1.0, area / 10000)
            
            elif zone_type == ZoneType.SCHOOL:
                # 学校：适合3000-30000平方米
                if 3000 <= area <= 30000:
                    score = 1.0
                elif area < 3000:
                    score = area / 6000
                else:
                    score = max(0.3, 1.0 - (area - 30000) / 30000)
            
            elif zone_type == ZoneType.HOSPITAL:
                # 医院：需要较大面积（10000+平方米）
                if area >= 10000:
                    score = min(1.0, area / 20000)
                else:
                    score = area / 20000  # 小地块也可以建小型医院
            
            elif zone_type == ZoneType.PARK:
                # 公园：各种大小都可以
                score = 0.7 + min(0.3, area / 50000)
            
            elif zone_type == ZoneType.INDUSTRIAL:
                # 工业区：需要大面积
                score = min(1.0, area / 20000)
            
            elif zone_type == ZoneType.OFFICE:
                # 办公区：中等面积
                if 5000 <= area <= 40000:
                    score = 1.0
                else:
                    score = 0.6
            
            else:
                # 其他类型：根据面积评分
                score = min(1.0, area / 10000)
            
            scored_blocks.append((block, score))
        
        # 按评分排序
        scored_blocks.sort(key=lambda x: x[1], reverse=True)
        
        if scored_blocks and scored_blocks[0][1] > 0.3:
            return scored_blocks[0][0]
        
        return None
    
    def _get_network_info(self) -> dict[str, Any]:
        """获取道路网络信息。"""
        if not self.environment:
            return {'nodes': 0, 'bounds': None}
        
        network = self.environment.road_network
        nodes = list(network.nodes.values())
        
        if not nodes:
            return {'nodes': 0, 'bounds': None}
        
        positions = [n.position for n in nodes]
        min_x = min(p.x for p in positions)
        max_x = max(p.x for p in positions)
        min_y = min(p.y for p in positions)
        max_y = max(p.y for p in positions)
        
        return {
            'nodes': len(nodes),
            'bounds': {'min_x': min_x, 'max_x': max_x, 'min_y': min_y, 'max_y': max_y},
            'center': {'x': (min_x + max_x) / 2, 'y': (min_y + max_y) / 2}
        }
    
    def _get_llm_manager(self):
        """获取LLM管理器。"""
        try:
            from city.llm.llm_manager import get_llm_manager
            return get_llm_manager()
        except:
            return None
