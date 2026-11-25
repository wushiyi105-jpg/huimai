"""惠买离线单测:不联网、不花 token。"""

from __future__ import annotations

import io
import json
import os
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from huimai import agent, cli, mock, tools, web
from huimai.db import Database

ROOT = os.path.dirname(os.path.dirname(__file__))
ITEMS = json.load(open(os.path.join(ROOT, "data", "products-sample.json"), encoding="utf-8"))


class BaseCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Database(os.path.join(self.tmp.name, "t.db"))
        self.db.seed(ITEMS)
        self.pid = self.db.get_product("耳机")["id"]
        self.offers = self.db.list_offers(self.pid)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()


class TestTools(unittest.TestCase):
    def test_money(self):
        self.assertEqual(tools.money(879), "¥879")
        self.assertEqual(tools.money(12.5), "¥12.50")

    def test_stats(self):
        st = tools.stats([{"platform": "a", "price": 100, "shipping": 0},
                          {"platform": "b", "price": 120, "shipping": 10},
                          {"platform": "c", "price": 90, "shipping": 20}])
        self.assertEqual(st["min"], 100)
        self.assertEqual(st["max"], 130)
        self.assertEqual(st["best"]["platform"], "a")

    def test_units_multiplication(self):
        qty, unit = tools.units("3 包 × 60 片")
        self.assertEqual((qty, unit), (180, "包"))

    def test_unit_price(self):
        up = tools.unit_price("500g", 128)
        self.assertEqual(up["unit"], "g")
        self.assertAlmostEqual(up["value"], 0.256, places=3)

    def test_outliers(self):
        offers = [{"platform": "a", "price": 900, "shipping": 0},
                  {"platform": "b", "price": 880, "shipping": 10},
                  {"platform": "c", "price": 450, "shipping": 0}]
        out = tools.outliers(offers)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["platform"], "c")

    def test_flags_note(self):
        f = tools.flags({"platform": "x", "price": 100, "shipping": 0, "note": "临期,无票"}, [])
        self.assertTrue(any("临期" in i for i in f))

    def test_verdict_target(self):
        st = tools.stats([{"platform": "a", "price": 600, "shipping": 0},
                          {"platform": "b", "price": 620, "shipping": 0}])
        self.assertEqual(tools.verdict(st, [], 600), "值得买")

    def test_new_numbers(self):
        self.assertEqual(tools.new_numbers("899 元", "899 元,便宜 450 元"), ["450"])


class TestDb(BaseCase):
    def test_seed_and_list(self):
        st = self.db.stats()
        self.assertEqual(st["products"], 4)
        self.assertEqual(st["offers"], 13)
        first = self.db.list_products()[0]
        self.assertEqual(first["low"], 449)

    def test_add_offer_and_clear(self):
        self.db.add_offer(self.pid, "测试店", 700, 5)
        self.assertEqual(len(self.db.list_offers(self.pid)), 5)
        self.db.clear_offers(self.pid)
        self.assertEqual(self.db.list_offers(self.pid), [])

    def test_watch_hit(self):
        self.db.add_watch(self.pid, 500)
        w = self.db.list_watch()[0]
        self.assertTrue(w["hit"])
        self.assertEqual(w["best"], 449)

    def test_watch_update_unique(self):
        self.db.add_watch(self.pid, 400)
        self.db.add_watch(self.pid, 450)
        self.assertEqual(len(self.db.list_watch()), 1)
        self.assertEqual(self.db.list_watch()[0]["target"], 450)

    def test_remove_watch(self):
        self.db.add_watch(self.pid, 0)
        self.assertTrue(self.db.remove_watch(self.pid))
        self.assertFalse(self.db.remove_watch(self.pid))


class TestOffline(BaseCase):
    def test_compare_suggests_channel_switch(self):
        p = self.db.get_product(self.pid)
        r = mock.compare(p, self.offers)
        self.assertEqual(r["verdict"], "换渠道")
        self.assertTrue(r["risks"])
        self.assertIn("离线模式", r["note"])

    def test_compare_no_offers(self):
        r = mock.compare({"name": "空商品", "specs": ""}, [])
        self.assertEqual(r["verdict"], "没报价")

    def test_agent_compare_offline(self):
        p = self.db.get_product(self.pid)
        r = agent.compare(p, self.offers, 500, {"api_key": ""}, True)
        self.assertTrue(r["offline"])
        self.assertTrue(r["advice"])


class TestVerify(BaseCase):
    def test_bad_platform_replaced(self):
        p = self.db.get_product(self.pid)
        body, problems = agent.verify_compare(p, self.offers, {
            "verdict": "乱写", "best_platform": "某不存在平台", "reasons": ["京东 899 元含保修"],
            "risks": ["拼多多 449 元低得反常"], "advice": ["先确认是否官方店"],
        })
        self.assertIn(body["best_platform"], [o["platform"] for o in self.offers])
        self.assertEqual(body["verdict"], "换渠道")
        self.assertTrue(problems)

    def test_invented_number_dropped(self):
        p = self.db.get_product(self.pid)
        body, problems = agent.verify_compare(p, self.offers, {
            "verdict": "值得买", "best_platform": "京东自营",
            "reasons": ["比京东便宜 500 元", "天猫 879 元"],
            "risks": [], "advice": ["付款前确认发票"],
        })
        self.assertEqual(body["reasons"], ["天猫 879 元"])
        self.assertTrue(any("500" in p for p in problems))


class TestCli(BaseCase):
    def _run(self, argv, db_path):
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.main(["--db", db_path] + argv)
        return buf.getvalue()

    def test_seed_items_compare_watch(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db_path = os.path.join(tmp.name, "c.db")
        self.assertIn("已导入 4 个商品", self._run(["seed"], db_path))
        items = self._run(["items"], db_path)
        self.assertIn("耳机", items)
        out = self._run(["compare", "1", "--mock"], db_path)
        self.assertIn("结论", out)
        self.assertIn("换渠道", out)
        self._run(["watch", "1", "--target", "500"], db_path)
        self.assertIn("到价", self._run(["watchlist"], db_path))
        self.assertIn("已加报价", self._run(["offer", "1", "--platform", "测试店", "--price", "700"], db_path))
        self.assertIn("已移出", self._run(["unwatch", "1"], db_path))
        tmp.cleanup()


class TestWeb(BaseCase):
    def test_api_compare_and_watch(self):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), web._make_handler(self.db, {"api_key": ""}, True))
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        try:
            with urlopen(base + "/api/items", timeout=15) as resp:
                self.assertEqual(len(json.loads(resp.read().decode("utf-8"))), 4)
            body = json.dumps({"product_id": 0}).encode("utf-8")
            req = Request(base + "/api/compare", data=body, headers={"Content-Type": "application/json"},
                          method="POST")
            with self.assertRaises(HTTPError) as ctx:
                urlopen(req, timeout=15)
            self.assertEqual(ctx.exception.code, 400)
            body = json.dumps({"product_id": self.pid, "target": 500}).encode("utf-8")
            req = Request(base + "/api/compare", data=body, headers={"Content-Type": "application/json"},
                          method="POST")
            with urlopen(req, timeout=20) as resp:
                r = json.loads(resp.read().decode("utf-8"))
            self.assertIn("换渠道", r["text"])
            wreq = Request(base + "/api/watch", data=json.dumps({"product_id": self.pid, "target": 500}).encode("utf-8"),
                           headers={"Content-Type": "application/json"}, method="POST")
            with urlopen(wreq, timeout=15) as resp:
                self.assertTrue(json.loads(resp.read().decode("utf-8"))["id"])
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()
