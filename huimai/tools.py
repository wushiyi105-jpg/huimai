"""本地规则:价格统计、单位价、异常低价、渠道风险、结论。

这里所有数字都从内置报价里算出来,模型只负责解释。
"""

from __future__ import annotations

import re
import statistics

_PRICE = re.compile(r"[¥￥]\s*(\d+(?:\.\d+)?)")
_UNIT = re.compile(r"(\d+(?:\.\d+)?)\s*(万)?\s*(ml|mL|g|kg|片|包|袋|支|瓶|盒|只|条|个)")
_MULT = re.compile(r"(\d+)\s*(包|盒|袋|瓶|支|只)\s*[×x*]\s*(\d+)")
_NUM = re.compile(r"\d+(?:\.\d+)?")

RISK_WORDS = ("临期", "无票", "非官方", "二手", "拼单", "代购", "清仓")


def money(x: float) -> str:
    return f"¥{x:.0f}" if abs(x - round(x)) < 0.01 else f"¥{x:.2f}"


def numbers(text: str) -> list[str]:
    return _NUM.findall(text or "")


def new_numbers(before: str, after: str) -> list[str]:
    old = set(numbers(before))
    return [n for n in numbers(after) if n not in old]


def contains_quote(quote: str, text: str, min_len: int = 6) -> bool:
    return len(quote or "") >= min_len and quote in (text or "")


def clamp(text: str, limit: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit] + "…"


def total(offer: dict) -> float:
    return float(offer["price"]) + float(offer.get("shipping", 0))


def stats(offers: list[dict]) -> dict:
    if not offers:
        return {"count": 0}
    totals = [total(o) for o in offers]
    prices = [float(o["price"]) for o in offers]
    best = min(offers, key=total)
    med = statistics.median(totals)
    return {
        "count": len(offers),
        "min": min(totals), "max": max(totals),
        "median": med, "mean": round(statistics.fmean(totals), 2),
        "spread": round(max(totals) - min(totals), 2),
        "spread_ratio": round((max(totals) - min(totals)) / med, 2) if med else 0,
        "price_min": min(prices), "price_max": max(prices),
        "best": best, "best_total": total(best),
    }


def units(specs: str) -> tuple[float, str]:
    """从规格里估总量,如「3 包 × 60 片」→ 180 片;估不出就返回 (0, '')。"""
    m = _MULT.search(specs or "")
    if m:
        return float(m.group(1)) * float(m.group(3)), m.group(2)
    m = _UNIT.search(specs or "")
    if not m:
        return 0.0, ""
    val = float(m.group(1)) * (10000 if m.group(2) else 1)
    unit = m.group(3)
    if unit in ("kg",):
        return val * 1000, "g"
    if unit in ("ml", "mL"):
        return val, "ml"
    return val, unit


def unit_price(specs: str, amount: float) -> dict:
    qty, unit = units(specs)
    if not qty or not amount:
        return {"qty": 0, "unit": "", "value": 0}
    return {"qty": qty, "unit": unit, "value": round(amount / qty, 4)}


def outliers(offers: list[dict]) -> list[dict]:
    """低于中位总价 60% 的报价,标出来但不自动判假。"""
    if len(offers) < 2:
        return []
    med = statistics.median(total(o) for o in offers)
    return [o for o in offers if med and total(o) < med * 0.6]


def flags(offer: dict, offers: list[dict]) -> list[str]:
    out = []
    if len(offers) >= 2:
        med = statistics.median(total(o) for o in offers)
        if med and total(offer) < med * 0.6:
            out.append(f"总价只有中位价的 {total(offer) / med:.0%},低得不正常")
    for w in RISK_WORDS:
        if w in (offer.get("note") or "") or w in (offer.get("platform") or ""):
            out.append(f"渠道说明里出现「{w}」")
    if not offer.get("note"):
        out.append("没有票据/来源说明")
    return out


def verdict(st: dict, risky: list[dict], target: float = 0.0) -> str:
    if not st.get("count"):
        return "没报价"
    if risky:
        return "换渠道"
    if target and st["best_total"] <= target:
        return "值得买"
    if st["count"] >= 3 and st["spread_ratio"] >= 0.35:
        return "再等等"
    return "值得买"


def offer_text(offers: list[dict]) -> str:
    return "\n".join(
        f"{o['platform']} {money(o['price'])}(运费 {money(o['shipping'])}) {o.get('note', '')}".strip()
        for o in offers
    )


TOOLS = [
    {"name": "price_stats", "desc": "返回最低/最高/中位/极差与最低总价的那家"},
    {"name": "risk_flags", "desc": "返回每家的异常低价与渠道风险提示"},
]


def execute(name: str, ctx: dict) -> dict:
    offers = ctx.get("offers", [])
    if name == "price_stats":
        st = stats(offers)
        return {k: st[k] for k in ("count", "min", "max", "median", "spread", "spread_ratio")}
    if name == "risk_flags":
        return {o["platform"]: flags(o, offers) for o in offers}
    return {"error": f"未知工具:{name}"}
