"""SQLite 持久层:商品、报价、关注清单。

报价是内置示例数据,不是实时抓取——这一点在 schema 里的 note 字段就写清楚。
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime

DDL = """
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL DEFAULT '',
    specs TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS offers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    platform TEXT NOT NULL,
    price REAL NOT NULL,
    shipping REAL NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL UNIQUE,
    target REAL NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Database:
    def __init__(self, path: str = "data/huimai.db"):
        self.path = path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(DDL)
            self._conn.commit()

    # 商品 ----------------------------------------------------------------
    def add_product(self, name: str, category: str = "", specs: str = "", note: str = "") -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO products (name, category, specs, note, created_at) VALUES (?,?,?,?,?)"
                " ON CONFLICT(name) DO UPDATE SET category=excluded.category, specs=excluded.specs,"
                " note=excluded.note RETURNING id",
                (name, category, specs, note, _now()),
            )
            row = cur.fetchone()
            self._conn.commit()
            return int(row["id"])

    def get_product(self, key) -> dict | None:
        with self._lock:
            if isinstance(key, int) or (isinstance(key, str) and key.isdigit()):
                row = self._conn.execute("SELECT * FROM products WHERE id=?", (int(key),)).fetchone()
            else:
                row = self._conn.execute(
                    "SELECT * FROM products WHERE name LIKE ? ORDER BY id DESC LIMIT 1", (f"%{key}%",)
                ).fetchone()
            return dict(row) if row else None

    def list_products(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM products ORDER BY id").fetchall()
            out = []
            for r in rows:
                d = dict(r)
                offers = [dict(o) for o in self._conn.execute(
                    "SELECT * FROM offers WHERE product_id=?", (r["id"],)).fetchall()]
                d["offers"] = offers
                d["offer_count"] = len(offers)
                if offers:
                    d["low"] = min(o["price"] + o["shipping"] for o in offers)
                    d["high"] = max(o["price"] + o["shipping"] for o in offers)
                else:
                    d["low"] = d["high"] = 0
                out.append(d)
            return out

    # 报价 ----------------------------------------------------------------
    def add_offer(self, product_id: int, platform: str, price: float, shipping: float = 0.0,
                  note: str = "") -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO offers (product_id, platform, price, shipping, note, created_at)"
                " VALUES (?,?,?,?,?,?)",
                (product_id, platform, float(price), float(shipping), note, _now()),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def list_offers(self, product_id: int) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM offers WHERE product_id=? ORDER BY price", (product_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def clear_offers(self, product_id: int) -> int:
        with self._lock:
            cur = self._conn.execute("DELETE FROM offers WHERE product_id=?", (product_id,))
            self._conn.commit()
            return cur.rowcount

    def seed(self, items: list[dict]) -> int:
        """按内置示例数据灌库;同名商品覆盖价格,便于反复导入。"""
        count = 0
        for item in items:
            pid = self.add_product(item["name"], item.get("category", ""),
                                   item.get("specs", ""), item.get("note", ""))
            self.clear_offers(pid)
            for o in item.get("offers", []):
                self.add_offer(pid, o["platform"], float(o["price"]),
                               float(o.get("shipping", 0)), o.get("note", ""))
            count += 1
        return count

    # 关注清单 -------------------------------------------------------------
    def add_watch(self, product_id: int, target: float = 0.0, note: str = "") -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO watchlist (product_id, target, note, created_at) VALUES (?,?,?,?)"
                " ON CONFLICT(product_id) DO UPDATE SET target=excluded.target, note=excluded.note"
                " RETURNING id",
                (product_id, float(target), note, _now()),
            )
            row = cur.fetchone()
            self._conn.commit()
            return int(row["id"])

    def list_watch(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT w.*, p.name, p.specs FROM watchlist w JOIN products p ON p.id=w.product_id"
                " ORDER BY w.id"
            ).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                best = self._conn.execute(
                    "SELECT MIN(price + shipping) AS low FROM offers WHERE product_id=?",
                    (r["product_id"],),
                ).fetchone()
                d["best"] = float(best["low"]) if best and best["low"] is not None else 0.0
                d["hit"] = bool(d["target"]) and d["best"] and d["best"] <= d["target"]
                out.append(d)
            return out

    def remove_watch(self, product_id: int) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM watchlist WHERE product_id=?", (product_id,))
            self._conn.commit()
            return cur.rowcount > 0

    def stats(self) -> dict:
        with self._lock:
            c = self._conn
            return {
                "products": c.execute("SELECT COUNT(*) FROM products").fetchone()[0],
                "offers": c.execute("SELECT COUNT(*) FROM offers").fetchone()[0],
                "watch": c.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0],
            }

    def close(self) -> None:
        with self._lock:
            self._conn.close()
