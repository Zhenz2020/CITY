"""
璺綉瑙勫垝鏅鸿兘浣?(Road Planning Agent) - 浜哄彛椹卞姩鍩庡競婕斿寲鐗?

鍩轰簬浜哄彛瀵嗗害鑷姩鎵╁睍璺綉鐨勬櫤鑳戒綋锛岄噰鐢ㄧ綉鏍肩姸甯冨眬閬垮厤闀挎潯鍖栥€?
涓撴敞浜庨亾璺綉缁滄墿灞曪紝涓庡煄甯傝鍒掓櫤鑳戒綋鍗忓悓宸ヤ綔銆?
"""

from __future__ import annotations

import json
import math
import os
import random
from typing import TYPE_CHECKING, Any

from city.agents.base import AgentType, BaseAgent
from city.agents.vehicle import Vehicle, VehicleType
from city.utils.vector import Vector2D

if TYPE_CHECKING:
    from city.simulation.environment import SimulationEnvironment
    from city.environment.road_network import Node, Edge


class PopulationCityPlanner(BaseAgent):
    """
    浜哄彛椹卞姩鐨勮矾缃戣鍒掓櫤鑳戒綋銆?
    
    鏍稿績鏈哄埗锛?
    1. 姣忎釜鑺傜偣鏈変竴瀹氫汉鍙ｅ閲?
    2. 杞﹁締浠ｈ〃浜哄彛/閫氬嫟鑰?
    3. 褰撲汉鍙ｅ瘑搴﹁秴杩囬槇鍊硷紝鍩庡競鎵╁紶锛堟坊鍔犳柊鑺傜偣锛?
    4. 鑷姩鍦∣D瀵逛箣闂寸敓鎴愰€氬嫟杞﹁締
    5. 閲囩敤缃戞牸鐘跺竷灞€锛岄伩鍏嶅煄甯傞暱鏉″寲
    
    涓庡煄甯傝鍒掓櫤鑳戒綋(ZoningAgent)鍗忓悓宸ヤ綔锛岃矾缃戞墿寮犲悗鐢盳oningAgent瑙勫垝鍔熻兘鍖哄煙銆?
    
    Attributes:
        population_per_node: 姣忎釜鑺傜偣鐨勪汉鍙ｅ閲?
        current_population: 褰撳墠鎬讳汉鍙ｏ紙杞﹁締鏁帮級
        expansion_threshold: 鎵╁紶闃堝€硷紙浜哄彛瀵嗗害锛?
        auto_spawn_timer: 鑷姩鐢熸垚杞﹁締璁℃椂鍣?
    """
    
    def __init__(
        self,
        environment: SimulationEnvironment | None = None,
        use_llm: bool = True,
        population_per_node: int = 3,
        expansion_threshold: float = 0.8,
        spawn_interval: float = 3.0,
        max_nodes: int = 25,
        min_edge_length: float = 200.0,
        max_edge_length: float = 500.0,
        enable_memory: bool = True
    ):
        super().__init__(AgentType.TRAFFIC_PLANNER, environment, use_llm, enable_memory=enable_memory, memory_capacity=50)
        
        # 浜哄彛绠＄悊
        self.population_per_node = population_per_node
        self.expansion_threshold = expansion_threshold
        self.spawn_interval = spawn_interval
        
        # 璺綉鎵╁睍闄愬埗
        self.max_nodes = max_nodes
        self.min_edge_length = min_edge_length
        self.max_edge_length = max_edge_length
        
        # 鐘舵€?
        self.auto_spawn_timer = 0.0
        self.last_expansion_time = 0.0
        self.expansion_cooldown = 30.0
        
        # 缁熻
        self.total_spawns = 0
        self.expansion_history: list[dict[str, Any]] = []

        # ????????????????????
        self.recent_expansion_directions: list[str] = []
        self.direction_window = 6
        self._procedural_growth_config: dict[str, Any] | None = None
        
        # LLM鍐崇瓥璁板綍锛堢敤浜庡墠绔睍绀猴級
        self.last_decision: dict[str, Any] | None = None
        
        # 鍩庡競婕斿寲闃舵
        self.city_stage = 'initial'  # initial, developing, mature
        self.stage_thresholds = {
            'initial': 4,      # 鍒濆闃舵锛?x2缃戞牸
            'developing': 9,   # 鍙戝睍闃舵锛?x3缃戞牸
            'mature': 16       # 鎴愮啛闃舵锛?x4缃戞牸
        }
        
    def get_population_density(self) -> float:
        """璁＄畻褰撳墠浜哄彛瀵嗗害 (0.0 - 1.0)銆"""
        if not self.environment:
            return 0.0
        
        num_nodes = len(self.environment.road_network.nodes)
        if num_nodes == 0:
            return 0.0
        
        current_vehicles = len(self.environment.vehicles)
        max_capacity = num_nodes * self.population_per_node
        
        return current_vehicles / max_capacity if max_capacity > 0 else 0.0
    
    def get_city_stats(self) -> dict[str, Any]:
        """鑾峰彇鍩庡競缁熻淇℃伅銆"""
        if not self.environment:
            return {}
        
        num_nodes = len(self.environment.road_network.nodes)
        current_vehicles = len(self.environment.vehicles)
        max_capacity = num_nodes * self.population_per_node
        density = self.get_population_density()
        
        # 璁＄畻缃戠粶褰㈢姸鎸囨爣
        network_shape = self._analyze_network_shape()
        
        return {
            'nodes': num_nodes,
            'current_population': current_vehicles,
            'max_capacity': max_capacity,
            'density': density,
            'density_percent': density * 100,
            'expansion_threshold': self.expansion_threshold,
            'should_expand': density >= self.expansion_threshold,
            'total_spawns': self.total_spawns,
            'expansion_count': len(self.expansion_history),
            'network_shape': network_shape
        }
    
    def _analyze_network_shape(self) -> dict[str, Any]:
        """鍒嗘瀽缃戠粶褰㈢姸锛岄伩鍏嶉暱鏉″寲銆"""
        if not self.environment or len(self.environment.road_network.nodes) < 2:
            return {'aspect_ratio': 1.0, 'shape': 'balanced'}
        
        positions = [n.position for n in self.environment.road_network.nodes.values()]
        xs = [p.x for p in positions]
        ys = [p.y for p in positions]
        
        width = max(xs) - min(xs)
        height = max(ys) - min(ys)
        
        if height == 0:
            aspect_ratio = float('inf')
        else:
            aspect_ratio = width / height
        
        # 鍒ゆ柇褰㈢姸
        if aspect_ratio > 2:
            shape = 'too_wide'
        elif aspect_ratio < 0.5:
            shape = 'too_tall'
        else:
            shape = 'balanced'
        
        return {
            'aspect_ratio': aspect_ratio,
            'shape': shape,
            'width': width,
            'height': height
        }
    
    def perceive(self) -> dict[str, Any]:
        """鎰熺煡鍩庡競鐘舵€併€"""
        return {
            'city_stats': self.get_city_stats(),
            'current_time': self.environment.current_time if self.environment else 0
        }
    
    def decide(self) -> dict[str, Any] | None:
        """
        鍐崇瓥锛氭牴鎹汉鍙ｅ瘑搴﹀喅瀹氭槸鍚︽墿寮犲煄甯傘€?
        """
        if not self.environment:
            return None
        
        stats = self.get_city_stats()
        current_time = self.environment.current_time
        self.record_perception(
            {
                'city_stats': stats,
                'current_time': current_time,
                'expansion_history_count': len(self.expansion_history),
            },
            importance=3.0
        )
        if self.has_memory():
            self.get_memory().set_working_memory('latest_city_stats', stats)
        
        # 妫€鏌ュ喎鍗存椂闂?
        if current_time - self.last_expansion_time < self.expansion_cooldown:
            return None
        
        # 妫€鏌ユ槸鍚﹀凡杈炬渶澶ц妯?
        if stats['nodes'] >= self.max_nodes:
            return None
        
        # 浜哄彛瀵嗗害瓒呰繃闃堝€硷紝闇€瑕佹墿寮?
        if stats['density'] >= self.expansion_threshold:
            expansion_plan = self._plan_expansion()
            if expansion_plan:
                self.last_decision = expansion_plan
                self.record_decision(
                    {
                        'action': expansion_plan.get('action', 'expand_city'),
                        'source': 'llm' if expansion_plan.get('is_llm') else 'rule',
                        'expansion_direction': expansion_plan.get('expansion_direction', 'unknown'),
                    },
                    {
                        'density': stats['density'],
                        'reason': expansion_plan.get('reason', ''),
                        'connect_to': expansion_plan.get('connect_to', []),
                    },
                    importance=6.0 if expansion_plan.get('is_llm') else 5.0
                )
                return expansion_plan
        
        return None
    
    def _plan_expansion(self) -> dict[str, Any] | None:
        """瑙勫垝鍩庡競鎵╁紶鏂规锛屼娇鐢↙LM鍐崇瓥鏈€浣充綅缃拰杩炴帴鏂瑰紡銆"""
        if not self.environment:
            return None
        
        network = self.environment.road_network
        if len(network.nodes) == 0:
            return None
        
        # 鏋勫缓缃戠粶鐘舵€佷俊鎭?
        nodes_info = []
        for node in network.nodes.values():
            load = len(node.incoming_edges) + len(node.outgoing_edges)
            nodes_info.append({
                'id': node.node_id,
                'name': node.name,
                'x': node.position.x,
                'y': node.position.y,
                'load': load
            })
        
        # 璁＄畻缃戠粶杈圭晫鍜屽舰鐘?
        positions = [n.position for n in network.nodes.values()]
        min_x, max_x = min(p.x for p in positions), max(p.x for p in positions)
        min_y, max_y = min(p.y for p in positions), max(p.y for p in positions)
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        
        # 璁＄畻褰㈢姸鎸囨爣
        width = max_x - min_x
        height = max_y - min_y
        aspect_ratio = width / height if height > 0 else 1.0
        
        # 纭畾浼樺厛鎵╁睍鏂瑰悜锛堥伩鍏嶉暱鏉″寲锛?
        if aspect_ratio > 1.5:
            preferred_direction = 'vertical'
        elif aspect_ratio < 0.67:
            preferred_direction = 'horizontal'
        else:
            preferred_direction = 'balanced'
        
        if self.use_llm:
            return self._llm_plan_expansion(
                nodes_info, min_x, max_x, min_y, max_y, 
                center_x, center_y, aspect_ratio, preferred_direction
            )
        else:
            return self._rule_plan_expansion(
                nodes_info, min_x, max_x, min_y, max_y,
                center_x, center_y, aspect_ratio, preferred_direction
            )
    
    def _llm_plan_expansion(
        self, nodes_info: list, min_x: float, max_x: float, 
        min_y: float, max_y: float, center_x: float, center_y: float,
        aspect_ratio: float, preferred_direction: str
    ) -> dict[str, Any] | None:
        """浣跨敤LLM瑙勫垝鍩庡競鎵╁紶銆"""
        try:
            prompt = f"""浣犳槸涓€浣嶅煄甯傝鍒掍笓瀹躲€傚熀浜庡綋鍓嶅煄甯傜綉缁滅姸鎬侊紝鍐冲畾鏂板尯鍩熺殑浣嶇疆鍜岃繛鎺ユ柟寮忋€?

## 褰撳墠缃戠粶鐘舵€?
- 鑺傜偣鏁? {len(nodes_info)}
- 缃戠粶鑼冨洿: X[{min_x:.0f}, {max_x:.0f}], Y[{min_y:.0f}, {max_y:.0f}]
- 涓績鐐? ({center_x:.0f}, {center_y:.0f})
- 瀹介珮姣? {aspect_ratio:.2f}
- 浜哄彛瀵嗗害: {self.get_population_density()*100:.0f}%

## 褰㈢姸鍒嗘瀽
褰撳墠鍩庡競缃戠粶褰㈢姸: {preferred_direction}
- 'vertical': 缃戠粶澶锛屽簲浼樺厛鍚戜笂/涓嬫墿灞?
- 'horizontal': 缃戠粶澶珮锛屽簲浼樺厛鍚戝乏/鍙虫墿灞? 
- 'balanced': 缃戠粶鍧囪　锛屽彲鍚戜换浣曟柟鍚戞墿灞?

## 鐜版湁鑺傜偣淇℃伅
{json.dumps(nodes_info[:10], ensure_ascii=False, indent=2)}

## 瑙勫垝绾︽潫
1. **閬垮厤闀挎潯鍖?*: 鏍规嵁褰㈢姸鍒嗘瀽锛屼紭鍏堝湪缂哄皯瑕嗙洊鐨勬柟鍚戞墿灞?
2. **缃戞牸甯冨眬**: 鏂拌妭鐐瑰簲涓庣幇鏈夎妭鐐瑰舰鎴愯繎浼肩綉鏍肩殑甯冨眬
3. **鍙揪鎬?*: 鏂拌妭鐐瑰繀椤讳笌鑷冲皯2涓幇鏈夎妭鐐硅繛鎺ワ紝纭繚璺綉杩為€?
4. **浼樺厛杩炴帴**: 浼樺厛杩炴帴璐熻浇杈冧綆锛堣繛鎺ヨ竟灏戯級鐨勮妭鐐癸紝鍧囪　缃戠粶
5. **璺濈鎺у埗**: 鏂拌妭鐐逛笌鏈€杩戠幇鏈夎妭鐐硅窛绂荤害250-350绫?

## 杈撳嚭鏍煎紡
璇疯繑鍥濲SON鏍煎紡鍐崇瓥:
{{
    "new_node_x": 鍧愭爣x锛堟暣鏁帮級,
    "new_node_y": 鍧愭爣y锛堟暣鏁帮級,
    "connect_to": ["鑺傜偣ID1", "鑺傜偣ID2"],
    "expansion_direction": "鎵╁睍鏂瑰悜鎻忚堪",
    "connect_reason": "閫夋嫨杩欎簺杩炴帴鐨勭悊鐢?,
    "shape_consideration": "濡備綍鏀瑰杽缃戠粶褰㈢姸",
    "reason": "鏁翠綋鍐崇瓥鐞嗙敱"
}}
"""
            
            llm_manager = self._get_llm_manager()
            if llm_manager:
                response = llm_manager.request_sync_decision(prompt, timeout=15.0)
                if response:
                    plan = self._parse_llm_expansion_plan(
                        response, nodes_info, center_x, center_y
                    )
                    if plan:
                        # ?????????????????
                        try:
                            pos_data = plan.get('new_node_position', {})
                            x = float(pos_data.get('x', center_x))
                            y = float(pos_data.get('y', center_y))
                            margin = 10.0
                            in_bounds = (
                                (min_x - margin) <= x <= (max_x + margin)
                                and (min_y - margin) <= y <= (max_y + margin)
                            )
                            if in_bounds:
                                print("[城市扩张] LLM 规划点位于现有边界附近，回退规则规划")
                            else:
                                # ?????????
                                plan_direction = plan.get('expansion_direction')
                                recent = self.recent_expansion_directions
                                if plan_direction and len(recent) >= 2 and recent[-1] == plan_direction and recent[-2] == plan_direction:
                                    print("[城市扩张] 连续同方向扩张，回退规则规划")
                                else:
                                    return plan
                        except Exception:
                            # ???????????
                            print("[城市扩张] LLM 结果不可用，回退规则规划")
        except Exception as e:
            print(f"[城市扩张] LLM 规划失败: {e}")
        
        return self._rule_plan_expansion(
            nodes_info, min_x, max_x, min_y, max_y,
            center_x, center_y, aspect_ratio, preferred_direction
        )
    
    def _parse_llm_expansion_plan(
        self, response: str, nodes_info: list, center_x: float, center_y: float
    ) -> dict[str, Any] | None:
        """瑙ｆ瀽LLM鐨勬墿寮犺鍒掑搷搴斻€"""
        try:
            start = response.find('{')
            end = response.rfind('}')
            if start == -1 or end == -1:
                return None
            
            plan = json.loads(response[start:end+1])
            
            # 楠岃瘉鑺傜偣ID
            connect_to = plan.get('connect_to', [])
            valid_nodes = [n['id'] for n in nodes_info]
            valid_connections = [nid for nid in connect_to if nid in valid_nodes]
            
            if len(valid_connections) < 1:
                return None
            
            return {
                'action': 'expand_city',
                'new_node_position': {
                    'x': plan.get('new_node_x', center_x),
                    'y': plan.get('new_node_y', center_y)
                },
                'connect_to': valid_connections[:3],
                'expansion_direction': plan.get('expansion_direction', '未知'),
                'connect_reason': plan.get('connect_reason', ''),
                'shape_consideration': plan.get('shape_consideration', ''),
                'reason': plan.get('reason', 'LLM规划'),
                'is_llm': True
            }
            
        except Exception as e:
            print(f"[城市扩张] 解析 LLM 响应失败: {e}")
            return None
    
    def _get_zones_for_expansion_planning(self) -> list:
        """鑾峰彇鐜版湁鍖哄煙鍒楄〃鐢ㄤ簬鎵╁紶瑙勫垝銆"""
        zoning_agent = self._get_zoning_agent()
        if zoning_agent and hasattr(zoning_agent, 'zone_manager'):
            return list(zoning_agent.zone_manager.zones.values())
        return []

    def _load_procedural_growth_config(self) -> dict[str, Any]:
        """加载 procedural_city_generation 的 roadmap 参数。"""
        if self._procedural_growth_config is not None:
            return self._procedural_growth_config

        default_conf: dict[str, Any] = {
            "gridpForward": 100.0,
            "gridpTurn": 9.0,
            "gridlMin": 1.0,
            "gridlMax": 1.0,
            "organicpForward": 92.0,
            "organicpTurn": 7.0,
            "organiclMin": 0.8,
            "organiclMax": 1.6,
            "radialpForward": 100.0,
            "radialpTurn": 10.0,
            "radiallMin": 0.8,
            "radiallMax": 1.5,
        }

        try:
            conf_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "procedural_city_generation-master",
                "procedural_city_generation",
                "inputs",
                "roadmap.conf",
            )
            if os.path.exists(conf_path):
                with open(conf_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                for k, v in raw.items():
                    if isinstance(v, dict) and "value" in v:
                        default_conf[k] = v["value"]
                    else:
                        default_conf[k] = v
        except Exception as e:
            print(f"[城市扩张] 读取 procedural roadmap.conf 失败，使用默认参数: {e}")

        self._procedural_growth_config = default_conf
        return default_conf

    def _find_procedural_expansion_candidates(
        self,
        nodes_info: list[dict[str, Any]],
        grid_size: float,
        preferred_direction: str,
    ) -> list[dict[str, Any]]:
        """
        参考 procedural_city_generation 的 grid/organic/radial growth 规则生成候选点。
        """
        if not nodes_info:
            return []

        conf = self._load_procedural_growth_config()
        center_x = sum(n["x"] for n in nodes_info) / len(nodes_info)
        center_y = sum(n["y"] for n in nodes_info) / len(nodes_info)
        existing_positions = [(n["x"], n["y"]) for n in nodes_info]

        leftmost_x = min(n["x"] for n in nodes_info)
        rightmost_x = max(n["x"] for n in nodes_info)
        topmost_y = min(n["y"] for n in nodes_info)
        bottommost_y = max(n["y"] for n in nodes_info)
        frontier_nodes = [
            n for n in nodes_info
            if abs(n["x"] - leftmost_x) < 12
            or abs(n["x"] - rightmost_x) < 12
            or abs(n["y"] - topmost_y) < 12
            or abs(n["y"] - bottommost_y) < 12
        ]
        if not frontier_nodes:
            frontier_nodes = nodes_info[:]

        min_node_gap = max(self.min_edge_length * 0.7, grid_size * 0.55)
        min_length = max(self.min_edge_length * 0.75, grid_size * 0.7)
        max_length = max(self.max_edge_length * 0.9, grid_size * 1.25)

        def _too_close(x: float, y: float) -> bool:
            for ex, ey in existing_positions:
                if math.hypot(x - ex, y - ey) < min_node_gap:
                    return True
            return False

        def _direction_label(dx: float, dy: float) -> str:
            if abs(dx) > abs(dy):
                return "right" if dx >= 0 else "left"
            return "down" if dy >= 0 else "up"

        def _normalize(vx: float, vy: float) -> tuple[float, float]:
            norm = math.hypot(vx, vy)
            if norm < 1e-6:
                return (1.0, 0.0)
            return (vx / norm, vy / norm)

        candidates: list[dict[str, Any]] = []

        for anchor in frontier_nodes:
            ax, ay = anchor["x"], anchor["y"]
            vx, vy = _normalize(ax - center_x, ay - center_y)
            if preferred_direction == "horizontal":
                vx, vy = _normalize(vx + random.choice([-0.2, 0.2]), vy * 0.4)
            elif preferred_direction == "vertical":
                vx, vy = _normalize(vx * 0.4, vy + random.choice([-0.2, 0.2]))

            # 1) grid 风格（正交、直线延展）
            grid_len = random.uniform(
                float(conf.get("gridlMin", 1.0)) * grid_size * 0.9,
                float(conf.get("gridlMax", 1.0)) * grid_size * 1.05,
            )
            gx = ax + round(vx) * max(min_length, min(max_length, grid_len))
            gy = ay + round(vy) * max(min_length, min(max_length, grid_len))
            if not _too_close(gx, gy):
                candidates.append({
                    "x": gx,
                    "y": gy,
                    "direction": _direction_label(gx - ax, gy - ay),
                    "anchor": anchor,
                    "priority": 1 if preferred_direction in ("horizontal", "vertical") else 2,
                    "type": "procedural_grid",
                    "source": "procedural",
                })

            # 2) organic 风格（偏转 30~120 度）
            organic_len = random.uniform(
                float(conf.get("organiclMin", 0.8)) * grid_size * 0.85,
                float(conf.get("organiclMax", 1.6)) * grid_size * 1.1,
            )
            turn = random.choice([-1, 1]) * random.uniform(30, 120)
            rad = math.radians(turn)
            ox = vx * math.cos(rad) - vy * math.sin(rad)
            oy = vx * math.sin(rad) + vy * math.cos(rad)
            ox, oy = _normalize(ox, oy)
            oxp = ax + ox * max(min_length, min(max_length, organic_len))
            oyp = ay + oy * max(min_length, min(max_length, organic_len))
            if not _too_close(oxp, oyp):
                candidates.append({
                    "x": oxp,
                    "y": oyp,
                    "direction": _direction_label(oxp - ax, oyp - ay),
                    "anchor": anchor,
                    "priority": 2,
                    "type": "procedural_organic",
                    "source": "procedural",
                })

            # 3) radial 风格（向中心/离中心辐射）
            radial_len = random.uniform(
                float(conf.get("radiallMin", 0.8)) * grid_size * 0.85,
                float(conf.get("radiallMax", 1.5)) * grid_size * 1.1,
            )
            rsign = random.choice([1.0, -1.0])
            rx, ry = _normalize((ax - center_x) * rsign, (ay - center_y) * rsign)
            rxp = ax + rx * max(min_length, min(max_length, radial_len))
            ryp = ay + ry * max(min_length, min(max_length, radial_len))
            if not _too_close(rxp, ryp):
                candidates.append({
                    "x": rxp,
                    "y": ryp,
                    "direction": _direction_label(rxp - ax, ryp - ay),
                    "anchor": anchor,
                    "priority": 2,
                    "type": "procedural_radial",
                    "source": "procedural",
                })

        return candidates
    
    def _find_expansion_candidates_with_zones(
        self, nodes_info: list, grid_size: float, preferred_direction: str
    ) -> list:
        """
        鎵惧埌鎵╁紶鍊欓€変綅缃?- 涓ユ牸浠庡綋鍓嶆渶澶栧洿鍚戝鎵╁睍銆?
        
        鍙€冭檻鍦ㄥ綋鍓嶈矾缃戞渶澶栧洿涔嬪鐨勪綅缃紝纭繚鍩庡競鍚戝鐢熼暱銆?
        """
        candidates = []
        
        # 鎵惧埌鏈€澶栧洿鐨勫潗鏍?
        leftmost_x = min(n['x'] for n in nodes_info)
        rightmost_x = max(n['x'] for n in nodes_info)
        topmost_y = min(n['y'] for n in nodes_info)
        bottommost_y = max(n['y'] for n in nodes_info)
        
        # 鍙湪鏈€澶栧洿涔嬪娣诲姞鍊欓€変綅缃?
        # 鍚戝乏鎵╁睍 - 鍦ㄦ渶宸︿晶涔嬪
        leftmost_nodes = [n for n in nodes_info if abs(n['x'] - leftmost_x) < 10]
        for n in leftmost_nodes:
            new_x = leftmost_x - grid_size
            candidates.append({
                'x': new_x,
                'y': n['y'],
                'direction': 'left',
                'anchor': n,
                'priority': 1 if preferred_direction == 'horizontal' else 2,
                'type': 'grid_outward'
            })
        
        # 鍚戝彸鎵╁睍 - 鍦ㄦ渶鍙充晶涔嬪
        rightmost_nodes = [n for n in nodes_info if abs(n['x'] - rightmost_x) < 10]
        for n in rightmost_nodes:
            new_x = rightmost_x + grid_size
            candidates.append({
                'x': new_x,
                'y': n['y'],
                'direction': 'right',
                'anchor': n,
                'priority': 1 if preferred_direction == 'horizontal' else 2,
                'type': 'grid_outward'
            })
        
        # 鍚戜笂鎵╁睍 - 鍦ㄦ渶涓婃柟涔嬪
        topmost_nodes = [n for n in nodes_info if abs(n['y'] - topmost_y) < 10]
        for n in topmost_nodes:
            new_y = topmost_y - grid_size
            candidates.append({
                'x': n['x'],
                'y': new_y,
                'direction': 'up',
                'anchor': n,
                'priority': 1 if preferred_direction == 'vertical' else 2,
                'type': 'grid_outward'
            })
        
        # 鍚戜笅鎵╁睍 - 鍦ㄦ渶涓嬫柟涔嬪
        bottommost_nodes = [n for n in nodes_info if abs(n['y'] - bottommost_y) < 10]
        for n in bottommost_nodes:
            new_y = bottommost_y + grid_size
            candidates.append({
                'x': n['x'],
                'y': new_y,
                'direction': 'down',
                'anchor': n,
                'priority': 1 if preferred_direction == 'vertical' else 2,
                'type': 'grid_outward'
            })
        
        return candidates
    
    def _line_intersects_zone(self, x1: float, y1: float, x2: float, y2: float, zone) -> bool:
        """妫€鏌ョ嚎娈垫槸鍚︿笌鍖哄煙鐩镐氦锛堣€冭檻閬撹矾缂撳啿锛夈€"""
        road_buffer = 30  # 閬撹矾鍗婂 + 瀹夊叏璺濈
        
        # 鎵╁睍鍖哄煙杈圭晫浠ュ寘鍚亾璺紦鍐?
        zone_min_x = zone.center.x - zone.width / 2 - road_buffer
        zone_max_x = zone.center.x + zone.width / 2 + road_buffer
        zone_min_y = zone.center.y - zone.height / 2 - road_buffer
        zone_max_y = zone.center.y + zone.height / 2 + road_buffer
        
        # 蹇€熸鏌ワ細濡傛灉涓や釜绔偣閮藉湪鍖哄煙鍚屼竴渚э紝涓嶄細鐩镐氦
        if (x1 < zone_min_x and x2 < zone_min_x) or (x1 > zone_max_x and x2 > zone_max_x):
            return False
        if (y1 < zone_min_y and y2 < zone_min_y) or (y1 > zone_max_y and y2 > zone_max_y):
            return False
        
        # 浣跨敤 Liang-Barsky 绠楁硶妫€鏌ョ嚎娈典笌鐭╁舰鐩镐氦
        dx = x2 - x1
        dy = y2 - y1
        
        p = [-dx, dx, -dy, dy]
        q = [x1 - zone_min_x, zone_max_x - x1, y1 - zone_min_y, zone_max_y - y1]
        
        u1 = 0
        u2 = 1
        
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
    
    def _find_path_around_zones(
        self, from_node, to_node, zones: list
    ) -> list[dict] | None:
        """
        瀵绘壘缁曡繃鍔熻兘鍖哄煙鐨勮矾寰勶紙鎶樼嚎璺緞锛夈€?
        
        杩斿洖璺緞涓婄殑涓棿鐐瑰垪琛紙涓嶅寘鍚捣鐐瑰拰缁堢偣锛夈€?
        璺緞娌跨潃鍖哄煙杈圭紭璧般€?
        """
        x1, y1 = from_node.position.x, from_node.position.y
        x2, y2 = to_node.position.x, to_node.position.y
        
        # 妫€鏌ョ洿鎺ヨ繛鎺ユ槸鍚︿細绌胯繃鍖哄煙
        intersects = False
        for zone in zones:
            if self._line_intersects_zone(x1, y1, x2, y2, zone):
                intersects = True
                break
        
        if not intersects:
            # 鐩存帴杩炴帴涓嶄細绌胯繃鍖哄煙
            return []
        
        # 闇€瑕佺粫琛岋紝娌跨潃鍖哄煙杈圭紭璧?
        # 鎵惧埌闇€瑕佺粫琛岀殑鍖哄煙
        blocking_zones = []
        for zone in zones:
            if self._line_intersects_zone(x1, y1, x2, y2, zone):
                blocking_zones.append(zone)
        
        if not blocking_zones:
            return []
        
        # 绠€鍗曠瓥鐣ワ細娌跨潃闃绘尅鍖哄煙鐨勮竟缂樿蛋
        # 閫夋嫨鏈€杩戠殑闃绘尅鍖哄煙锛屼粠鍏惰竟缂樼粫琛?
        nearest_zone = min(blocking_zones, 
            key=lambda z: ((z.center.x - (x1+x2)/2)**2 + (z.center.y - (y1+y2)/2)**2))
        
        road_buffer = 40
        
        # 鍖哄煙杈圭晫锛堝惈閬撹矾缂撳啿锛?
        z_min_x = nearest_zone.center.x - nearest_zone.width / 2 - road_buffer
        z_max_x = nearest_zone.center.x + nearest_zone.width / 2 + road_buffer
        z_min_y = nearest_zone.center.y - nearest_zone.height / 2 - road_buffer
        z_max_y = nearest_zone.center.y + nearest_zone.height / 2 + road_buffer
        
        # 鍒ゆ柇浠庡摢涓柟鍚戠粫琛?
        # 姣旇緝涓ょ缁曡鏂规鐨勭粫琛岃窛绂?
        
        # 鏂规1锛氫粠涓婃柟/涓嬫柟缁曡锛堟按骞虫柟鍚戣繛鎺ワ級
        if abs(x2 - x1) > abs(y2 - y1):
            # 姘村钩杩炴帴锛屼粠涓婃柟鎴栦笅鏂圭粫琛?
            mid_x = (x1 + x2) / 2
            
            # 璁＄畻涓や釜缁曡鏂规鐨勪唬浠?
            # 浠庝笂鏂圭粫琛?
            path_top = [
                {'x': mid_x, 'y': z_min_y, 'type': 'corner'},
            ]
            # 浠庝笅鏂圭粫琛?
            path_bottom = [
                {'x': mid_x, 'y': z_max_y, 'type': 'corner'},
            ]
            
            # 閫夋嫨缁曡璺濈鏇寸煭鐨勬柟妗?
            dist_via_top = abs(y1 - z_min_y) + abs(z_min_y - y2)
            dist_via_bottom = abs(y1 - z_max_y) + abs(z_max_y - y2)
            
            return path_top if dist_via_top < dist_via_bottom else path_bottom
        
        else:
            # 鍨傜洿杩炴帴锛屼粠宸︿晶鎴栧彸渚х粫琛?
            mid_y = (y1 + y2) / 2
            
            # 浠庡乏渚х粫琛?
            path_left = [
                {'x': z_min_x, 'y': mid_y, 'type': 'corner'},
            ]
            # 浠庡彸渚х粫琛?
            path_right = [
                {'x': z_max_x, 'y': mid_y, 'type': 'corner'},
            ]
            
            # 閫夋嫨缁曡璺濈鏇寸煭鐨勬柟妗?
            dist_via_left = abs(x1 - z_min_x) + abs(z_min_x - x2)
            dist_via_right = abs(x1 - z_max_x) + abs(z_max_x - x2)
            
            return path_left if dist_via_left < dist_via_right else path_right
    
    def _rule_plan_expansion(
        self, nodes_info: list, min_x: float, max_x: float,
        min_y: float, max_y: float, center_x: float, center_y: float,
        aspect_ratio: float, preferred_direction: str
    ) -> dict[str, Any] | None:
        """浣跨敤瑙勫垯瑙勫垝鍩庡競鎵╁紶锛屾柊鑺傜偣鍦ㄥ鍥达紝閬撹矾娌垮尯鍩熻竟缂樿蛋锛堟姌绾匡級銆"""
        # 鏀堕泦鎵€鏈夌幇鏈夌殑X鍜孻鍧愭爣
        existing_x = sorted(set(n['x'] for n in nodes_info))
        existing_y = sorted(set(n['y'] for n in nodes_info))
        
        # 璁＄畻缃戞牸闂磋窛
        x_gaps = [existing_x[i+1] - existing_x[i] for i in range(len(existing_x)-1)]
        y_gaps = [existing_y[i+1] - existing_y[i] for i in range(len(existing_y)-1)]
        grid_size = 300
        if x_gaps:
            grid_size = max(250, min(350, sum(x_gaps) / len(x_gaps)))
        elif y_gaps:
            grid_size = max(250, min(350, sum(y_gaps) / len(y_gaps)))
        
        # 璁＄畻褰撳墠杈圭晫锛堝湪鎵€鏈夊垎鏀兘闇€瑕侊級
        leftmost_x = min(n['x'] for n in nodes_info)
        rightmost_x = max(n['x'] for n in nodes_info)
        topmost_y = min(n['y'] for n in nodes_info)
        bottommost_y = max(n['y'] for n in nodes_info)
        
        # 鑾峰彇鍊欓€変綅缃?
        candidates = self._find_expansion_candidates_with_zones(
            nodes_info, grid_size, preferred_direction
        )
        candidates.extend(
            self._find_procedural_expansion_candidates(
                nodes_info=nodes_info,
                grid_size=grid_size,
                preferred_direction=preferred_direction,
            )
        )
        
        # 杩囨护鎺夊凡缁忓瓨鍦ㄧ殑鑺傜偣浣嶇疆
        existing_positions = {(n['x'], n['y']) for n in nodes_info}
        candidates = [c for c in candidates if (c['x'], c['y']) not in existing_positions]
        # 去重（同坐标只保留更高优先级）
        unique_candidates: dict[tuple[float, float], dict[str, Any]] = {}
        for c in candidates:
            key = (round(c["x"], 1), round(c["y"], 1))
            old = unique_candidates.get(key)
            if old is None or (c.get("priority", 9) < old.get("priority", 9)):
                unique_candidates[key] = c
        candidates = list(unique_candidates.values())
        
        # 鑾峰彇鍖哄煙鍒楄〃鐢ㄤ簬璺緞瑙勫垝
        zones = self._get_zones_for_expansion_planning()
        
        if not candidates:
            # 濡傛灉娌℃湁鍊欓€夛紝鍚戝榛樿鎵╁睍
            if preferred_direction == 'horizontal':
                target_x = rightmost_x + grid_size
                target_y = existing_y[len(existing_y)//2] if existing_y else center_y
                expansion_direction = 'right'
            else:
                target_x = existing_x[len(existing_x)//2] if existing_x else center_x
                target_y = bottommost_y + grid_size
                expansion_direction = 'down'
            anchor_node = nodes_info[0]
            candidate_type = 'grid'
        else:
            # 浼樺厛閫夋嫨浼樺厛绾ч珮鐨勫€欓€?
            # ????????????????????
            direction_counts = {}
            for d in self.recent_expansion_directions:
                direction_counts[d] = direction_counts.get(d, 0) + 1

            def _candidate_score(c):
                dir_count = direction_counts.get(c['direction'], 0)
                source_bonus = 0 if c.get("source") == "procedural" else 1
                type_pref = 0 if c.get("type") == "procedural_grid" else 1
                return (c['priority'], source_bonus, type_pref, dir_count, c['anchor']['load'], random.random() * 0.01)

            candidates.sort(key=_candidate_score)
            
            best_candidate = candidates[0]
            target_x = best_candidate['x']
            target_y = best_candidate['y']
            expansion_direction = best_candidate['direction']
            anchor_node = best_candidate['anchor']
            candidate_type = best_candidate.get('type', 'grid')
        allow_non_orthogonal = candidate_type in {'procedural_organic', 'procedural_radial'}
        
        # 閫夋嫨杩炴帴鑺傜偣 - 杩炴帴鍒版墍鏈夊悎閫傜殑澶栧洿閭诲眳锛堝舰鎴愮綉鏍肩粨鏋勶級
        connect_to = []
        path_waypoints = {}  # 瀛樺偍姣忎釜杩炴帴鐨勮矾寰勭偣
        
        # 鎵惧埌鎵€鏈夊鍥磋妭鐐?
        outer_nodes = [
            n for n in nodes_info
            if abs(n['x'] - leftmost_x) < 10 or
               abs(n['x'] - rightmost_x) < 10 or
               abs(n['y'] - topmost_y) < 10 or
               abs(n['y'] - bottommost_y) < 10
        ]
        
        if not outer_nodes:
            # 濡傛灉娌℃湁澶栧洿鑺傜偣锛屼娇鐢ㄦ渶杩戠殑鑺傜偣
            nearest = min(nodes_info, key=lambda n: (n['x'] - target_x)**2 + (n['y'] - target_y)**2)
            connect_to.append(nearest['id'])
        else:
            # 鎵惧埌鎵€鏈夊湪鍚堥€傝窛绂诲唴鐨勫鍥撮偦灞?
            # 瀵逛簬缃戞牸甯冨眬锛屾柊鑺傜偣搴旇杩炴帴鍒扮浉閭荤殑澶栧洿鑺傜偣
            
            for outer_node in outer_nodes:
                # 璁＄畻璺濈
                dist = ((outer_node['x'] - target_x)**2 + (outer_node['y'] - target_y)**2) ** 0.5
                
                # 鍙€冭檻璺濈鍦ㄥ悎鐞嗚寖鍥村唴鐨勮妭鐐癸紙缃戞牸闂磋窛鐨?.5鍊嶄互鍐咃級
                if dist > grid_size * 1.5:
                    continue
                
                # 妫€鏌ユ槸鍚︽槸姝ｄ氦鏂瑰悜鐨勯偦灞咃紙X鎴朰鍧愭爣鐩稿悓鎴栨帴杩戯級
                dx = abs(outer_node['x'] - target_x)
                dy = abs(outer_node['y'] - target_y)
                
                # 姝ｄ氦閭诲眳锛氫富瑕佹槸姘村钩鎴栧瀭鐩存柟鍚?
                is_orthogonal = min(dx, dy) < 50
                is_near_diagonal = abs(dx - dy) < 80 and max(dx, dy) <= grid_size * 1.35

                if not allow_non_orthogonal and not is_orthogonal and not is_near_diagonal:
                    continue
                
                # 娣诲姞鍒拌繛鎺ュ垪琛?
                connect_to.append(outer_node['id'])
                
                # 璁＄畻鍒拌繖涓妭鐐圭殑璺緞锛堣€冭檻鍖哄煙缁曡锛?
                if self.environment:
                    from_node_obj = None
                    for node in self.environment.road_network.nodes.values():
                        if node.node_id == outer_node['id']:
                            from_node_obj = node
                            break
                    
                    if from_node_obj:
                        temp_pos = Vector2D(target_x, target_y)
                        temp_node = type('TempNode', (), {'position': temp_pos})()
                        
                        path = self._find_path_around_zones(temp_node, from_node_obj, zones)
                        if path:
                            path_waypoints[outer_node['id']] = path
            
            # 濡傛灉杩樻槸娌℃湁鎵惧埌鍚堥€傜殑杩炴帴锛屼娇鐢ㄦ渶杩戠殑閿氱偣
            if len(connect_to) < 2 and outer_nodes:
                nearest_outer = sorted(
                    outer_nodes,
                    key=lambda n: (n['x'] - target_x) ** 2 + (n['y'] - target_y) ** 2
                )
                for n in nearest_outer:
                    if n['id'] not in connect_to:
                        connect_to.append(n['id'])
                    if len(connect_to) >= 2:
                        break

            if not connect_to and anchor_node:
                connect_to.append(anchor_node['id'])

        # 去重并限制连接数，避免一次扩张产生过多边
        connect_to = list(dict.fromkeys(connect_to))[:4]
        
        return {
            'action': 'expand_city',
            'new_node_position': {'x': target_x, 'y': target_y},
            'connect_to': connect_to,
            'path_waypoints': path_waypoints,  # 瀛樺偍璺緞鐐逛俊鎭?
            'expansion_direction': expansion_direction,
            'connect_reason': f'融合 procedural growth: 向{expansion_direction}扩展, 候选类型: {candidate_type}',
            'shape_consideration': f'融合 grid/organic/radial 规则，优先外圈增长并保持道路连通，道路间距约 {grid_size:.0f}m',
            'reason': f'规则规划(融合 procedural): 人口密度达到{self.get_population_density()*100:.0f}%',
            'is_llm': False,
            'candidate_type': candidate_type
        }
    
    def _get_llm_manager(self):
        """鑾峰彇LLM绠＄悊鍣ㄣ€"""
        try:
            from city.llm.llm_manager import get_llm_manager
            return get_llm_manager()
        except:
            return None

    def _iter_unique_edges(self):
        """Iterate each physical road once (dedupe bidirectional edges)."""
        if not self.environment:
            return
        seen: set[tuple[str, str]] = set()
        for edge in self.environment.road_network.edges.values():
            key = tuple(sorted((edge.from_node.node_id, edge.to_node.node_id)))
            if key in seen:
                continue
            seen.add(key)
            yield edge

    def _adjust_position_if_near_road(self, pos: Vector2D, min_clearance: float = 35.0) -> Vector2D:
        """
        If a new node falls on an existing road segment, move it slightly away.
        This avoids creating overlapping roads after expansion.
        """
        if not self.environment:
            return pos

        network = self.environment.road_network
        x0, y0 = pos.x, pos.y

        for edge in self._iter_unique_edges():
            x1, y1 = edge.from_node.position.x, edge.from_node.position.y
            x2, y2 = edge.to_node.position.x, edge.to_node.position.y
            dx, dy = x2 - x1, y2 - y1
            seg_len2 = dx * dx + dy * dy
            if seg_len2 < 1e-6:
                continue

            t = ((x0 - x1) * dx + (y0 - y1) * dy) / seg_len2
            if t <= 0.08 or t >= 0.92:
                continue

            proj_x = x1 + t * dx
            proj_y = y1 + t * dy
            dist = math.sqrt((x0 - proj_x) ** 2 + (y0 - proj_y) ** 2)
            if dist >= min_clearance:
                continue

            seg_len = math.sqrt(seg_len2)
            nx, ny = -dy / seg_len, dx / seg_len
            shift = min_clearance - dist + 8.0

            candidates = [
                Vector2D(x0 + nx * shift, y0 + ny * shift),
                Vector2D(x0 - nx * shift, y0 - ny * shift),
            ]

            def score(candidate: Vector2D) -> float:
                node_clear = min(
                    (
                        candidate.distance_to(node.position)
                        for node in network.nodes.values()
                    ),
                    default=9999.0
                )
                edge_clear = min(
                    (
                        self._point_to_segment_distance(
                            candidate.x,
                            candidate.y,
                            e.from_node.position.x,
                            e.from_node.position.y,
                            e.to_node.position.x,
                            e.to_node.position.y
                        )
                        for e in self._iter_unique_edges()
                    ),
                    default=9999.0
                )
                return min(node_clear, edge_clear)

            candidates.sort(key=score, reverse=True)
            for candidate in candidates:
                if score(candidate) >= 22.0:
                    print(
                        f"[城市扩张] 新节点位置贴近道路，自动偏移到 "
                        f"({candidate.x:.1f}, {candidate.y:.1f})"
                    )
                    return candidate

            return candidates[0]

        return pos

    def _orientation(self, ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> float:
        return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)

    def _on_segment(self, ax: float, ay: float, bx: float, by: float, cx: float, cy: float, tol: float = 1e-6) -> bool:
        return (
            min(ax, bx) - tol <= cx <= max(ax, bx) + tol
            and min(ay, by) - tol <= cy <= max(ay, by) + tol
        )

    def _segments_intersect_strict(
        self,
        a1x: float, a1y: float, a2x: float, a2y: float,
        b1x: float, b1y: float, b2x: float, b2y: float,
        tol: float = 1e-6
    ) -> bool:
        """Check whether two segments intersect at a non-endpoint position."""
        o1 = self._orientation(a1x, a1y, a2x, a2y, b1x, b1y)
        o2 = self._orientation(a1x, a1y, a2x, a2y, b2x, b2y)
        o3 = self._orientation(b1x, b1y, b2x, b2y, a1x, a1y)
        o4 = self._orientation(b1x, b1y, b2x, b2y, a2x, a2y)

        # Proper crossing
        if (o1 * o2 < -tol) and (o3 * o4 < -tol):
            return True

        # Colinear / touching cases (treat as intersect if not just endpoint touching)
        colinear_hit = (
            (abs(o1) <= tol and self._on_segment(a1x, a1y, a2x, a2y, b1x, b1y, tol))
            or (abs(o2) <= tol and self._on_segment(a1x, a1y, a2x, a2y, b2x, b2y, tol))
            or (abs(o3) <= tol and self._on_segment(b1x, b1y, b2x, b2y, a1x, a1y, tol))
            or (abs(o4) <= tol and self._on_segment(b1x, b1y, b2x, b2y, a2x, a2y, tol))
        )
        if not colinear_hit:
            return False

        endpoints_a = {(a1x, a1y), (a2x, a2y)}
        endpoints_b = {(b1x, b1y), (b2x, b2y)}
        shared_endpoints = endpoints_a & endpoints_b
        if shared_endpoints:
            return False
        return True

    def _segments_nearly_parallel_and_overlapping(
        self,
        a1x: float, a1y: float, a2x: float, a2y: float,
        b1x: float, b1y: float, b2x: float, b2y: float,
        min_parallel_gap: float = 20.0,
        min_overlap_span: float = 30.0
    ) -> bool:
        """Check if two segments run almost parallel and overlap in projection."""
        adx, ady = a2x - a1x, a2y - a1y
        bdx, bdy = b2x - b1x, b2y - b1y
        alen = math.sqrt(adx * adx + ady * ady)
        blen = math.sqrt(bdx * bdx + bdy * bdy)
        if alen < 1e-6 or blen < 1e-6:
            return False

        cos_theta = abs((adx * bdx + ady * bdy) / (alen * blen))
        if cos_theta < 0.98:
            return False

        # Use dominant axis to compute overlap span.
        if abs(adx) >= abs(ady):
            overlap = min(max(a1x, a2x), max(b1x, b2x)) - max(min(a1x, a2x), min(b1x, b2x))
        else:
            overlap = min(max(a1y, a2y), max(b1y, b2y)) - max(min(a1y, a2y), min(b1y, b2y))

        if overlap < min_overlap_span:
            return False

        dist_a_mid_to_b = self._point_to_segment_distance((a1x + a2x) / 2, (a1y + a2y) / 2, b1x, b1y, b2x, b2y)
        dist_b_mid_to_a = self._point_to_segment_distance((b1x + b2x) / 2, (b1y + b2y) / 2, a1x, a1y, a2x, a2y)
        return min(dist_a_mid_to_b, dist_b_mid_to_a) < min_parallel_gap

    def _has_direct_connection(self, node1: Node, node2: Node) -> bool:
        """Check whether two nodes already have at least one direct edge."""
        for edge in node1.outgoing_edges:
            if edge.to_node == node2:
                return True
        for edge in node1.incoming_edges:
            if edge.from_node == node2:
                return True
        return False

    def _line_intersection_params(
        self,
        a1x: float, a1y: float, a2x: float, a2y: float,
        b1x: float, b1y: float, b2x: float, b2y: float
    ) -> tuple[float, float] | None:
        """
        Return (t, u) for intersection of lines:
        A(t)=A1+t*(A2-A1), B(u)=B1+u*(B2-B1).
        """
        dax = a2x - a1x
        day = a2y - a1y
        dbx = b2x - b1x
        dby = b2y - b1y
        denom = dax * dby - day * dbx
        if abs(denom) < 1e-8:
            return None
        rx = b1x - a1x
        ry = b1y - a1y
        t = (rx * dby - ry * dbx) / denom
        u = (rx * day - ry * dax) / denom
        return (t, u)

    def _find_existing_node_near(self, x: float, y: float, radius: float = 28.0) -> Node | None:
        """Find an existing node near a given coordinate."""
        if not self.environment:
            return None
        best = None
        best_d = float("inf")
        p = Vector2D(x, y)
        for node in self.environment.road_network.nodes.values():
            d = p.distance_to(node.position)
            if d < radius and d < best_d:
                best = node
                best_d = d
        return best

    def _ensure_intersection_node_connected(self, inter_node: Node, host_edge: Edge) -> None:
        """Connect intersection node to both endpoints of the host edge."""
        if not self.environment:
            return
        for endpoint in (host_edge.from_node, host_edge.to_node):
            if inter_node.node_id == endpoint.node_id:
                continue
            if self._has_direct_connection(inter_node, endpoint):
                continue
            if self.environment.can_connect_nodes(
                inter_node,
                endpoint,
                max_distance=max(self.max_edge_length * 1.25, 650.0)
            ):
                self.environment.add_edge_dynamically(
                    from_node=inter_node,
                    to_node=endpoint,
                    num_lanes=2,
                    bidirectional=True
                )

    def _adjust_target_node_with_vertex_checks(self, from_node: Node, to_node: Node) -> tuple[Node, str | None]:
        """
        Apply procedural-style vertex checks before adding edge:
        1) snap to near existing vertex
        2) extend edge to nearby host-edge intersection
        3) shorten edge to first intersection with host edge
        """
        if not self.environment:
            return to_node, None

        x1, y1 = from_node.position.x, from_node.position.y
        x2, y2 = to_node.position.x, to_node.position.y

        # Case 1: new vertex too close to an existing vertex -> snap to that vertex.
        snap_node = self._find_existing_node_near(x2, y2, radius=38.0)
        if snap_node and snap_node.node_id not in {from_node.node_id, to_node.node_id}:
            return snap_node, "snap_to_near_vertex"

        best_shorten: tuple[float, float, float, Edge] | None = None
        best_extend: tuple[float, float, float, Edge] | None = None

        for edge in self._iter_unique_edges():
            a = edge.from_node
            b = edge.to_node
            if from_node.node_id in {a.node_id, b.node_id}:
                continue
            ex1, ey1 = a.position.x, a.position.y
            ex2, ey2 = b.position.x, b.position.y

            params = self._line_intersection_params(x1, y1, x2, y2, ex1, ey1, ex2, ey2)
            if params is None:
                continue
            t, u = params
            ix = x1 + (x2 - x1) * t
            iy = y1 + (y2 - y1) * t
            dist_from_start = math.hypot(ix - x1, iy - y1)

            # Case 3: candidate intersects an existing edge -> shorten to intersection.
            if 1e-3 < t < 0.999 and -1e-3 <= u <= 1.001:
                if best_shorten is None or dist_from_start < best_shorten[0]:
                    best_shorten = (dist_from_start, ix, iy, edge)
                continue

            # Case 2: candidate stops shortly before host edge -> extend to intersection.
            end_to_edge = self._point_to_segment_distance(x2, y2, ex1, ey1, ex2, ey2)
            if 1.0 < t <= 1.35 and -1e-3 <= u <= 1.001 and end_to_edge <= 36.0:
                if best_extend is None or dist_from_start < best_extend[0]:
                    best_extend = (dist_from_start, ix, iy, edge)

        chosen = best_shorten if best_shorten is not None else best_extend
        if chosen is None:
            return to_node, None

        _, ix, iy, host_edge = chosen
        near_node = self._find_existing_node_near(ix, iy, radius=22.0)
        if near_node:
            return near_node, "snap_to_intersection_near_vertex"

        inter_node = self.environment.add_node_dynamically(
            position=Vector2D(ix, iy),
            name=f"inter_{len(self.expansion_history)+1}"
        )
        self._ensure_intersection_node_connected(inter_node, host_edge)
        if best_shorten is not None:
            return inter_node, "shorten_to_intersection"
        return inter_node, "extend_to_intersection"

    def _would_overlap_existing_roads(self, from_node: Node, to_node: Node) -> bool:
        """Validate whether a new road segment would overlap/cross existing roads."""
        if not self.environment:
            return True

        x1, y1 = from_node.position.x, from_node.position.y
        x2, y2 = to_node.position.x, to_node.position.y
        candidate_key = tuple(sorted((from_node.node_id, to_node.node_id)))

        for edge in self._iter_unique_edges():
            a = edge.from_node
            b = edge.to_node
            existing_key = tuple(sorted((a.node_id, b.node_id)))

            # Same undirected road already exists.
            if existing_key == candidate_key:
                return True

            # Shared endpoint is allowed as a proper intersection.
            if len({from_node.node_id, to_node.node_id} & {a.node_id, b.node_id}) > 0:
                continue

            ex1, ey1 = a.position.x, a.position.y
            ex2, ey2 = b.position.x, b.position.y

            if self._segments_intersect_strict(x1, y1, x2, y2, ex1, ey1, ex2, ey2):
                # Allow touching host edge exactly at candidate endpoint when
                # endpoint is already connected to host edge endpoints.
                endpoint_touch = self._point_to_segment_distance(x2, y2, ex1, ey1, ex2, ey2) <= 1.0
                if endpoint_touch and self._has_direct_connection(to_node, a) and self._has_direct_connection(to_node, b):
                    continue
                return True

            if self._segments_nearly_parallel_and_overlapping(x1, y1, x2, y2, ex1, ey1, ex2, ey2):
                return True

        return False

    def _safe_add_edge(self, from_node: Node, to_node: Node, num_lanes: int = 2, bidirectional: bool = True):
        """Add edge with geometric overlap guards."""
        if not self.environment:
            return None

        adjusted_to_node, adjust_reason = self._adjust_target_node_with_vertex_checks(from_node, to_node)
        if adjusted_to_node.node_id != to_node.node_id:
            to_node = adjusted_to_node
            if adjust_reason:
                print(f"[城市扩张] 顶点检查命中: {adjust_reason}, 终点调整为 {to_node.node_id}")

        if not self.environment.can_connect_nodes(
            from_node, to_node, max_distance=max(self.max_edge_length * 1.25, 650.0)
        ):
            return None
        if self._would_overlap_existing_roads(from_node, to_node):
            print(f"[城市扩张] 跳过重叠道路: {from_node.node_id} -> {to_node.node_id}")
            return None
        return self.environment.add_edge_dynamically(
            from_node=from_node,
            to_node=to_node,
            num_lanes=num_lanes,
            bidirectional=bidirectional
        )
    
    def _expand_with_growth(self, expansion_size: str = "medium") -> bool:
        """
        使用真正仿 procedural_city_generation 的方式扩展城市路网。
        
        核心机制：
        1. Vertex + neighbours 图结构
        2. Front (生长前沿) 迭代生长
        3. Check 函数处理相交、吸附、创建交叉口
        4. Seed + vertex_queue 支路生成机制
        5. KDTree 空间查询加速
        
        Args:
            expansion_size: 扩展规模 (small/medium/large)
            
        Returns:
            是否成功扩展
        """
        if not self.environment:
            return False
        
        try:
            from city.environment.procedural_roadmap import (
                expand_with_procedural_roadmap,
                ProceduralRoadmapGenerator,
                ProceduralConfig
            )
            
            print(f"\n{'='*60}")
            print(f"[城市扩张] 启动真正 Procedural 扩展 (规模: {expansion_size})")
            print(f"{'='*60}")
            
            # 根据规模选择配置
            configs = {
                "small": {"iterations": 2, "description": "小幅扩展"},
                "medium": {"iterations": 3, "description": "中等扩展"},
                "large": {"iterations": 5, "description": "大幅扩展"}
            }
            config = configs.get(expansion_size, configs["medium"])
            
            # 记录扩展前状态
            nodes_before = len(self.environment.road_network.nodes)
            edges_before = len(self.environment.road_network.edges)
            
            # 执行生长扩展
            num_new = expand_with_procedural_roadmap(
                self.environment,
                num_iterations=config["iterations"]
            )
            
            # 记录扩展结果
            nodes_after = len(self.environment.road_network.nodes)
            edges_after = len(self.environment.road_network.edges)
            
            if num_new > 0:
                self.last_expansion_time = self.environment.current_time
                
                # 记录扩展历史
                expansion_record = {
                    'time': self.environment.current_time,
                    'method': 'procedural_roadmap_v2',
                    'size': expansion_size,
                    'description': config["description"],
                    'nodes_added': num_new,
                    'nodes_before': nodes_before,
                    'nodes_after': nodes_after,
                    'edges_before': edges_before,
                    'edges_after': edges_after
                }
                self.expansion_history.append(expansion_record)
                
                print(f"[城市扩张] 完成! 新增 {num_new} 个节点, "
                      f"{edges_after - edges_before} 条边")
                print(f"  当前路网: {nodes_after} 节点, {edges_after} 边")
                
                # 为新节点添加红绿灯
                new_nodes = list(self.environment.road_network.nodes.values())[-num_new:]
                self._add_traffic_lights_to_new_nodes(new_nodes)
                
                return True
            else:
                print("[城市扩张] 没有生成新节点")
                return False
                
        except Exception as e:
            print(f"[城市扩张] 生长扩展失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _add_traffic_lights_to_new_nodes(self, nodes: list) -> None:
        """为新节点中的交叉口添加红绿灯。"""
        if not self.environment:
            return
        
        from city.environment.road_network import TrafficLight
        from city.agents.traffic_light_agent import TrafficLightAgent
        
        count = 0
        for node in nodes:
            # 如果是交叉口（连接数 >= 3）
            total_connections = len(node.incoming_edges) + len(node.outgoing_edges)
            if total_connections >= 3 and not node.traffic_light:
                node.is_intersection = True
                node.traffic_light = TrafficLight(
                    node, cycle_time=60, green_duration=25, yellow_duration=5
                )
                
                tl_agent = TrafficLightAgent(
                    control_node=node,
                    environment=self.environment,
                    use_llm=self.use_llm,
                    name=f"红绿灯_{node.node_id}",
                    enable_memory=self.use_llm
                )
                tl_agent.activate()
                self.environment.add_agent(tl_agent)
                count += 1
        
        if count > 0:
            print(f"[城市扩张] 为 {count} 个交叉口添加了红绿灯")
    
    def act(self, decision: dict[str, Any] | None) -> bool:
        """
        执行城市扩展。
        
        优先使用生长式扩展（多分支、自然生长），
        回退到传统单节点扩展。
        """
        if not decision or not self.environment:
            return False
        
        action = decision.get('action')
        if action != 'expand_city':
            return False
        
        self.record_action(
            'expand_city',
            {
                'source': 'llm' if decision.get('is_llm') else 'rule',
                'direction': decision.get('expansion_direction', 'unknown'),
            },
            importance=5.0
        )
        
        # 优先使用生长式扩展
        try:
            # 根据城市规模选择扩展大小
            current_nodes = len(self.environment.road_network.nodes)
            if current_nodes < 8:
                expansion_size = "small"
            elif current_nodes < 15:
                expansion_size = "medium"
            else:
                expansion_size = "large"
            
            # 尝试生长式扩展
            success = self._expand_with_growth(expansion_size)
            if success:
                self.record_event(
                    '路网扩展成功',
                    {
                        'mode': 'growth',
                        'expansion_size': expansion_size,
                        'nodes': len(self.environment.road_network.nodes),
                        'edges': len(self.environment.road_network.edges),
                    },
                    importance=7.0
                )
                return True
            
            print("[城市扩张] 生长式扩展未生成节点，回退到传统扩展")
            
        except Exception as e:
            print(f"[城市扩张] 生长式扩展异常: {e}，回退到传统扩展")
        
        # 回退到传统单节点扩展
        success = self._act_traditional(decision)
        if success:
            self.record_event(
                '路网扩展成功',
                {
                    'mode': 'traditional',
                    'direction': decision.get('expansion_direction', 'unknown'),
                    'nodes': len(self.environment.road_network.nodes),
                    'edges': len(self.environment.road_network.edges),
                },
                importance=7.0
            )
        return success
    
    def _act_traditional(self, decision: dict[str, Any] | None) -> bool:
        """传统的单节点扩展方式（作为回退）。"""
        if not decision or not self.environment:
            return False
        
        try:
            # 鍒涘缓鏂拌妭鐐?
            pos_data = decision['new_node_position']
            planned_pos = Vector2D(pos_data['x'], pos_data['y'])
            new_pos = self._adjust_position_if_near_road(planned_pos)
            
            new_node = self.environment.add_node_dynamically(
                position=new_pos,
                name=f"district_{len(self.expansion_history)+1}"
            )
            
            # 杩炴帴鍒板喅绛栨寚瀹氱殑鑺傜偣
            network = self.environment.road_network
            connect_to = decision.get('connect_to', [])
            path_waypoints = decision.get('path_waypoints', {})
            
            print(f"[城市扩张] 新节点 {new_node.node_id} 计划连接: {connect_to}")
            if path_waypoints:
                print(f"[城市扩张] 使用折线路径，路径点: {path_waypoints}")
            
            connections = 0
            connected_nodes = []
            
            # 鑾峰彇鎵€鏈夊姛鑳藉尯鍩熺敤浜庤矾寰勮鍒?
            zones = self._get_zones_for_expansion_planning()
            
            for nid in connect_to:
                if nid == new_node.node_id:
                    continue
                target_node = network.nodes.get(nid)
                if not target_node:
                    continue
                    
                dist = new_node.position.distance_to(target_node.position)
                print(f"[城市扩张] 尝试连接 {nid}, 距离 {dist:.1f}m")
                
                # 妫€鏌ョ洿鎺ヨ繛鎺ユ槸鍚︿細绌胯繃鍔熻兘鍖哄煙
                needs_waypoints = False
                waypoints = []
                
                for zone in zones:
                    if self._line_intersects_zone(
                        new_node.position.x, new_node.position.y,
                        target_node.position.x, target_node.position.y,
                        zone
                    ):
                        print(f"[城市扩张] 直接连接会穿过区域 {zone.name}，需要绕行")
                        needs_waypoints = True
                        # 璁＄畻缁曡璺緞
                        path = self._find_path_around_zones(new_node, target_node, [zone])
                        if path:
                            waypoints.extend(path)
                        break
                
                # 濡傛灉鏈夐璁＄畻鐨勮矾寰勭偣鎴栬€呭垰璁＄畻鐨勭粫琛岃矾寰勶紝浣跨敤鎶樼嚎
                if (nid in path_waypoints and path_waypoints[nid]) or waypoints:
                    if not waypoints and nid in path_waypoints:
                        waypoints = path_waypoints[nid]
                    
                    print(f"[城市扩张] 使用折线路径连接 {nid}，经过 {len(waypoints)} 个中间点")
                    
                    # 鍒涘缓鎶樼嚎璺緞锛氭柊鑺傜偣 -> 涓棿鐐?-> 鐩爣鑺傜偣
                    current_node = new_node
                    path_success = True
                    
                    for i, wp in enumerate(waypoints):
                        # 鍒涘缓涓棿鑺傜偣锛堝鏋滄槸鎶樼嚎璺緞锛?
                        wp_pos = Vector2D(wp['x'], wp['y'])
                        
                        # 妫€鏌ユ槸鍚﹀凡鏈夎妭鐐瑰湪杩欎釜浣嶇疆
                        existing = None
                        for node in network.nodes.values():
                            if node.position.distance_to(wp_pos) < 30:
                                existing = node
                                break
                        
                        if existing:
                            # 浣跨敤鐜版湁鑺傜偣
                            intermediate_node = existing
                            print(f"[城市扩张] 使用现有节点作为中间点: {intermediate_node.node_id}")
                        else:
                            # 鍒涘缓鏂扮殑涓棿鑺傜偣锛堢敤浜庢姌绾胯浆寮級
                            intermediate_node = self.environment.add_node_dynamically(
                                position=wp_pos,
                                name=f"corner_{new_node.node_id}_{i}"
                            )
                            print(f"[城市扩张] 创建中间节点: {intermediate_node.node_id}")
                        
                        # 杩炴帴褰撳墠鑺傜偣鍒颁腑闂磋妭鐐?
                        edge1 = self._safe_add_edge(
                            from_node=current_node,
                            to_node=intermediate_node,
                            num_lanes=2,
                            bidirectional=True
                        )
                        
                        if edge1:
                            print(f"[城市扩张] 折线连接: {current_node.node_id} -> {intermediate_node.node_id}")
                        else:
                            path_success = False
                            break
                        
                        current_node = intermediate_node
                    
                    # 鏈€鍚庤繛鎺ュ埌鐩爣鑺傜偣
                    if path_success:
                        final_edge = self._safe_add_edge(
                            from_node=current_node,
                            to_node=target_node,
                            num_lanes=2,
                            bidirectional=True
                        )
                        if final_edge:
                            connections += 1
                            connected_nodes.append(nid)
                            print(f"[城市扩张] 折线连接成功: {new_node.node_id} ... -> {nid}")
                else:
                    # 鐩存帴杩炴帴锛堜笉浼氱┛杩囧尯鍩燂級
                    edge = self._safe_add_edge(
                        from_node=new_node,
                        to_node=target_node,
                        num_lanes=2,
                        bidirectional=True
                    )
                    if edge:
                        connections += 1
                        connected_nodes.append(nid)
                        print(f"[城市扩张] 成功连接 {nid}")
            
            # 纭繚鑷冲皯2涓繛鎺ワ紙濡傛灉娌℃湁瓒冲杩炴帴锛屽皾璇曠洿鎺ヨ繛鎺ユ渶杩戠殑鑺傜偣锛?
            # 闄愬埗锛氬彧杩炴帴鍒扮洿鎺ョ浉閭荤殑鑺傜偣锛堢綉鏍奸棿璺濊寖鍥村唴锛夛紝閬垮厤闀胯窛绂诲瑙掕繛鎺?
            has_detour_path = any(
                nid in path_waypoints and path_waypoints[nid] 
                for nid in connected_nodes
            )
            
            # 璁＄畻鍚堢悊鐨勬渶澶ц繛鎺ヨ窛绂伙紙鍩轰簬缃戞牸闂磋窛锛屽厑璁稿皯閲忎綑閲忥級
            max_connection_dist = max(self.max_edge_length * 0.95, 360.0)
            
            if connections < 2 and not has_detour_path:
                distances = [
                    (nid, new_node.position.distance_to(n.position))
                    for nid, n in network.nodes.items()
                    if nid != new_node.node_id 
                    and nid not in connected_nodes
                    and new_node.position.distance_to(n.position) <= max_connection_dist  # 鍙€冭檻杩戣窛绂昏妭鐐?
                ]
                distances.sort(key=lambda x: x[1])
                
                for nid, dist in distances:
                    if connections >= 2:
                        break
                    target_node = network.nodes.get(nid)
                    if target_node:
                        # 鍙€冭檻姝ｄ氦鏂瑰悜鐨勮妭鐐癸紙X鎴朰鍧愭爣鐩稿悓鎴栨帴杩戯級
                        dx = abs(new_node.position.x - target_node.position.x)
                        dy = abs(new_node.position.y - target_node.position.y)
                        
                        # 蹇呴』鏄浜ら偦灞咃紙涓昏鏄按骞虫垨鍨傜洿鏂瑰悜锛?
                        is_orthogonal = min(dx, dy) < 50
                        is_near_diagonal = abs(dx - dy) < 80 and max(dx, dy) <= self.max_edge_length
                        
                        if not allow_non_orthogonal and not is_orthogonal and not is_near_diagonal:
                            continue  # 璺宠繃瀵硅绾胯妭鐐?
                        
                        # 妫€鏌ョ洿鎺ヨ繛鎺ユ槸鍚︿細绌胯繃鍖哄煙
                        would_intersect = False
                        for zone in zones:
                            if self._line_intersects_zone(
                                new_node.position.x, new_node.position.y,
                                target_node.position.x, target_node.position.y,
                                zone
                            ):
                                would_intersect = True
                                break
                        
                        if would_intersect:
                            continue  # 璺宠繃浼氱┛杩囧尯鍩熺殑杩炴帴
                        
                        edge = self._safe_add_edge(
                            from_node=new_node,
                            to_node=target_node,
                            num_lanes=2,
                            bidirectional=True
                        )
                        if edge:
                            connections += 1
                            connected_nodes.append(nid)
                            print(f"[城市扩张] 补充连接 {nid} (距离 {dist:.0f}m)")
            
            if connections > 0:
                self.last_expansion_time = self.environment.current_time
                
                # 璁板綍鎵╁睍鍘嗗彶
                expansion_record = {
                    'time': self.environment.current_time,
                    'new_node': new_node.node_id,
                    'position': pos_data,
                    'connections': connections,
                    'connected_to': connected_nodes,
                    'population_before': len(self.environment.vehicles),
                    'decision': decision
                }
                self.expansion_history.append(expansion_record)
                
                # ????????????????
                direction = decision.get('expansion_direction')
                if direction:
                    self.recent_expansion_directions.append(direction)
                    if len(self.recent_expansion_directions) > self.direction_window:
                        self.recent_expansion_directions.pop(0)
                
                print(f"[城市扩张] 新增区域 {new_node.node_id}，连接 {connections} 条道路")
                return True
            
            return False
            
        except Exception as e:
            print(f"[城市扩张] 执行失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _get_time_of_day(self) -> str:
        """
        鑾峰彇褰撳墠鏃舵銆?
        
        妯℃嫙涓€澶?4灏忔椂鐨勬椂娈碉細
        - morning_rush: 鏃╅珮宄?(7-9鐐?
        - daytime: 鐧藉ぉ (9-17鐐?
        - evening_rush: 鏅氶珮宄?(17-19鐐?
        - night: 澶滈棿 (19-7鐐?
        """
        if not self.environment:
            return 'daytime'
        
        # 灏嗕豢鐪熸椂闂存槧灏勫埌24灏忔椂鍒?(姣忎釜浠跨湡鏃ュ亣璁句负360绉掞紝鍗?鍒嗛挓)
        day_seconds = 360
        time_of_day = self.environment.current_time % day_seconds
        hour = (time_of_day / day_seconds) * 24
        
        if 7 <= hour < 9:
            return 'morning_rush'
        elif 9 <= hour < 17:
            return 'daytime'
        elif 17 <= hour < 19:
            return 'evening_rush'
        else:
            return 'night'
    
    def _get_zone_travel_multiplier(self, zone_type_name: str, time_period: str, is_origin: bool) -> float:
        """
        鑾峰彇鍖哄煙鍦ㄧ壒瀹氭椂娈电殑鍑鸿鍊嶆暟銆?
        
        Args:
            zone_type_name: 鍖哄煙绫诲瀷鍚嶇О
            time_period: 鏃舵
            is_origin: 鏄惁鏄捣鐐癸紙True=鍑哄彂锛孎alse=鍒拌揪锛?
        
        Returns:
            鍑鸿鍊嶆暟锛?.0涓哄熀鍑嗭級
        """
        multipliers = {
            'RESIDENTIAL': {
                'morning_rush': {'origin': 2.5, 'destination': 0.3},  # 鏃╅珮宄板ぇ閲忓嚭闂?
                'daytime': {'origin': 0.8, 'destination': 0.6},
                'evening_rush': {'origin': 0.3, 'destination': 2.5},  # 鏅氶珮宄板ぇ閲忓洖瀹?
                'night': {'origin': 0.2, 'destination': 1.0}
            },
            'COMMERCIAL': {
                'morning_rush': {'origin': 0.3, 'destination': 2.0},  # 鏃╅珮宄板幓鍟嗕笟鍖?
                'daytime': {'origin': 1.0, 'destination': 1.5},       # 鐧藉ぉ鍟嗕笟鍖烘椿璺?
                'evening_rush': {'origin': 1.5, 'destination': 0.5},
                'night': {'origin': 0.5, 'destination': 0.3}
            },
            'OFFICE': {
                'morning_rush': {'origin': 0.2, 'destination': 2.5},  # 鏃╅珮宄板幓鍔炲叕鍖?
                'daytime': {'origin': 0.8, 'destination': 0.8},
                'evening_rush': {'origin': 2.5, 'destination': 0.2},  # 鏅氶珮宄扮寮€鍔炲叕鍖?
                'night': {'origin': 0.1, 'destination': 0.1}
            },
            'INDUSTRIAL': {
                'morning_rush': {'origin': 0.3, 'destination': 2.0},
                'daytime': {'origin': 1.2, 'destination': 1.0},
                'evening_rush': {'origin': 2.0, 'destination': 0.3},
                'night': {'origin': 0.5, 'destination': 0.5}
            },
            'SCHOOL': {
                'morning_rush': {'origin': 0.3, 'destination': 2.0},  # 鏃╀笂涓婂
                'daytime': {'origin': 0.5, 'destination': 0.3},
                'evening_rush': {'origin': 2.0, 'destination': 0.3},  # 涓嬪崍鏀惧
                'night': {'origin': 0.1, 'destination': 0.1}
            },
            'HOSPITAL': {
                'morning_rush': {'origin': 0.8, 'destination': 1.0},
                'daytime': {'origin': 1.0, 'destination': 1.2},
                'evening_rush': {'origin': 1.0, 'destination': 0.8},
                'night': {'origin': 0.5, 'destination': 0.5}
            },
            'PARK': {
                'morning_rush': {'origin': 0.5, 'destination': 0.8},
                'daytime': {'origin': 1.0, 'destination': 1.5},       # 鐧藉ぉ鍘诲叕鍥?
                'evening_rush': {'origin': 1.0, 'destination': 0.5},
                'night': {'origin': 0.1, 'destination': 0.1}
            }
        }
        
        zone_multipliers = multipliers.get(zone_type_name, multipliers['RESIDENTIAL'])
        period_multipliers = zone_multipliers.get(time_period, zone_multipliers['daytime'])
        return period_multipliers['origin'] if is_origin else period_multipliers['destination']
    
    def _get_node_zones_info(self, node) -> list[dict]:
        """鑾峰彇鑺傜偣闄勮繎鐨勫尯鍩熶俊鎭€"""
        nearby_zones = []
        if not self.environment:
            return nearby_zones
        
        # 鑾峰彇鍩庡競瑙勫垝鏅鸿兘浣撶殑鍖哄煙绠＄悊鍣?
        zoning_agent = None
        for agent in self.environment.agents:
            if hasattr(agent, 'zone_manager') and agent.agent_type == AgentType.TRAFFIC_PLANNER:
                zoning_agent = agent
                break
        
        if not zoning_agent:
            # 濡傛灉娌℃湁鎵惧埌鍩庡競瑙勫垝鏅鸿兘浣擄紝杩斿洖绌哄垪琛?
            return nearby_zones
        
        zone_manager = zoning_agent.zone_manager
        for zone in zone_manager.zones.values():
            # 璁＄畻鑺傜偣鍒板尯鍩熺殑璺濈
            dist = node.position.distance_to(zone.center)
            if dist < 250:  # 250绫冲唴璁や负鏄檮杩?
                nearby_zones.append({
                    'type': zone.zone_type.name,
                    'population': zone.population,
                    'distance': dist
                })
        
        return nearby_zones
    
    def _get_zoning_agent(self):
        """鑾峰彇鍩庡競瑙勫垝鏅鸿兘浣撱€"""
        if not self.environment:
            return None
        for agent in self.environment.agents.values():
            if hasattr(agent, 'zone_manager') and agent.agent_type == AgentType.TRAFFIC_PLANNER:
                return agent
        return None
    
    def _auto_spawn_vehicles(self) -> int:
        """
        鍩轰簬鍖哄煙浜哄彛鍜屾椂娈电壒寰佺敓鎴愯溅杈嗭紙OD瀵癸級銆?
        
        杞﹁締鐢熸垚閫昏緫锛?
        1. 鑰冭檻鏃舵鐗瑰緛锛堟棭楂樺嘲銆佹櫄楂樺嘲绛夛級
        2. 鍩轰簬鍖哄煙浜哄彛鍜岀被鍨嬭绠楃敓鎴愭鐜?
        3. 浣忓畢鍖烘棭涓婄敓鎴愬嚭闂ㄨ溅杈嗭紝鏅氫笂鐢熸垚鍥炲杞﹁締
        4. 鍟嗕笟鍖?鍔炲叕鍖烘湁瀵瑰簲鐨勫嚭琛屾ā寮?
        """
        if not self.environment:
            return 0
        
        network = self.environment.road_network
        nodes = list(network.nodes.values())
        
        if len(nodes) < 2:
            return 0
        
        spawned = 0
        stats = self.get_city_stats()
        time_period = self._get_time_of_day()
        
        # 璁＄畻鍩轰簬鏃舵鐨勫熀纭€鐢熸垚鐜?
        base_spawn_rate = {
            'morning_rush': 0.8,    # 鏃╅珮宄扮敓鎴愮巼楂?
            'daytime': 0.4,
            'evening_rush': 0.8,    # 鏅氶珮宄扮敓鎴愮巼楂?
            'night': 0.15
        }.get(time_period, 0.4)
        
        # 鏍规嵁褰撳墠浜哄彛鍜屽閲忓喅瀹氱敓鎴愭暟閲?
        if stats['current_population'] < stats['max_capacity']:
            # 璁＄畻鍙敓鎴愮殑杞﹁締鏁?
            available_slots = stats['max_capacity'] - stats['current_population']
            
            # 鍩轰簬鍖哄煙璁＄畻姣忎釜鑺傜偣鐨勭敓鎴愭潈閲?
            node_weights = []
            for node in nodes:
                weight = 0
                nearby_zones = self._get_node_zones_info(node)
                
                for zone_info in nearby_zones:
                    # 鏉冮噸 = 浜哄彛 * 鏃舵鍊嶆暟 * 璺濈琛板噺
                    zone_type = zone_info['type']
                    population = zone_info['population']
                    distance = zone_info['distance']
                    
                    # 鏃舵鍊嶆暟锛堜綔涓鸿捣鐐癸級
                    time_multiplier = self._get_zone_travel_multiplier(
                        zone_type, time_period, is_origin=True
                    )
                    
                    # 璺濈琛板噺锛堣秺杩戝奖鍝嶈秺澶э級
                    distance_decay = max(0, 1 - distance / 200)
                    
                    weight += population * time_multiplier * distance_decay
                
                # 濡傛灉娌℃湁闄勮繎鍖哄煙锛岀粰浜堝熀纭€鏉冮噸
                if weight == 0:
                    weight = 10
                
                node_weights.append((node, weight))
            
            # 鎸夋潈閲嶉€夋嫨璧风偣
            total_weight = sum(w for _, w in node_weights)
            if total_weight == 0:
                return spawned
            
            # 鐢熸垚杞﹁締鏁板熀浜庢椂娈靛拰鍙敤瀹归噺
            num_to_spawn = min(
                int(available_slots * base_spawn_rate) + 1,
                available_slots,
                5  # 姣忔鏈€澶氱敓鎴?杈?
            )
            
            for _ in range(num_to_spawn):
                # 鎸夋潈閲嶉€夋嫨璧风偣
                r = random.uniform(0, total_weight)
                cumsum = 0
                origin = nodes[0]
                for node, weight in node_weights:
                    cumsum += weight
                    if cumsum >= r:
                        origin = node
                        break
                
                # 閫夋嫨缁堢偣 - 鍩轰簬缁堢偣鐨勫惛寮曟潈閲?
                dest_candidates = []
                for node in nodes:
                    if node.node_id == origin.node_id:
                        continue
                    
                    # 璁＄畻缁堢偣鍚稿紩鍔?
                    attraction = 0
                    nearby_zones = self._get_node_zones_info(node)
                    
                    for zone_info in nearby_zones:
                        zone_type = zone_info['type']
                        population = zone_info['population']
                        distance = zone_info['distance']
                        
                        # 鏃舵鍊嶆暟锛堜綔涓虹粓鐐癸級
                        time_multiplier = self._get_zone_travel_multiplier(
                            zone_type, time_period, is_origin=False
                        )
                        
                        distance_decay = max(0, 1 - distance / 200)
                        attraction += population * time_multiplier * distance_decay
                    
                    if attraction > 0:
                        dest_candidates.append((node, attraction))
                
                if dest_candidates:
                    # 鎸夊惛寮曞姏閫夋嫨缁堢偣
                    total_attraction = sum(a for _, a in dest_candidates)
                    r = random.uniform(0, total_attraction)
                    cumsum = 0
                    destination = dest_candidates[0][0]
                    for node, attraction in dest_candidates:
                        cumsum += attraction
                        if cumsum >= r:
                            destination = node
                            break
                else:
                    # 闅忔満閫夋嫨
                    destination = random.choice([n for n in nodes if n.node_id != origin.node_id])
                
                # 鐢熸垚杞﹁締
                vehicle = self.environment.spawn_vehicle(
                    start_node=origin,
                    end_node=destination,
                    vehicle_type=VehicleType.CAR
                )
                
                if vehicle:
                    vehicle_config = getattr(self.environment, 'agent_configs', {})
                    vehicle.use_llm = vehicle_config.get('vehicle', True)
                    spawned += 1
                    self.total_spawns += 1
        
        if spawned > 0:
            print(f"[车辆生成] 时段: {time_period}, 生成 {spawned} 辆车, 当前人口: {stats['current_population'] + spawned}/{stats['max_capacity']}")
        
        return spawned
    
    def _optimize_road_network(self) -> bool:
        """
        优先对已有主干路做车道升级。

        当前策略：
        1. 对每条物理道路汇总双向车辆数
        2. 优先升级车辆数较多、且仍是 2 车道的道路
        3. 一次只把一条物理道路提升到 4 车道
        """
        if not self.environment:
            return False

        candidates: list[tuple[float, Edge, int]] = []
        seen_pairs: set[tuple[str, str]] = set()
        for edge in self.environment.road_network.edges.values():
            pair_key = tuple(sorted((edge.from_node.node_id, edge.to_node.node_id)))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            reverse_edge = self.environment.road_network.find_edge(edge.to_node, edge.from_node)
            current_lanes = max(len(edge.lanes), len(reverse_edge.lanes) if reverse_edge else 0)
            if current_lanes >= 4:
                continue

            vehicle_count = sum(len(lane.vehicles) for lane in edge.lanes)
            if reverse_edge:
                vehicle_count += sum(len(lane.vehicles) for lane in reverse_edge.lanes)

            if vehicle_count <= 0:
                continue

            score = vehicle_count * 1000 + edge.length
            candidates.append((score, edge, current_lanes))

        if not candidates:
            return False

        candidates.sort(key=lambda item: item[0], reverse=True)
        _, target_edge, current_lanes = candidates[0]
        if current_lanes >= 4:
            return False

        upgraded = self.environment.upgrade_edge_lanes_dynamically(
            from_node=target_edge.from_node,
            to_node=target_edge.to_node,
            new_num_lanes=4,
            bidirectional=True
        )
        if upgraded:
            print(
                f"[路网优化] 主干路拓宽 {target_edge.from_node.node_id} <-> "
                f"{target_edge.to_node.node_id}: {current_lanes} -> 4 车道"
            )
        return upgraded
    
    def _can_remove_without_disconnecting(self, from_node, to_node, edge_id_to_skip) -> bool:
        """妫€鏌ュ垹闄よ竟鍚庢槸鍚︿細鏂紑缃戠粶銆"""
        if not self.environment:
            return False
        
        network = self.environment.road_network
        
        # 浣跨敤BFS妫€鏌ヤ粠from_node鏄惁杩樿兘鍒拌揪to_node
        visited = set()
        queue = [from_node.node_id]
        visited.add(from_node.node_id)
        
        while queue:
            current_id = queue.pop(0)
            if current_id == to_node.node_id:
                return True  # 杩樻湁鍏朵粬璺緞
            
            current = network.nodes.get(current_id)
            if not current:
                continue
            
            # 妫€鏌ユ墍鏈夐偦鎺ヨ竟锛堣烦杩囪鍒犻櫎鐨勮竟锛?
            for edge in list(current.outgoing_edges) + list(current.incoming_edges):
                if edge.edge_id == edge_id_to_skip:
                    continue
                neighbor = edge.to_node if edge.from_node == current else edge.from_node
                if neighbor.node_id not in visited:
                    visited.add(neighbor.node_id)
                    queue.append(neighbor.node_id)
        
        return False  # 娌℃湁鍏朵粬璺緞锛屼笉鑳藉垹闄?
    
    def _are_edges_parallel_and_close(self, edge1, edge2, angle_threshold=15, dist_threshold=80) -> bool:
        """妫€鏌ヤ袱鏉¤竟鏄惁杩戜技骞宠涓旇窛绂诲緢杩戙€"""
        # 璁＄畻杈?鐨勬柟鍚戝悜閲?
        dx1 = edge1.to_node.position.x - edge1.from_node.position.x
        dy1 = edge1.to_node.position.y - edge1.from_node.position.y
        len1 = math.sqrt(dx1**2 + dy1**2)
        if len1 < 1:
            return False
        
        # 璁＄畻杈?鐨勬柟鍚戝悜閲?
        dx2 = edge2.to_node.position.x - edge2.from_node.position.x
        dy2 = edge2.to_node.position.y - edge2.from_node.position.y
        len2 = math.sqrt(dx2**2 + dy2**2)
        if len2 < 1:
            return False
        
        # 妫€鏌ユ槸鍚﹀钩琛岋紙鐐圭Н鎺ヨ繎1鎴?1锛?
        cos_angle = abs((dx1*dx2 + dy1*dy2) / (len1 * len2))
        if cos_angle < 0.95:  # 瑙掑害澶т簬绾?8搴?
            return False
        
        # 妫€鏌ヨ窛绂伙紙鍙栬竟1鐨勪腑鐐瑰埌杈?鐨勮窛绂伙級
        mid1_x = (edge1.from_node.position.x + edge1.to_node.position.x) / 2
        mid1_y = (edge1.from_node.position.y + edge1.to_node.position.y) / 2
        
        # 璁＄畻涓偣鍒拌竟2鐨勮窛绂?
        dist = self._point_to_segment_distance(
            mid1_x, mid1_y,
            edge2.from_node.position.x, edge2.from_node.position.y,
            edge2.to_node.position.x, edge2.to_node.position.y
        )
        
        return dist < dist_threshold
    
    def _point_to_segment_distance(self, px, py, x1, y1, x2, y2) -> float:
        """璁＄畻鐐瑰埌绾挎鐨勮窛绂汇€"""
        dx = x2 - x1
        dy = y2 - y1
        
        if dx == 0 and dy == 0:
            return math.sqrt((px - x1)**2 + (py - y1)**2)
        
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        
        return math.sqrt((px - proj_x)**2 + (py - proj_y)**2)
    
    def update(self, dt: float) -> None:
        """鏇存柊瑙勫垝鏅鸿兘浣撶姸鎬併€"""
        if not self.environment:
            return
            
        current_time = self.environment.current_time
        
        # 瀹氭湡鑷姩鐢熸垚杞﹁締
        self.auto_spawn_timer += dt
        if self.auto_spawn_timer >= self.spawn_interval:
            self.auto_spawn_timer = 0.0
            spawned = self._auto_spawn_vehicles()
            if spawned > 0:
                stats = self.get_city_stats()
                print(f"[人口增长] 新增 {spawned} 名通勤者，"
                      f"褰撳墠浜哄彛: {stats['current_population']}/{stats['max_capacity']}")
        
        # 瀹氭湡鍐崇瓥鏄惁闇€瑕佹墿寮?
        check_interval = 5
        if int(current_time) % check_interval == 0 and int(current_time) > 0:
            if not hasattr(self, '_last_expansion_check') or self._last_expansion_check != int(current_time):
                self._last_expansion_check = int(current_time)
                stats = self.get_city_stats()
                
                if stats['density'] >= self.expansion_threshold:
                    decision = self.decide()
                    if decision:
                        success = self.act(decision)
                        if success:
                            print(f"[路网规划] 城市路网已扩展，当前节点数: "
                                  f"{len(self.environment.road_network.nodes)}")
        
        # 瀹氭湡浼樺寲閬撹矾缃戠粶锛堝垹闄や綆鏁堥亾璺級
        optimize_interval = 15  # 姣?5绉掓鏌ヤ竴娆?
        if int(current_time) % optimize_interval == 0 and int(current_time) > 5:
            if not hasattr(self, '_last_optimize_check') or self._last_optimize_check != int(current_time):
                self._last_optimize_check = int(current_time)
                optimized = self._optimize_road_network()
                if optimized:
                    print(f"[路网优化] 已优化道路网络，当前边数: "
                          f"{len(self.environment.road_network.edges)}")
    
    def get_status(self) -> dict[str, Any]:
        """鑾峰彇瑙勫垝鏅鸿兘浣撶姸鎬併€"""
        time_period = self._get_time_of_day()
        
        # 鑾峰彇鍖哄煙缁熻
        zone_stats = {}
        zoning_agent = self._get_zoning_agent()
        if zoning_agent:
            zm = zoning_agent.zone_manager
            zone_stats = {
                'total_zones': len(zm.zones),
                'total_population': zm.get_total_population(),
                'by_type': {}
            }
            from city.urban_planning.zone import ZoneType
            for zt in ZoneType:
                count = len(zm.get_zones_by_type(zt))
                if count > 0:
                    zone_stats['by_type'][zt.name] = count
        
        return {
            'agent_id': self.agent_id,
            'agent_type': 'PopulationCityPlanner',
            'city_stats': self.get_city_stats(),
            'expansion_count': len(self.expansion_history),
            'total_spawns': self.total_spawns,
            'last_expansion_time': self.last_expansion_time,
            'population_per_node': self.population_per_node,
            'expansion_threshold': self.expansion_threshold,
            'last_decision': self.last_decision,
            'city_stage': self._get_city_stage(),
            'time_of_day': time_period,
            'time_display': {
                'morning_rush': '早高峰 (7-9点)',
                'daytime': '白天 (9-17点)',
                'evening_rush': '晚高峰 (17-19点)',
                'night': '夜间 (19-7点)'
            }.get(time_period, time_period),
            'zone_stats': zone_stats
        }
    
    def _get_city_stage(self) -> str:
        """鏍规嵁鑺傜偣鏁伴噺鍒ゆ柇鍩庡競鍙戝睍闃舵銆"""
        if not self.environment:
            return 'initial'
        node_count = len(self.environment.road_network.nodes)
        if node_count >= self.stage_thresholds['mature']:
            return 'mature'
        elif node_count >= self.stage_thresholds['developing']:
            return 'developing'
        return 'initial'


# 淇濈暀鏃х被鍚嶄互渚垮吋瀹?
PlanningAgent = PopulationCityPlanner



