"""模型主路径:解释价差、点风险、给买不买的建议。"""

from __future__ import annotations

from . import llm, mock, tools

VERDICTS = ("值得买", "再等等", "换渠道", "别买", "没报价")

COMPARE_SYSTEM = """你是帮人看价格的购物参谋,只依据给定的商品信息与报价表说话。

规则:
1. 只输出 JSON,不要解释。
2. verdict 只能取:值得买 / 再等等 / 换渠道 / 别买 / 没报价。
3. best_platform 必须是报价表里出现过的渠道名,照抄,不许自创。
4. 任何数字只能取用报价表或系统给的统计值,不许自己算新的数字。
5. 不判定真伪,只提示风险(异常低价、临期、无票、非官方)。
6. reasons 最多 3 条,advice 最多 4 条,每条不超过 60 字。

JSON 模板:
{"verdict": "再等等", "best_platform": "京东自营", "reasons": ["..."], "risks": ["..."], "advice": ["..."]}"""


def _use_model(cfg) -> bool:
    return bool((cfg or {}).get("api_key"))


def allowed_numbers(product: dict, offers: list[dict], target: float = 0.0) -> set[str]:
    st = tools.stats(offers)
    text = tools.offer_text(offers) + " " + str(product.get("specs", ""))
    nums = set(tools.numbers(text))
    for key in ("min", "max", "median", "mean", "spread"):
        if key in st:
            nums.add(str(int(round(st[key]))) if abs(st[key] - round(st[key])) < 0.01 else f"{st[key]:.2f}")
    if st.get("spread_ratio"):
        nums.add(str(int(round(st["spread_ratio"] * 100))))
    if st.get("median"):
        nums.add(str(int(round(st["best_total"] / st["median"] * 100))))
    totals = sorted({int(round(tools.total(o))) for o in offers})
    if target:
        nums.add(str(int(round(target))))
        totals.append(int(round(target)))
    for i, a in enumerate(totals):
        for b in totals[i + 1:]:
            nums.add(str(abs(a - b)))
    return nums


def verify_compare(product: dict, offers: list[dict], data: dict,
                   target: float = 0.0) -> tuple[dict, list[str]]:
    problems: list[str] = []
    platforms = [o["platform"] for o in offers]
    local = mock.compare(product, offers)
    best = str(data.get("best_platform", "")).strip()
    if best not in platforms:
        if best:
            problems.append(f"「{best}」不在报价表里,换成最低价渠道")
        best = local["best_platform"]
    outlier_platforms = {o["platform"] for o in tools.outliers(offers)}
    verdict = str(data.get("verdict", "")).strip()
    if verdict not in VERDICTS:
        problems.append(f"结论「{verdict}」不在允许值里,按规则改判")
        verdict = local["verdict"]
    if verdict == "换渠道" and best in outlier_platforms:
        safe = [o for o in offers if o["platform"] not in outlier_platforms]
        if safe:
            safer = min(safe, key=tools.total)["platform"]
            problems.append(f"「{best}」是异常低价渠道,既然结论是换渠道,推荐改成 {safer}")
            best = safer
    allowed = allowed_numbers(product, offers, target)

    def clean(items, limit: int) -> list[str]:
        out = []
        for it in items or []:
            s = tools.clamp(str(it), 60)
            bad = tools.new_numbers(" ".join(allowed), s)
            if bad:
                problems.append(f"「{s}」里出现报价表没有的数字 {bad[0]},已丢弃")
                continue
            out.append(s)
        return out[:limit]

    reasons = clean(data.get("reasons"), 3)
    risks = clean(data.get("risks"), 3)
    advice = clean(data.get("advice"), 4)
    if not reasons:
        reasons = local["reasons"]
    if not advice:
        advice = local["advice"]
    return {"verdict": verdict, "best_platform": best,
            "lowest_platform": local.get("lowest_platform", ""),
            "reasons": reasons, "risks": risks, "advice": advice}, problems


def compare(product: dict, offers: list[dict], target: float = 0.0,
            cfg: dict | None = None, force_mock: bool = False) -> dict:
    st = tools.stats(offers)
    if force_mock or not _use_model(cfg):
        return mock.compare(product, offers, target)
    if not offers:
        return mock.compare(product, offers, target)
    user = (
        f"【商品】{product.get('name', '')}\n【分类】{product.get('category', '')}\n"
        f"【规格】{product.get('specs', '')}\n【备注】{product.get('note', '')}\n\n"
        f"【报价表】\n{tools.offer_text(offers)}\n\n"
        f"【本地统计】最低总价 {tools.money(st['min'])},最高 {tools.money(st['max'])},"
        f"中位 {tools.money(st['median'])},极差 {tools.money(st['spread'])},"
        f"极差占中位 {st['spread_ratio']:.0%}\n"
        f"【目标价】{tools.money(target) if target else '未设'}\n"
    )
    text = llm.chat(
        [{"role": "system", "content": COMPARE_SYSTEM}, {"role": "user", "content": user}],
        cfg, temperature=0.3, max_tokens=1200,
    )
    data = llm.extract_json(text)
    body, problems = verify_compare(product, offers, data if isinstance(data, dict) else {}, target)
    body.update({"stats": st, "problems": problems, "offline": False})
    return body
