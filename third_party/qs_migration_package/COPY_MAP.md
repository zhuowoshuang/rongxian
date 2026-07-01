# 复制映射 — 迁移到清数智算

## 需要复制的目录

| 源路径 (qs_migration_package/) | 目标路径 (清数智算项目/) | 说明 |
|------|------|------|
| `python/qs_adapter/` | `backend/app/integrations/adata/qs_adapter/` | 数据适配层 |
| `python/qs_backend_bridge/` | `backend/app/integrations/adata/qs_backend_bridge/` | 桥接服务层 |
| `python/pyproject.toml` | `backend/app/integrations/adata/pyproject.toml` | 可选：pip install |
| `python/requirements-adata.txt` | `backend/app/integrations/adata/requirements-adata.txt` | 依赖 |
| `frontend_contract/stock-data-types.ts` | `frontend/src/types/stockData.ts` | TypeScript 类型 |
| `frontend_contract/stock-data-client.example.ts` | `frontend/src/services/adataStockApi.ts` | API 客户端（参考） |
| `openapi/qs_adata_api.openapi.json` | `docs/openapi/adata/qs_adata_api.openapi.json` | API 文档 |
| `docs/integration-guide.md` | `docs/adata_migration/integration-guide.md` | 接入文档 |
| `docs/api-contract.md` | `docs/adata_migration/api-contract.md` | API 契约 |
| `docs/known-limitations.md` | `docs/adata_migration/known-limitations.md` | 已知限制 |
| `target_templates/fastapi/adata_stock_routes.py` | `backend/app/routers/adata_stock_routes.py` | FastAPI 路由 |
| `target_templates/frontend/StockDataStateView.example.tsx` | `frontend/src/components/StockDataStateView.tsx` | 四态渲染参考 |

## 不应该复制的内容

| 路径 | 原因 |
|------|------|
| `__pycache__/` | 编译缓存 |
| `*.pyc` | 编译缓存 |
| `web/` | AData 前端页面（不需要） |
| `acceptance/` | 验收脚本（仅在 AData 端使用） |
| `contract_tests/` | 契约测试（仅在 AData 端使用） |
| `examples/` | 样例数据（仅供参考） |
| `integration_demo/` | 临时集成演示 |
| `tests/` | AData 测试 |
| `*test*.py` | 测试文件（除 smoke_test） |
