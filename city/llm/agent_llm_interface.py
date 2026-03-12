"""
智能体LLM接口 - 优化版。

提供更丰富的上下文和更智能的决策支持。
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from city.llm.llm_client import LLMClient, LLMConfig
from city.llm.llm_pool import get_llm_pool

if TYPE_CHECKING:
    from city.agents.base import BaseAgent


class AgentLLMInterface:
    """
    智能体LLM接口 - 增强版。
    
    为不同类型的智能体提供LLM增强的决策能力。
    优化点：
    1. 更丰富的上下文信息
    2. 结构化决策输出
    3. 多步骤推理支持
    4. 死锁处理建议
    5. 支持多API Key池
    """

    def __init__(
        self,
        agent: BaseAgent,
        llm_client: LLMClient | None = None,
        use_llm: bool = True
    ) -> None:
        self.agent = agent
        
        # 优先使用传入的client，否则从池中获取
        if llm_client:
            self.llm_client = llm_client
        else:
            # 从池中获取分配给该agent的client
            pool = get_llm_pool()
            self.llm_client = pool.get_client_for_agent(agent.agent_id) or LLMClient()
        
        self.use_llm = use_llm and self.llm_client.is_available()
        self.system_prompt = self._get_system_prompt()
        self.decision_history: list[dict] = []  # 决策历史

    def _get_system_prompt(self) -> str:
        """根据智能体类型获取系统提示词 - 增强版。"""
        agent_type = self.agent.agent_type.name

        base_prompt = """你是一个专业的交通仿真决策助手。你的任务是基于当前交通状况，做出安全、高效的决策。

重要规则：
1. 必须考虑安全距离，避免碰撞
2. 遵守交通信号灯规则
3. 遇到死锁时要有恢复策略
4. 决策要考虑到周围所有车辆

你必须以JSON格式回复，格式如下：
{
    "action": "动作类型",
    "reason": "决策理由（简要）",
    "reasoning_chain": ["推理步骤1", "推理步骤2", ...],
    "confidence": 0.95,
    "parameters": {
        "target_speed": 目标速度,
        "safe_distance": 安全距离
    }
}"""

        vehicle_prompt = base_prompt + """

你是车辆驾驶专家。可用动作：
- accelerate: 加速（前方畅通，速度低于限速）
- decelerate: 减速（前方有车辆/障碍物，或接近红灯）
- maintain: 保持当前速度（稳定巡航）
- stop: 停车（红灯或完全堵住）
- proceed: 继续/恢复行驶（从停止状态起步）
- emergency_brake: 紧急制动（即将碰撞）
- change_lane_left/right: 变道（死锁恢复或超车）

决策逻辑：
1. 首先评估碰撞风险（time_to_collision < 3秒时必须减速）
2. 检查交通信号灯（红灯必须停车，黄灯视情况）
3. 评估前方车辆距离和速度
4. 如果是死锁状态，尝试变道或缓慢前进
"""

        pedestrian_prompt = base_prompt + """

你是行人安全专家。可用动作：walk, wait, cross
决策原则：安全第一，只在安全时过马路。
"""

        manager_prompt = base_prompt + """

