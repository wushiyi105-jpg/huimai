"""离线模式:价格全部按内置报价算,结论按规则给,不假装懂商品。"""

from __future__ import annotations

from . import tools


def compare(product: dict, offers: list[dict], target: float = 0.0) -> dict:
    st = tools.stats(offers)
    if not st.get("count"):
        return {"verdict": "没报价", "best_platform": "", "reasons": [], "risks": [],
                "advice": ["先加一条报价再看"], "stats": st, "offline": True,
                "note": "离线模式:没有报价,给不出结论"}
    risky = tools.outliers(offers)
    best = st["best"]
    safe = [o for o in offers if o["platform"] not in {x["platform"] for x in risky}]
    recommend = min(safe, key=tools.total) if risky and safe else best
    up = tools.unit_price(product.get("specs", ""), st["best_total"])
    reasons = [f"{best['platform']} 总价最低:{tools.money(st['best_total'])}"
               f"(商品 {tools.money(best['price'])} + 运费 {tools.money(best.get('shipping', 0))})"]
    if st["count"] >= 2:
        reasons.append(f"各渠道总价从 {tools.money(st['min'])} 到 {tools.money(st['max'])},"
                       f"中位价 {tools.money(st['median'])}")
    if up["value"]:
        reasons.append(f"按规格 {product.get('specs', '')} 算,折合 {up['value']} 元/{up['unit']}")
    risks = []
    best_flags = tools.flags(best, offers)
    if best_flags:
        risks.append(f"最低价渠道有风险:{'、'.join(best_flags)}")
    for o in risky:
        if o is not best:
            risks.append(f"{o['platform']} 的 {tools.money(tools.total(o))} 明显低于其他渠道,先核实货源")
    advice = ["付款前确认是否官方店/自营,以及发票与保修"]
    if st["spread_ratio"] >= 0.35:
        advice.append("价差超过三成,优先看售后而不是只看价格")
    if target:
        advice.append(f"目标价 {tools.money(target)}:" +
                      ("已经达到,可以下手" if st["best_total"] <= target else "还没到,继续等"))
    advice.append("把这家加进关注清单,到价再买")
    return {
        "verdict": tools.verdict(st, risky, target), "best_platform": recommend["platform"],
        "lowest_platform": best["platform"],
        "reasons": reasons, "risks": risks, "advice": advice[:4],
        "stats": st, "offline": True,
        "note": "离线模式:价格来自内置示例报价,结论按价差与渠道说明的规则给,不做真伪鉴定",
    }
