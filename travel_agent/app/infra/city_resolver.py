"""旅行场景下的城市识别工具。"""

from __future__ import annotations

import re
from typing import Any


KNOWN_CITIES = (
    "上海",
    "北京",
    "杭州",
    "深圳",
    "广州",
    "苏州",
    "南京",
    "成都",
    "重庆",
    "西安",
)


def guess_trip_city(query: str, constraints: dict[str, Any]) -> str:
    """优先识别目的地城市，最后才退回出发城市。"""
    for field in ("destination_city", "target_city", "city"):
        value = str(constraints.get(field, "")).strip()
        if value:
            return value

    stripped_query = query.strip()
    if stripped_query:
        for city in KNOWN_CITIES:
            if any(marker in stripped_query for marker in (f"去{city}", f"到{city}", f"飞{city}", f"{city}玩")):
                return city

        mentioned = [
            (match.start(), city)
            for city in KNOWN_CITIES
            for match in re.finditer(re.escape(city), stripped_query)
        ]
        if mentioned:
            # 同一句话里提到多个城市时，
            # 更靠后的城市通常更接近目的地表达。
            return max(mentioned, key=lambda item: item[0])[1]

    start_city = str(constraints.get("start_city", "")).strip()
    if start_city:
        return start_city
    return "其他城市"
