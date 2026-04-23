"""
智能体LLM接口 - 优化版。

提供更丰富的上下文和更智能的决策支持。
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from city.llm.llm_client import LLMClient, LLMConfig
from city.llm.llm_pool import get_llm_pool
from city.llm.text_normalizer import normalize_decision_text_fields

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
        """Return an English-only system prompt for the current agent type."""
        agent_type = self.agent.agent_type.name

        base_prompt = """You are a professional traffic simulation decision assistant.
Make safe, efficient, and realistic decisions based on the current traffic state.

Important rules:
1. Always prioritize safety and collision avoidance.
2. Follow traffic signal and right-of-way rules.
3. If the scene is deadlocked, prefer recovery actions that unblock traffic safely.
4. Return valid JSON only.
5. Write every explanation in English only.

Use this JSON structure:
{
  "action": "action_name",
  "reason": "short English reason",
  "reasoning_chain": ["step 1", "step 2"],
  "confidence": 0.95,
  "parameters": {
    "target_speed": 0.0,
    "safe_distance": 0.0
  }
}"""

        vehicle_prompt = base_prompt + """

You are the driving policy for a vehicle agent.
Available actions: accelerate, decelerate, maintain, stop, proceed, emergency_brake, change_lane_left, change_lane_right.
Prefer smooth control unless safety requires urgent intervention."""

        pedestrian_prompt = base_prompt + """

You are the safety policy for a pedestrian agent.
Available actions: walk, wait, cross.
Only cross when the situation is clearly safe."""

        manager_prompt = base_prompt + """

You are the control policy for a traffic management agent.
Available actions: adjust_signal, publish_warning, no_action.
Optimize flow while maintaining safety and fairness across approaches."""

        prompts = {
            'VEHICLE': vehicle_prompt,
            'PEDESTRIAN': pedestrian_prompt,
            'TRAFFIC_MANAGER': manager_prompt,
            'TRAFFIC_PLANNER': base_prompt + "\n\nYou are a transport planning expert. Provide long-term planning recommendations in English only."
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
                response = self._finalize_decision(response)
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
            return (
                "Current state:\n"
                f"{json.dumps(perception, ensure_ascii=False, indent=2)}\n\n"
                "Return valid JSON only and write every explanation in English."
            )

    def _build_vehicle_enhanced_prompt(self, perception: dict[str, Any] | None) -> str:
        """Build an English driving prompt with structured context."""
        vehicle = self.agent
        if not perception:
            return '{"action": "maintain", "reason": "No perception data is available.", "confidence": 0.5}'

        self_info = perception.get('self', {})
        route_info = perception.get('route', {})
        front_v = perception.get('front_vehicle')
        left_v = perception.get('left_lane_vehicle')
        right_v = perception.get('right_lane_vehicle')
        traffic_light = perception.get('traffic_light')
        intersection = perception.get('intersection_queue')
        surroundings = perception.get('surroundings', [])
        is_deadlocked = perception.get('is_deadlocked', False)

        prompt_parts = [f"""=== Vehicle Driving Decision Request ===

[Self State]
- ID: {vehicle.agent_id}
- Type: {vehicle.vehicle_type.name}
- Current speed: {self_info.get('velocity', 0):.2f} m/s (max: {self_info.get('max_speed', 0):.2f})
- Current state: {self_info.get('state', 'UNKNOWN')}
- Position: ({self_info.get('position', [0, 0])[0]:.1f}, {self_info.get('position', [0, 0])[1]:.1f})
- Route progress: {route_info.get('progress_ratio', 0) * 100:.1f}%
- Remaining nodes: {route_info.get('remaining_nodes', 0)}
"""]

        if front_v:
            prompt_parts.append(f"""
