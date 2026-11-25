# Huimai 惠买

[![test](https://github.com/wushiyi105-jpg/huimai/workflows/test/badge.svg)](https://github.com/wushiyi105-jpg/huimai/actions)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![codecov](https://codecov.io/gh/wushiyi105-jpg/huimai/branch/main/graph/badge.svg)](https://codecov.io/gh/wushiyi105-jpg/huimai)

![usage](assets/demo.gif)

Pick a product and lay its offers from several channels side by side: landed price, unit price, which one is suspiciously low, whether to buy now — and put the one you want to wait for on a watchlist.

The hard part of price comparison is not scraping prices, it is the **landed price**. 879 with 12 shipping versus 899 with free shipping differs by eight yuan; 449 from a non-official seller without an invoice differs not in money but in after-sales support. Huimai adds shipping in, flags outliers, and gives a rule-based verdict — it never claims to authenticate goods, only tells you what to verify.

## Features

- **Landed-price sorting**: `price + shipping` is the comparable number; min, max, median and spread are computed locally.
- **Unit price**: estimates total quantity from specs (`3 包 × 60 片` → 180) and converts to price per piece or per 100g, so bulk packs cannot fake being cheaper.
- **Outlier flagging**: offers below 60% of the median landed price are listed separately, but not automatically declared fake — it could be a genuine subsidy or a trap.
- **Channel risk**: notes containing 临期 / 无票 / 非官方 / 二手 / 代购 / 清仓 raise a flag, and price risk is kept distinct from after-sales risk.
- **The model explains, never computes**: verdict (`值得买 / 再等等 / 换渠道 / 别买 / 没报价`), recommended channel, reasons and advice are model-written; but the channel must exist in the offer table and every number must come from the offers or local stats, otherwise the line is dropped.
- **Recommendation is shown apart from the lowest price**: the cheapest channel is often the most uncertain one, so "lowest landed" and "recommended" are listed separately.
- **Watchlist**: set a target price, and reaching it is marked; reaching it is a hint, not a purchase order.
- **Offline mode**: prices and stats still work, verdicts come from rules, with an explicit note that no authenticity check was made.
- **Two entry points**: CLI and web.

## Quick start

```bash
git clone https://github.com/wushiyi105-jpg/huimai.git
cd huimai
python -m huimai seed          # load built-in sample offers (4 products, 13 offers)
python -m huimai items
python -m huimai compare 1 --target 600
python -m huimai watch 1 --target 600
python -m huimai watchlist
```

With a model:

```bash
cp .env.example .env
# set LLM_API_KEY; defaults are https://api.deepseek.com + deepseek-flash
```

```bash
LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4 LLM_MODEL=glm-4.6 python -m huimai compare 1
```

Web UI:

```bash
python -m huimai web --port 8772
# http://127.0.0.1:8772
```

All offers live in `data/products-sample.json` as fixed sample prices; no e-commerce API is involved.

Run in Docker (the container uses the default port 8772):

```bash
docker build -t huimai .
docker run -p 8772:8772 huimai
```

## Command reference

| Command | What it does |
| --- | --- |
| `seed` | Load built-in sample offers (same name overwrites) |
| `items` | Product list with lowest–highest landed price |
| `show <id\|name>` | Product detail and per-channel offers |
| `compare <id\|name> [--target N]` | Prices, risks, verdict |
| `offer <id\|name> --platform --price [--shipping] [--note]` | Add one offer manually |
| `watch <id\|name> [--target N]` | Add to watchlist |
| `watchlist` / `unwatch <id\|name>` | List / remove |
| `stats` / `web` | Stats / web |

Global flags: `--mock`, `--json`, `--model`, `--base-url`, `--api-key`, `--db`.

## 🤔 Why not just ask a general LLM

A general model can say "that is a good price". Huimai adds the three things it cannot:

1. **Landed price is computed locally** — item price plus shipping is the real cost, unit price is derived from packs such as "3 packs × 60 tablets", and median, spread and outlier prices are all calculated, so shipping is never forgotten and a quote at sixty percent of the median gets noticed.
2. **Cheap needs a reason** — outlier prices are flagged with channel risks: near expiry, no invoice, not an official store, slow shipping. The verdict stays inside a fixed set (buy / wait / switch channel / do not buy / no quote) instead of hedging prose.
3. **The watch list stays local** — quotes and the watch list live in local SQLite; quotes are built-in or entered by hand, no e-commerce API is called, and nothing is ordered for you.
4. **Works offline** — comparison, unit price and outlier checks are local rules and run without a key; the model only phrases the conclusion more smoothly.

## 🎯 Use cases

- **Comparing before a big purchase**: enter the price and shipping of the same earphones on four platforms, sort by landed price, then ask why the cheapest is cheap.
- **Seeing a suspiciously low price**: when one seller is half the others, the outlier flag points at near-expiry or unofficial channels, so you decide whether the saving is worth the risk.
- **Tracking one item**: add it to the watch list and compare again when new quotes arrive, instead of reopening pages.

## 🗺 Roadmap

- **Faster quote entry**: paste several quotes at once and split them into channel, price and shipping.
- **Price history**: repeated comparisons as a curve, to tell a real drop from a rise-then-fall.
- **Coupons and tax in the landed price**: include discounts and tax, not just the sticker price.
- **Price-drop alert**: notify once when a watched item falls below your target.
- **Comparison export**: write one comparison to a Markdown table for whoever is buying with you.

## ❓ FAQ

**Where do I get an API key?**
Comparison needs no key; only smoother wording uses a model. It defaults to DeepSeek (`https://api.deepseek.com`) via `LLM_API_KEY`.

**Where is data stored, and does it scrape marketplaces?**
It does not scrape. Quotes are built in or entered by hand and stored in local SQLite; a model call sends this quote set, not your whole watch list.

**Does it work without a key?**
Yes. `compare` is local arithmetic: landed price, unit price, outlier flags and the verdict all come out; only the phrasing is less polished.

**How do I switch models?**
Change `LLM_BASE_URL`, `LLM_MODEL` and `LLM_API_KEY`, or override with `--model`.

**Why is the cheapest seller not recommended?**
Because it was flagged as an outlier (near expiry, no invoice, unofficial). The verdict becomes "switch channel" and recommends the next-cheapest safe seller instead of letting you save a few yuan and regret it.

## How it works

```mermaid
flowchart TD
    CLI["cli.py<br/>argparse subcommands"] --> AGENT
    WEB["web.py<br/>ThreadingHTTPServer + single page"] --> AGENT
    AGENT["agent.py<br/>verdict checks / channel and number checks"] -->|with key| LLM["llm.py<br/>urllib to /chat/completions"]
    AGENT -->|no key or --mock| MOCK["mock.py<br/>stats + rule verdict"]
    AGENT --> TOOLS["tools.py<br/>stats / unit_price / outliers / flags"]
    TOOLS --> DB["db.py<br/>products / offers / watchlist"]
```

Three trade-offs:

1. **Landed price is the only price.** Comparing list prices erases the difference between free and paid shipping; `stats` always sorts by `price + shipping`, so the "lowest" it reports is what you would actually pay.
2. **No authenticity claims.** This project has no channel licence data, serial number or invoice verification, so saying "this is fake" would be fabrication. It does only what it can: flag prices that are abnormally low and notes that mention 临期 / 无票 / 二手, leaving verification to you.
3. **Recommended is not the cheapest.** The cheapest offer is often the least certain; when the verdict is "switch channel" and the model's pick is itself an outlier, it is replaced by the next cheapest safe channel, and the output states what changed and why.

One SQLite file with `check_same_thread=False` + `threading.Lock`, default `data/huimai.db`, overridable via `HUIMAI_DB`.

## Layout

```
huimai/
├── huimai/
│   ├── __init__.py / __main__.py
│   ├── llm.py     # OpenAI-compatible client + .env loader
│   ├── db.py      # products / offers / watchlist
│   ├── tools.py   # price stats, unit price, outliers, channel risk
│   ├── mock.py    # offline stats and rule verdict
│   ├── agent.py   # verdict checks, channel and number checks
│   ├── cli.py     # command line
│   └── web.py     # web UI
├── data/products-sample.json
├── tests/test_huimai.py
├── assets/demo.gif
├── .github/workflows/test.yml
├── pyproject.toml
├── README.md / README.en.md
└── CHANGELOG.md / SECURITY.md / CODE_OF_CONDUCT.md / CONTRIBUTING.md
```

## Author

shiyi · GitHub [@wushiyi105-jpg](https://github.com/wushiyi105-jpg) · wushiyi105@gmail.com

MIT License, Copyright (c) 2026 wushiyi105-jpg
