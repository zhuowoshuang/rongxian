# AData 迁移包 — 迁移就绪报告

生成时间：2026-06-30 | 版本：1.2.0

## 1. 迁移状态：READY ✅

迁移包的接口契约已冻结，可复制到清数智算项目。

## 2. 机器验收结果

| 验收项 | 结果 | 说明 |
|--------|------|------|
| manifest | PASS | package_manifest.json 结构完整 |
| contract | PASS | OpenAPI/TS/examples 三向一致 |
| importability | PASS | qs_adapter + qs_backend_bridge 可独立导入 |
| status semantics | PASS | 300866→PARTIAL, 999999→EMPTY, abc→ERROR |
| fastapi template | PASS | 5/5 路由 OK |
| no fake data | PASS | 无假数据/随机评分/假行情 |
| live smoke | WARN | 企业代理阻塞 EastMoney API（环境问题） |

## 3. 可以复制的目录

- `python/qs_adapter/` → data adapter
- `python/qs_backend_bridge/` → bridge service
- `frontend_contract/` → TypeScript types
- `target_templates/` → FastAPI + frontend templates
- `openapi/` → API spec
- `docs/` → documentation

## 4. 不应该复制的目录

- `acceptance/` — 验收脚本（AData 端验证用）
- `contract_tests/` — 契约测试（AData 端验证用）
- `integration_demo/` — 临时演示
- `__pycache__/` — 编译缓存

## 5. 接入清数智算的最小步骤

1. 复制 `python/qs_adapter` 和 `python/qs_backend_bridge` 到 backend
2. 安装依赖 `pip install -r requirements-adata.txt`
3. 复制 `adata_stock_routes.py` 到 backend routers 并注册
4. 复制 `stock-data-types.ts` + `adataStockApi.ts` 到前端
5. 前端调用 `getStockDataBundle(symbol)` 替换 demo 数据

## 6. 外部风险

- 东方财富 API 可能被企业代理拦截
- 百度 API 仍在变更中（`all_code()` fallback 已就位）
- 非交易时段实时行情为空（K 线 fallback 已就位）
- 行业字段暂缺
- 无 WebSocket 实时推送

## 7. 声明

该迁移包仅负责 A 股数据接入，不生成正式评分，不构成投资建议。
清数智算评分模块在未接入真实评分算法前，必须标记为"演示评分"。
