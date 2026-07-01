# 清数智算 — 股票数据 API 契约

## 通用约定

- 所有接口返回 JSON
- 所有字段使用 camelCase
- 数值缺失时为 `null`，不填 `0`
- 每个响应都包含 `dataStatus`、`missingFields`、`errorMessage`

---

## 1. GET /api/adata/stocks/search?keyword=

**参数**：`keyword` (string) — 股票代码或名称

**返回**：`StockSearchItem[]`

```json
[{
  "symbol": "300866",
  "name": "安克创新",
  "market": "A",
  "exchange": "SZ",
  "industry": null,
  "source": "search_stocks",
  "updateTime": "2026-06-30T15:00:00",
  "dataStatus": "OK",
  "missingFields": [],
  "errorMessage": null
}]
```

---

## 2. GET /api/adata/stocks/:symbol/quote

**参数**：`symbol` (path) — 6位股票代码

**返回**：`StockQuote`

```json
{
  "symbol": "300866",
  "name": "安克创新",
  "price": 104.50,
  "change": -3.62,
  "changePct": -3.35,
  "isRealtime": false,
  "source": "AData-Kline-Fallback",
  "dataStatus": "PARTIAL",
  "missingFields": ["realtimeQuote"]
}
```

---

## 3. GET /api/adata/stocks/:symbol/kline?period=daily

**参数**：
- `symbol` (path)
- `period` (query) — `daily` / `weekly` / `monthly`

**返回**：`StockKline`

```json
{
  "symbol": "300866",
  "period": "daily",
  "items": [
    { "date": "2026-06-30", "open": 108.12, "close": 104.50, ... }
  ],
  "dataStatus": "OK"
}
```

---

## 4. GET /api/adata/stocks/:symbol/financials

**返回**：`FinancialMetric[]`

```json
[{
  "period": "2026-03-31",
  "revenue": 6123456789.00,
  "netProfit": 471594189.71,
  "roe": 4.35,
  "eps": 0.88,
  "dataStatus": "OK"
}]
```

---

## 5. GET /api/adata/stocks/:symbol/bundle?period=daily

**返回**：`StockDataBundle`（包含以上全部）

```json
{
  "symbol": "300866",
  "searchItem": { ... },
  "quote": { ... },
  "kline": { ... },
  "financials": [ ... ],
  "sourceSummary": {
    "quoteSource": "AData-Kline-Fallback",
    "klineSource": "adata",
    "financialsSource": "adata-eastmoney",
    "searchSource": "code-csv"
  },
  "dataStatus": "PARTIAL",
  "missingFields": ["quote"],
  "errorMessage": null
}
```

---

## 错误响应

当接口完全不可用时返回：

```json
{
  "symbol": "999999",
  "dataStatus": "ERROR",
  "missingFields": ["searchItem", "quote", "kline", "financials"],
  "errorMessage": "无法获取任何数据"
}
```