[Lead Vehicle]
- Distance: {front_v['distance']:.2f} m
- Speed: {front_v['velocity']:.2f} m/s
- Relative speed: {front_v['relative_velocity']:.2f} m/s
- Time to collision: {front_v['time_to_collision']:.2f} s
- Lead vehicle stopped: {front_v['is_stopped']}
""")
            if front_v['time_to_collision'] < 3:
                prompt_parts.append("High collision risk detected. Immediate deceleration or stopping should be considered.")
        else:
            prompt_parts.append("[Lead Vehicle] No vehicle is directly ahead.")

        if traffic_light:
            prompt_parts.append(f"""
[Traffic Light]
- State: {traffic_light['state']}
- Distance to intersection: {traffic_light['distance']:.2f} m
- Estimated time to reach: {traffic_light['time_to_reach']:.2f} s
""")
        else:
            prompt_parts.append("[Traffic Light] No relevant signal is ahead.")

        if intersection and intersection['length'] > 0:
            prompt_parts.append(f"""
[Intersection Queue]
- Queue length: {intersection['length']}
- Blocked: {intersection['is_blocked']}
""")

        lane_info = []
        lane_info.append(
            f"Left lane: {'occupied' if left_v else 'clear'}"
            + (f", vehicle {left_v['distance']:.1f} m {'ahead' if left_v['is_front'] else 'behind'}" if left_v else "")
        )
        lane_info.append(
            f"Right lane: {'occupied' if right_v else 'clear'}"
            + (f", vehicle {right_v['distance']:.1f} m {'ahead' if right_v['is_front'] else 'behind'}" if right_v else "")
        )
        prompt_parts.append("[Adjacent Lanes]\n" + "\n".join(f"- {info}" for info in lane_info))

        if surroundings:
            prompt_parts.append(f"[Nearby Environment] {len(surroundings)} nearby vehicles are within 100 m.")

        if is_deadlocked:
            prompt_parts.append("""
[Deadlock Warning]
The vehicle appears to be deadlocked.
Prefer safe recovery actions such as lane changes or cautious forward progress.
""")

        if self.decision_history:
            last_decision = self.decision_history[-1]['decision']
            prompt_parts.append(f"""
[Previous Decision]
- Action: {last_decision.get('action', 'unknown')}
- Reason: {last_decision.get('reason', 'N/A')}
""")

        prompt_parts.append("""
[Decision Requirements]
1. If time to collision is below 3 seconds, prioritize braking or stopping.
2. Stop for red lights. Treat yellow lights based on distance and safety.
3. If the vehicle is deadlocked, consider lane changes or cautious recovery.
4. Keep control smooth and avoid unnecessary oscillation.

Return valid JSON only, and write the reason in English.
""")

        return "\n".join(prompt_parts)

    def _build_pedestrian_prompt(self, perception: dict[str, Any]) -> str:
        """Build an English pedestrian decision prompt."""
        pedestrian = self.agent
        return f"""=== Pedestrian Decision Request ===

[Self State]
- ID: {pedestrian.agent_id}
- Current speed: {pedestrian.velocity:.2f} m/s
- Position: ({pedestrian.position.x:.2f}, {pedestrian.position.y:.2f})

[Perception]
{json.dumps(perception, ensure_ascii=False, indent=2)}

Return valid JSON only and explain the decision in English."""

    def _build_manager_prompt(self, perception: dict[str, Any]) -> str:
        """Build an English traffic management or signal control prompt."""
        manager = self.agent
        
        if hasattr(manager, 'control_area'):
            prompt = f"""=== Traffic Management Decision Request ===

[Management State]
- Controlled nodes: {len(manager.control_area)}
- Active incidents: {len(manager.incidents)}

[Perception]
{json.dumps(perception, ensure_ascii=False, indent=2)}

Return valid JSON only and explain the decision in English."""
        elif hasattr(manager, 'control_node'):
            prompt = f"""=== Signal Control Decision Request ===

[Intersection State]
- Controlled node: {manager.control_node.name}
- Current phase: {perception.get('current_phase', 'UNKNOWN')}

[Perception]
{json.dumps(perception, ensure_ascii=False, indent=2)}