你是交通管理者。可用动作：adjust_signal, publish_warning, no_action
目标：优化整体交通流量，减少拥堵。
"""

        prompts = {
            'VEHICLE': vehicle_prompt,
            'PEDESTRIAN': pedestrian_prompt,
            'TRAFFIC_MANAGER': manager_prompt,
            'TRAFFIC_PLANNER': base_prompt + "\n\n你是交通规划专家。提供长期规划建议。"
        }

        return prompts.get(agent_type, base_prompt)

    def get_llm_decision(self, perception: dict[str, Any] | None) -> dict[str, Any]:
        """
        获取LLM的决策建议 - 增强版。
        
        Args:
            perception: 感知信息字典

        Returns:
            LLM的决策建议，包含推理链
        """
        if not perception:
            return self._fallback_decision({'self': {'velocity': 0}})
        
        if not self.use_llm:
            return self._fallback_decision(perception)

        prompt = self._build_enhanced_prompt(perception)

        try:
            response = self.llm_client.structured_chat(
                message=prompt,
                system_prompt=self.system_prompt
            )

            if isinstance(response, dict):
                # 记录决策历史
                self.decision_history.append({
                    'timestamp': getattr(self.agent.environment, 'current_time', 0),
                    'perception_summary': self._summarize_perception(perception),
                    'decision': response
                })
                # 只保留最近10条历史
                self.decision_history = self.decision_history[-10:]
                return response
            else:
                return self._parse_response(str(response))

        except Exception as e:
            print(f"LLM决策获取失败: {e}")
            return self._fallback_decision(perception)

    def _build_enhanced_prompt(self, perception: dict[str, Any]) -> str:
        """构建增强版提示消息 - 丰富的上下文。"""
        agent_type = self.agent.agent_type.name

        if agent_type == 'VEHICLE':
            return self._build_vehicle_enhanced_prompt(perception)
        elif agent_type == 'PEDESTRIAN':
            return self._build_pedestrian_prompt(perception)
        elif agent_type == 'TRAFFIC_MANAGER':
            return self._build_manager_prompt(perception)
        else:
            return f"当前状态: {json.dumps(perception, ensure_ascii=False, indent=2)}"

    def _build_vehicle_enhanced_prompt(self, perception: dict[str, Any] | None) -> str:
        """构建车辆增强版决策提示。"""
        vehicle = self.agent
        if not perception:
            return '{"action": "maintain", "reason": "无感知数据", "confidence": 0.5}'
        self_info = perception.get('self', {})
        route_info = perception.get('route', {})
        front_v = perception.get('front_vehicle')
        rear_v = perception.get('rear_vehicle')
        left_v = perception.get('left_lane_vehicle')
        right_v = perception.get('right_lane_vehicle')
        traffic_light = perception.get('traffic_light')
        intersection = perception.get('intersection_queue')
        surroundings = perception.get('surroundings', [])
        is_deadlocked = perception.get('is_deadlocked', False)

        prompt_parts = [f"""=== 车辆驾驶决策请求 ===

【自身状态】
- ID: {vehicle.agent_id}
- 类型: {vehicle.vehicle_type.name}
- 当前速度: {self_info.get('velocity', 0):.2f} m/s (最大: {self_info.get('max_speed', 0):.2f})
- 当前状态: {self_info.get('state', 'UNKNOWN')}
- 位置: ({self_info.get('position', [0, 0])[0]:.1f}, {self_info.get('position', [0, 0])[1]:.1f})
- 当前路段进度: {route_info.get('progress_ratio', 0)*100:.1f}%
- 剩余节点: {route_info.get('remaining_nodes', 0)}
"""]

        # 添加前车信息
        if front_v:
            prompt_parts.append(f"""
【前方车辆 - 关键信息】
- 距离前车: {front_v['distance']:.2f} 米
- 前车速度: {front_v['velocity']:.2f} m/s
- 相对速度: {front_v['relative_velocity']:.2f} m/s
- 碰撞时间(TTC): {front_v['time_to_collision']:.2f} 秒
- 前车是否停止: {'是' if front_v['is_stopped'] else '否'}
""")
            # 碰撞风险评估
            if front_v['time_to_collision'] < 3:
                prompt_parts.append("⚠️ 警告：碰撞风险高！需要立即减速或停车！")
        else:
            prompt_parts.append("\n【前方车辆】前方无车辆，道路畅通")

        # 添加交通信号灯信息
        if traffic_light:
            prompt_parts.append(f"""
【交通信号灯】
- 信号灯状态: {traffic_light['state']}
- 距离路口: {traffic_light['distance']:.2f} 米
- 预计到达时间: {traffic_light['time_to_reach']:.2f} 秒
""")
            if traffic_light['distance'] < 30:
                if 'RED' in traffic_light['state']:
                    prompt_parts.append("🔴 红灯即将到达，需要准备停车")
                elif 'YELLOW' in traffic_light['state']:
                    prompt_parts.append("🟡 黄灯，根据距离决定是否通过")
        else:
            prompt_parts.append("\n【交通信号灯】前方无信号灯")

        # 添加路口排队信息
        if intersection and intersection['length'] > 0:
            prompt_parts.append(f"""
