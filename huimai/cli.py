"""命令行入口:python -m huimai <子命令>。"""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import __version__, agent, llm, tools
from .db import Database

MOCK_BANNER = "· 离线模式:没配 LLM_API_KEY,或显式 --mock。价格按内置报价算,结论按规则给。"

SEED_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "products-sample.json")

_OPEN: list[Database] = []


def _db(args) -> Database:
    db = Database(args.db)
    _OPEN.append(db)
    return db


def _close_all() -> None:
    for db in _OPEN:
        try:
            db.close()
        except Exception:
            pass
    _OPEN.clear()


def render_compare(result: dict) -> str:
    lines = []
    st = result.get("stats") or {}
    if st.get("count"):
        lines.append(f"结论:{result['verdict']}  ·  推荐渠道:{result['best_platform']}"
                     f"  ·  本地最低到手:{result.get('lowest_platform') or result['best_platform']}")
        lines.append(f"总价 {tools.money(st['min'])}–{tools.money(st['max'])},"
                     f"中位 {tools.money(st['median'])},极差 {tools.money(st['spread'])}"
                     f"(占中位 {st['spread_ratio']:.0%})")
    else:
        lines.append(f"结论:{result.get('verdict', '没报价')}")
    if result.get("reasons"):
        lines.append("")
        lines.append("依据:")
        lines.extend(f"  · {r}" for r in result["reasons"])
    if result.get("risks"):
        lines.append("")
        lines.append("风险:")
        lines.extend(f"  ! {r}" for r in result["risks"])
    if result.get("advice"):
        lines.append("")
        lines.append("建议:")
        lines.extend(f"  {i}. {a}" for i, a in enumerate(result["advice"], 1))
    if result.get("problems"):
        lines.append("")
        lines.extend(f"! {p}" for p in result["problems"])
    if result.get("note"):
        lines.append(result["note"])
    return "\n".join(lines)


def _product_or_exit(db: Database, key) -> dict:
    p = db.get_product(key)
    if not p:
        print(f"❌ 找不到商品「{key}」。先 python -m huimai seed", file=sys.stderr)
        raise SystemExit(1)
    return p


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="huimai", description="惠买 · 比价购物:内置报价、风险提示、关注清单。")
    p.add_argument("--version", action="version", version=f"huimai {__version__}")
    p.add_argument("--mock", action="store_true", help="强制离线模式")
    p.add_argument("--json", action="store_true")
    p.add_argument("--model")
    p.add_argument("--base-url")
    p.add_argument("--api-key")
    p.add_argument("--db", default="data/huimai.db")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("seed", help="导入内置示例报价")
    sub.add_parser("items", help="商品列表")
    s = sub.add_parser("show", help="看商品与报价")
    s.add_argument("key")
    c = sub.add_parser("compare", help="比价与建议")
    c.add_argument("key")
    c.add_argument("--target", type=float, default=0.0, help="目标价")
    o = sub.add_parser("offer", help="补一条报价")
    o.add_argument("key")
    o.add_argument("--platform", required=True)
    o.add_argument("--price", type=float, required=True)
    o.add_argument("--shipping", type=float, default=0.0)
    o.add_argument("--note", default="")
    w = sub.add_parser("watch", help="加入关注清单")
    w.add_argument("key")
    w.add_argument("--target", type=float, default=0.0)
    w.add_argument("--note", default="")
    sub.add_parser("watchlist", help="关注清单")
    u = sub.add_parser("unwatch", help="移出关注清单")
    u.add_argument("key")
    sub.add_parser("stats", help="统计")
    we = sub.add_parser("web", help="启动 Web 界面")
    we.add_argument("--host", default="127.0.0.1")
    we.add_argument("--port", type=int, default=8772)
    return p


def run(args) -> None:
    db = _db(args)
    cfg = llm.config_from_args(args)
    force = args.mock or not cfg.get("api_key")
    cmd = args.cmd

    if cmd == "seed":
        with open(SEED_PATH, encoding="utf-8") as f:
            items = json.load(f)
        n = db.seed(items)
        print(f"· 已导入 {n} 个商品、{db.stats()['offers']} 条报价(内置示例价,非实时)")
    elif cmd == "items":
        rows = db.list_products()
        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2, default=str))
            return
        for r in rows:
            rng = (f"{tools.money(r['low'])}–{tools.money(r['high'])}" if r["offer_count"] else "无报价")
            print(f"[{r['id']}] {r['name']}  {r['specs']}  {r['offer_count']} 家  {rng}")
        if not rows:
            print("还没有商品。python -m huimai seed")
    elif cmd == "show":
        p = _product_or_exit(db, args.key)
        offers = db.list_offers(int(p["id"]))
        print(f"[{p['id']}] {p['name']}  {p['category']}  {p['specs']}")
        if p.get("note"):
            print(f"备注:{p['note']}")
        for o in offers:
            print(f"  {o['platform']:<10} {tools.money(o['price']):>10}  运费 {tools.money(o['shipping'])}"
                  f"  {o.get('note', '')}")
    elif cmd == "compare":
        p = _product_or_exit(db, args.key)
        offers = db.list_offers(int(p["id"]))
        result = agent.compare(p, offers, args.target, cfg, force)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
            return
        if force:
            print(MOCK_BANNER, file=sys.stderr)
        print(render_compare(result))
    elif cmd == "offer":
        p = _product_or_exit(db, args.key)
        db.add_offer(int(p["id"]), args.platform, args.price, args.shipping, args.note)
        print(f"· 已加报价:{args.platform} {tools.money(args.price)}(运费 {tools.money(args.shipping)})")
    elif cmd == "watch":
        p = _product_or_exit(db, args.key)
        db.add_watch(int(p["id"]), args.target, args.note)
        print(f"· 已关注 [{p['id']}] {p['name']}"
              + (f",目标价 {tools.money(args.target)}" if args.target else ""))
    elif cmd == "watchlist":
        rows = db.list_watch()
        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2, default=str))
            return
        for r in rows:
            flag = "  ✓ 到价" if r["hit"] else ""
            print(f"[{r['product_id']}] {r['name']}  现最低 {tools.money(r['best'])}"
                  f"  目标 {tools.money(r['target']) if r['target'] else '未设'}{flag}")
        if not rows:
            print("关注清单是空的。python -m huimai watch 1 --target 600")
    elif cmd == "unwatch":
        p = _product_or_exit(db, args.key)
        print("· 已移出" if db.remove_watch(int(p["id"])) else "· 本来就没关注")
    elif cmd == "stats":
        print(json.dumps(db.stats(), ensure_ascii=False, indent=2))
    elif cmd == "web":
        from .web import serve
        serve(args.host, args.port, args.db, force, cfg)


def hoist_globals(argv: list[str]) -> list[str]:
    takes_value = {"--model", "--base-url", "--api-key", "--db"}
    flags = {"--mock", "--json"}
    head: list[str] = []
    rest: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in flags:
            head.append(a)
            i += 1
        elif a in takes_value and i + 1 < len(argv):
            head.extend(argv[i:i + 2])
            i += 2
        else:
            rest.append(a)
            i += 1
    return head + rest


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        args = build_parser().parse_args(hoist_globals(argv))
        run(args)
        return 0
    except llm.LLMError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1
    finally:
        _close_all()


if __name__ == "__main__":
    raise SystemExit(main())