Choose one of: maintain, switch_phase, extend_current.
Return valid JSON only and explain the decision in English."""
        else:
            prompt = f"""=== Traffic Control Decision Request ===

[Perception]
{json.dumps(perception, ensure_ascii=False, indent=2)}

Return valid JSON only and explain the decision in English."""
        
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

    def _extract_json_candidate(self, response: str) -> str:
        """Extract the most likely JSON fragment from a raw LLM response."""
        text = (response or "").strip()

        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end != -1:
                text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end != -1:
                text = text[start:end].strip()

        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            text = text[first_brace:last_brace + 1]

        return text.strip()

    def _clean_json_candidate(self, json_str: str) -> str:
        """Repair common LLM JSON corruption patterns before parsing."""
        text = (json_str or "").strip()
        text = text.replace("\r", "")
        text = text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
        text = text.replace("，", ",").replace("：", ":")

        text = re.sub(r"(?:_?isis)+", "", text, flags=re.IGNORECASE)

        while '""' in text:
            text = text.replace('""', '"')

        text = text.replace('"is_reason"', '"reason"')
        text = re.sub(r",\s*([}\]])", r"\1", text)
        return text.strip()

    def _normalize_action_name(self, action: Any) -> str:
        """Normalize noisy action strings returned by the LLM."""
        if not isinstance(action, str):
            return "maintain"

        cleaned = re.sub(r"(?:_?isis)+", "", action, flags=re.IGNORECASE)
        cleaned = cleaned.strip().strip('"').strip("'").lower()
        cleaned = re.sub(r"[^a-z_]+", "_", cleaned)
        cleaned = re.sub(r"_+", "_", cleaned).strip("_")

        action_aliases = {
            "adjust_signal": "adjust_signal",
            "adjust_signals": "adjust_signal",
            "switch_phase": "switch_phase",
            "extend_current": "extend_current",
            "maintain": "maintain",
            "maintain_current_light": "maintain",
            "no_action": "no_action",
            "publish_warning": "publish_warning",
            "accelerate": "accelerate",
            "decelerate": "decelerate",
            "stop": "stop",
            "proceed": "proceed",
            "emergency_brake": "emergency_brake",
            "change_lane_left": "change_lane_left",
            "change_lane_right": "change_lane_right",
            "walk": "walk",
            "wait": "wait",
            "cross": "cross",
        }

        if cleaned in action_aliases:
            return action_aliases[cleaned]
        if cleaned.startswith("adjust_signal"):
            return "adjust_signal"
        if cleaned.startswith("maintain"):
            return "maintain"
        return cleaned or "maintain"

    def _salvage_decision_fields(self, response: str) -> dict[str, Any]:
        """Best-effort extraction when valid JSON cannot be recovered."""
        text = self._clean_json_candidate(self._extract_json_candidate(response))

        action_match = re.search(r'"?action"?\s*:\s*"?(?P<value>[A-Za-z_]+)', text, flags=re.IGNORECASE)
        reason_match = re.search(r'"?(?:reason|is_reason)"?\s*:\s*"?(?P<value>[^"\n,}{]+)', text, flags=re.IGNORECASE)
        confidence_match = re.search(r'"?confidence"?\s*:\s*(?P<value>\d+(?:\.\d+)?)', text, flags=re.IGNORECASE)

        return {
            "action": self._normalize_action_name(action_match.group("value") if action_match else "maintain"),
            "reason": (reason_match.group("value").strip() if reason_match else "Malformed LLM response, fallback decision"),
            "confidence": float(confidence_match.group("value")) if confidence_match else 0.4,
        }

    def _finalize_decision(self, result: dict[str, Any]) -> dict[str, Any]:
        """Ensure required decision fields are present and normalized."""
        normalized = normalize_decision_text_fields(dict(result or {}))
        normalized["action"] = self._normalize_action_name(normalized.get("action"))
        normalized["reason"] = normalize_reason_text(normalized.get("reason"), action=normalized["action"], fallback="Use LLM suggestion.")
        normalized["confidence"] = float(normalized.get("confidence", 0.8) or 0.8)
        return normalized

    def _parse_response(self, response: str) -> dict[str, Any]:
        """解析LLM响应 - 增强版。"""
        json_str = self._extract_json_candidate(response)
        candidates = [json_str]

        cleaned = self._clean_json_candidate(json_str)
        if cleaned and cleaned not in candidates:
            candidates.append(cleaned)

        last_error: Exception | None = None
        for candidate in candidates:
            if not candidate:
                continue
            try:
                result = json.loads(candidate)
                if isinstance(result, dict):
                    return self._finalize_decision(result)
            except (json.JSONDecodeError, ValueError) as e:
                last_error = e

        salvage = self._salvage_decision_fields(response)
        if salvage:
            print(f"JSON解析失败: {last_error}, 已启用容错提取, 原始响应: {response[:200]}")
            return self._finalize_decision(salvage)

        print(f"JSON解析失败: {last_error}, 原始响应: {response[:200]}")
        return {"action": "maintain", "reason": "Malformed LLM response, use safe fallback", "confidence": 0.5}

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
                    'reason': 'Collision risk is high, apply emergency braking.',
                    'confidence': 0.95
                }
            
            # 红灯停车
            if traffic_light and 'RED' in traffic_light.get('state', ''):
                if traffic_light.get('distance', 100) < 20:
                    return {
                        'action': 'stop',
                        'reason': 'Red light ahead, stop the vehicle.',
                        'confidence': 0.9
                    }
                else:
                    return {
                        'action': 'decelerate',
                        'reason': 'Red light ahead, decelerate and prepare to stop.',
                        'confidence': 0.85
                    }
            
            # 跟车减速
            if front_v and front_v.get('distance', 100) < 15:
                return {
                    'action': 'decelerate',
                    'reason': f"Lead vehicle is {front_v['distance']:.1f} m ahead, maintain a safe gap.",
                    'confidence': 0.8
                }
            
            # 死锁恢复
            if is_deadlocked:
                return {
                    'action': 'change_lane_left',
                    'reason': 'Deadlock recovery: attempt a lane change.',
                    'confidence': 0.6
                }
            
            # 默认加速或保持
            velocity = perception.get('self', {}).get('velocity', 0)
            max_speed = perception.get('self', {}).get('max_speed', 30)
            
            if velocity < max_speed * 0.8:
                return {
                    'action': 'accelerate',
                    'reason': 'The road ahead is clear, accelerate toward the target speed.',
                    'confidence': 0.75
                }
            
            return {
                'action': 'maintain',
                'reason': 'Maintain the current cruising state.',
                'confidence': 0.7
            }

        fallbacks = {
            'PEDESTRIAN': {'action': 'wait', 'reason': 'Use the default pedestrian fallback.', 'confidence': 0.5},
            'TRAFFIC_MANAGER': {'action': 'no_action', 'reason': 'Use the default traffic-management fallback.', 'confidence': 0.5},
            'TRAFFIC_PLANNER': {'action': 'no_proposal', 'reason': 'Use the default planning fallback.', 'confidence': 0.5}
        }

        return fallbacks.get(agent_type, {'action': 'unknown', 'reason': 'Unknown agent type, use a safe fallback.', 'confidence': 0.5})

    def get_decision_explanation(self) -> str:
        """获取最后一次决策的解释（用于前端展示）。"""
        if not self.decision_history:
            return "No decision history is available."
        
        last = self.decision_history[-1]
        decision = last['decision']
        
        explanation = f"""
Decision time: {last['timestamp']:.1f}s
Action: {decision.get('action', 'unknown')}
Reason: {decision.get('reason', 'N/A')}
Confidence: {decision.get('confidence', 0):.0%}
"""
        if 'reasoning_chain' in decision:
            explanation += "\nReasoning chain:\n"
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