【路口排队情况】
- 排队车辆数: {intersection['length']}
- 是否被堵住: {'是' if intersection['is_blocked'] else '否'}
""")

        # 添加相邻车道信息
        lane_info = []
        if left_v:
            lane_info.append(f"左车道: {left_v['distance']:.1f}米{'前' if left_v['is_front'] else '后'}有车辆")
        else:
            lane_info.append("左车道: 空闲")
        if right_v:
            lane_info.append(f"右车道: {right_v['distance']:.1f}米{'前' if right_v['is_front'] else '后'}有车辆")
        else:
            lane_info.append("右车道: 空闲")
        prompt_parts.append(f"\n【相邻车道】\n" + "\n".join(f"  - {info}" for info in lane_info))

        # 添加周边环境概要
        if surroundings:
            prompt_parts.append(f"\n【周边环境】周边{len(surroundings)}辆车在100米范围内")

        # 添加死锁提示
        if is_deadlocked:
            prompt_parts.append("""

🚨 【死锁警告】车辆处于死锁状态！
请优先考虑：
1. 检查是否可以变道
2. 如果前车停止，等待并尝试变道
3. 如果是第一辆车，缓慢前进
""")

        # 添加决策历史（如果存在）
        if self.decision_history:
            last_decision = self.decision_history[-1]['decision']
            prompt_parts.append(f"""
【上次决策】
- 动作: {last_decision.get('action', 'unknown')}
- 理由: {last_decision.get('reason', 'N/A')}
""")

        prompt_parts.append("""

=== 决策要求 ===
请基于以上信息，提供驾驶决策。
特别注意事项：
1. 如果 collision time < 3秒，必须减速或停车
2. 红灯时必须停车，黄灯视情况决定
3. 如果被堵住(is_deadlocked=true)，尝试变道
4. 决策要平滑，避免频繁加减速

请以JSON格式回复。""")

        return "\n".join(prompt_parts)

    def _build_pedestrian_prompt(self, perception: dict[str, Any]) -> str:
        """构建行人决策提示。"""
        pedestrian = self.agent
        prompt = f"""=== 行人决策请求 ===

【自身状态】
- ID: {pedestrian.agent_id}
- 当前速度: {pedestrian.velocity:.2f} m/s
- 位置: ({pedestrian.position.x:.2f}, {pedestrian.position.y:.2f})

感知信息：
{json.dumps(perception, ensure_ascii=False, indent=2)}

请提供行动决策。"""
        return prompt

    def _build_manager_prompt(self, perception: dict[str, Any]) -> str:
        """构建交通管理者/红绿灯决策提示。"""
        manager = self.agent
        
        # 检查是 TrafficManager 还是 TrafficLightAgent
        if hasattr(manager, 'control_area'):
            # TrafficManager
            prompt = f"""=== 交通管理决策请求 ===

【管理状态】
- 管理区域: {len(manager.control_area)} 个节点
- 活跃事件: {len(manager.incidents)} 个

感知信息：
{json.dumps(perception, ensure_ascii=False, indent=2)}

请提供管理决策。"""
        elif hasattr(manager, 'control_node'):
            # TrafficLightAgent
            prompt = f"""=== 红绿灯控制决策请求 ===

【路口状态】
- 控制节点: {manager.control_node.name}
- 当前相位: {perception.get('current_phase', 'UNKNOWN')}

感知信息：
{json.dumps(perception, ensure_ascii=False, indent=2)}

请提供红绿灯配时决策（maintain/switch_phase/extend_current）。"""
        else:
            # 其他类型
            prompt = f"""=== 交通管理决策请求 ===

感知信息：
{json.dumps(perception, ensure_ascii=False, indent=2)}

