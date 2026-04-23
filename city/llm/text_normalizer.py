from __future__ import annotations

import re
from typing import Any


_CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")

_PHRASE_TRANSLATIONS: list[tuple[str, str]] = [
    ("平衡土地使用增长", "balanced land-use growth"),
    ("道路距离适中", "appropriate road access distance"),
    ("与周边区域类型高度兼容", "high compatibility with nearby zone types"),
    ("服务覆盖良好", "good service coverage"),
    ("规则规划", "rule-based planning"),
    ("LLM规划", "LLM planning"),
    ("使用LLM建议", "use LLM suggestion"),
    ("解析失败，使用默认策略", "malformed LLM response, use default strategy"),
    ("增加居住容量", "increase housing capacity"),
    ("完善商业配套", "improve commercial support"),
    ("提供就业机会", "provide employment capacity"),
    ("发展工业功能", "develop industrial capacity"),
    ("教育设施配套", "expand education services"),
    ("医疗服务配套", "expand medical services"),
    ("增加绿地空间", "add green space"),
    ("扩展居住空间", "expand residential space"),
    ("增加商业服务", "add commercial services"),
    ("增加绿地公园", "add parks and green space"),
    ("首个住宅区，奠定基础", "establish the first residential district"),
    ("缩小尺寸后找到合适位置", "found a valid location after reducing the footprint"),
    ("根据", "based on"),
    ("类型选择合适位置", "zone type requirements"),
    ("综合评分高", "high overall score"),
    ("交通便利", "good transport accessibility"),
    ("覆盖范围广", "broad service coverage"),
    ("靠近住宅区", "close to residential zones"),
    ("靠近中心", "close to the urban center"),
    ("边缘位置", "edge location"),
]

_ACTION_FALLBACKS: dict[str, str] = {
    "maintain": "Maintain the current state.",
    "adjust_signal": "Adjust signal timing based on current traffic conditions.",
    "switch_phase": "Switch the signal phase to improve flow balance.",
    "extend_current": "Extend the current phase to clear the active queue.",
    "no_action": "No intervention is required at the current step.",
    "publish_warning": "Publish a warning for the affected traffic area.",
    "accelerate": "Accelerate because the road ahead is clear.",
    "decelerate": "Decelerate to maintain safety and spacing.",
    "stop": "Stop because proceeding is not safe.",
    "proceed": "Proceed because the path ahead is available.",
    "emergency_brake": "Apply emergency braking due to collision risk.",
    "change_lane_left": "Change to the left lane to improve movement.",
    "change_lane_right": "Change to the right lane to improve movement.",
    "walk": "Walk because the path is currently safe.",
    "wait": "Wait until the crossing becomes safe.",
    "cross": "Cross because the current gap is safe.",
    "expand_city": "Expand the network based on current demand and layout balance.",
    "create_zone": "Create the selected zone based on current land-use needs.",
    "no_proposal": "No planning proposal is recommended at this stage.",
}


def contains_cjk(text: str | None) -> bool:
    return bool(text and _CJK_PATTERN.search(text))


def english_fallback_for_action(action: str | None, fallback: str | None = None) -> str:
    if fallback:
        return fallback
    return _ACTION_FALLBACKS.get((action or "").strip().lower(), "Model-selected action based on current state.")


def normalize_reason_text(text: Any, action: str | None = None, fallback: str | None = None) -> str:
    raw = "" if text is None else str(text).strip()
    if not raw:
        return english_fallback_for_action(action, fallback)

    normalized = " ".join(raw.split())
    if not contains_cjk(normalized):
        return normalized

    parts: list[str] = []
    lowered_ascii = normalized.lower()
    for source, target in _PHRASE_TRANSLATIONS:
        if source in normalized and target not in parts:
            parts.append(target)

    if parts:
        sentence = ", ".join(parts)
        return sentence[0].upper() + sentence[1:] + "."

    if "reason" in lowered_ascii:
        return normalized

    return english_fallback_for_action(action, fallback)


def normalize_text_list(values: Any, action: str | None = None) -> list[str]:
    if not isinstance(values, list):
        return []
    normalized: list[str] = []
    for item in values:
        text = normalize_reason_text(item, action=action, fallback="Planning step derived from the current context.")
        if text:
            normalized.append(text)
    return normalized


def normalize_decision_text_fields(
    payload: dict[str, Any] | None,
    action_key: str = "action",
    text_fields: tuple[str, ...] = ("reason", "reasoning", "connect_reason", "shape_consideration", "suggestions", "urban_planning_principles"),
    list_fields: tuple[str, ...] = ("reasoning_chain",),
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}

    normalized = dict(payload)
    action = str(normalized.get(action_key, "") or "")
    for field in text_fields:
        if field in normalized:
            normalized[field] = normalize_reason_text(normalized.get(field), action=action)
    for field in list_fields:
        if field in normalized:
            normalized[field] = normalize_text_list(normalized.get(field), action=action)
    return normalized
