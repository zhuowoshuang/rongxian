# 清数智算 — AData 数据接入指南

## 1. 复制迁移包

将 `qs_migration_package/` 整个文件夹复制到清数智算项目根目录下。

## 2. 安装依赖

```bash
# Python 依赖
pip install -r qs_migration_package/python/requirements-adata.txt

# AData 项目（需要先 clone 到本地，然后以可编辑模式安装）
cd /path/to/adata
pip install -e .

# Python 3.12 用户注意
pip install "setuptools>=68"
```

## 3. 验证环境

```bash
# 运行 smoke test
python qs_migration_package/python/qs_backend_bridge/smoke_test.py --symbol 300866
```

预期输出：
- search: OK
- quote: OK（可能触发 fallback）
- kline: items > 1000
- financials: 期数 > 10
- error_example: OK

## 4. 后端集成

在清数智算 backend 中引入：

```python
import sys
sys.path.insert(0, 'qs_migration_package/python')

from qs_backend_bridge import (
    search_stocks,
    get_stock_quote,
    get_stock_kline,
    get_stock_financials,
    get_stock_data_bundle,
)
```

API 路由示例（FastAPI）：

```python
@app.get("/api/adata/stocks/search")
async def api_search_stocks(keyword: str):
    return search_stocks(keyword)

@app.get("/api/adata/stocks/{symbol}/quote")
async def api_stock_quote(symbol: str):
    return get_stock_quote(symbol)

@app.get("/api/adata/stocks/{symbol}/kline")
async def api_stock_kline(symbol: str, period: str = "daily"):
    return get_stock_kline(symbol, period)

@app.get("/api/adata/stocks/{symbol}/financials")
async def api_stock_financials(symbol: str):
    return get_stock_financials(symbol)

@app.get("/api/adata/stocks/{symbol}/bundle")
async def api_stock_bundle(symbol: str, period: str = "daily"):
    return get_stock_data_bundle(symbol, period)
```

## 5. 前端集成

复制 `frontend_contract/` 下的 TypeScript 类型和示例到清数智算前端项目。

```typescript
import { searchStocks, getStockQuote } from '@/api/adata-client';
```

## 6. 环境变量

无需额外环境变量。AData API 直接请求公开数据源，不需要 API Key。