请提供管理决策。"""
        
        return prompt

    def _summarize_perception(self, perception: dict | None) -> dict:
        """简化感知信息用于历史记录。"""
        if not perception:
            return {'velocity': 0, 'has_front_vehicle': False, 'traffic_light': None, 'is_deadlocked': False}
        return {
            'velocity': perception.get('self', {}).get('velocity'),
            'has_front_vehicle': perception.get('front_vehicle') is not None,
            'traffic_light': perception.get('traffic_light', {}).get('state'),
            'is_deadlocked': perception.get('is_deadlocked'),
        }

    def _parse_response(self, response: str) -> dict[str, Any]:
        """解析LLM响应 - 增强版。"""
        try:
            # 尝试多种方式提取JSON
            json_str = None
            
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                json_str = response[start:end].strip()
            elif "```" in response:
                start = response.find("```") + 3
                end = response.find("```", start)
                json_str = response[start:end].strip()
            else:
                # 尝试直接解析整个响应
                json_str = response.strip()

            if json_str:
                result = json.loads(json_str)
                # 确保必要字段存在
                if 'action' not in result:
                    result['action'] = 'maintain'
                if 'reason' not in result:
                    result['reason'] = '使用LLM建议'
                if 'confidence' not in result:
                    result['confidence'] = 0.8
                return result
                
        except (json.JSONDecodeError, ValueError) as e:
            print(f"JSON解析失败: {e}, 原始响应: {response[:200]}")
            
        return {"action": "maintain", "reason": "解析失败，使用默认策略", "confidence": 0.5}

    def _fallback_decision(self, perception: dict[str, Any] | None) -> dict[str, Any]:
        """当LLM不可用时使用增强版默认决策。"""
        agent_type = self.agent.agent_type.name
        
        # 确保 perception 不为 None
        if not perception:
            perception = {}
        
        # 基于感知信息做简单的规则决策
        if agent_type == 'VEHICLE':
            front_v = perception.get('front_vehicle')
            traffic_light = perception.get('traffic_light')
            is_deadlocked = perception.get('is_deadlocked', False)
            
            # 紧急制动
            if front_v and front_v.get('time_to_collision', float('inf')) < 2:
                return {
                    'action': 'emergency_brake',
                    'reason': '碰撞风险高，紧急制动',
                    'confidence': 0.95
                }
            
            # 红灯停车
            if traffic_light and 'RED' in traffic_light.get('state', ''):
                if traffic_light.get('distance', 100) < 20:
                    return {
                        'action': 'stop',
                        'reason': '红灯，需要停车',
                        'confidence': 0.9
                    }
                else:
                    return {
                        'action': 'decelerate',
                        'reason': '前方红灯，准备停车',
                        'confidence': 0.85
                    }
            
            # 跟车减速
            if front_v and front_v.get('distance', 100) < 15:
                return {
                    'action': 'decelerate',
                    'reason': f"前车距离{front_v['distance']:.1f}米，保持安全距离",
                    'confidence': 0.8
                }
            
            # 死锁恢复
            if is_deadlocked:
                return {
                    'action': 'change_lane_left',
                    'reason': '死锁恢复：尝试变道',
                    'confidence': 0.6
                }
            
            # 默认加速或保持
            velocity = perception.get('self', {}).get('velocity', 0)
            max_speed = perception.get('self', {}).get('max_speed', 30)
            
            if velocity < max_speed * 0.8:
                return {
                    'action': 'accelerate',
                    'reason': '道路畅通，加速至目标速度',
                    'confidence': 0.75
                }
            
            return {
                'action': 'maintain',
                'reason': '巡航中',
                'confidence': 0.7
            }

        fallbacks = {
            'PEDESTRIAN': {'action': 'wait', 'reason': '使用默认策略', 'confidence': 0.5},
            'TRAFFIC_MANAGER': {'action': 'no_action', 'reason': '使用默认策略', 'confidence': 0.5},
            'TRAFFIC_PLANNER': {'action': 'no_proposal', 'reason': '使用默认策略', 'confidence': 0.5}
        }

        return fallbacks.get(agent_type, {'action': 'unknown', 'reason': '未知类型', 'confidence': 0.5})

    def get_decision_explanation(self) -> str:
        """获取最后一次决策的解释（用于前端展示）。"""
        if not self.decision_history:
            return "暂无决策历史"
        
        last = self.decision_history[-1]
        decision = last['decision']
        
        explanation = f"""
决策时间: {last['timestamp']:.1f}s
执行动作: {decision.get('action', 'unknown')}
决策理由: {decision.get('reason', 'N/A')}
置信度: {decision.get('confidence', 0):.0%}
"""
        if 'reasoning_chain' in decision:
            explanation += "\n推理过程:\n"
            for i, step in enumerate(decision['reasoning_chain'], 1):
                explanation += f"  {i}. {step}\n"
        
        return explanation


_global_llm_client = None


def get_global_llm_client() -> LLMClient:
    """获取全局LLM客户端实例。"""
    global _global_llm_client
    if _global_llm_client is None:
        _global_llm_client = LLMClient()
    return _global_llm_client


def set_global_llm_client(client: LLMClient) -> None:
    """设置全局LLM客户端实例。"""
    global _global_llm_client
    _global_llm_client = client
