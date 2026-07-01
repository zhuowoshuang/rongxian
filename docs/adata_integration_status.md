# AData 接口对齐与 live 收口状态

## 当前接口口径
- 健康检查：`/api/adata/health`
- 搜索：`/api/adata/stocks/search?keyword=300866`
- 个股聚合：`/api/adata/stocks/{symbol}/bundle?period=daily`
- 行情：`/api/adata/stocks/{symbol}/quote`
- K 线：`/api/adata/stocks/{symbol}/kline?period=daily`
- 财务：`/api/adata/stocks/{symbol}/financials`

## 明确约束
- 只保留正式搜索路径 `/api/adata/stocks/search?keyword=`
- `/api/adata/stocks/{symbol}/search` 不是正式路径，验收脚本要求返回 `404`
- `financials` 始终返回数组
- `999999` 必须返回 `EMPTY`
- `abc` 必须返回 `ERROR`
- `ADATA_USE_FIXTURES=true` 仅用于离线验收，返回体必须带 `Fixture-Only`

## live / fixture 区分
- 默认 `ADATA_USE_FIXTURES=false`
- `mode=live` 表示尝试真实链路
- `mode=fixture` 表示离线验收数据
- `networkStatus=NETWORK_WARN` 表示当前环境更像网络或代理阻塞，不计为代码契约失败
- 前端个股页必须展示“离线验收数据 / 非实时行情”提示，不能把 fixture 冒充成 live

## 验收命令
- 后端编译：`cd backend && python -m compileall app`
- AData 单测：`cd backend && $env:PYTHONPATH='.'; python -m pytest tests/test_adata_api.py -q`
- live smoke：`python backend/scripts/smoke_adata_api.py --base-url http://127.0.0.1:8010`
- fixture smoke：`python backend/scripts/smoke_adata_api.py --base-url http://127.0.0.1:8012 --use-fixtures`
- 严格 live：`python backend/scripts/smoke_adata_api.py --base-url http://127.0.0.1:8010 --strict-live`
- 前端构建：`cd frontend && npm run build`

## 页面验收口径
- `/stocks/300866`
  页面可展示 AData 补充区；fixture 模式下必须显示离线验收提示
- `/stocks/999999`
  页面保留原清数智算结构，同时明确空状态
- `/stocks/abc`
  页面保留原结构，同时明确非法代码错误态
- 评分追溯、信号解释、相关报告、数据来源区域必须保留

## 2026-06-30 最终运行态验收结论
- `/api/adata/health` 当前返回 `mode=live`、`fixturesEnabled=false`、`networkStatus=READY`
- 当前机器 `HTTP_PROXY / HTTPS_PROXY / NO_PROXY` 均为 `unset`
- `python backend/scripts/smoke_adata_api.py --base-url http://127.0.0.1:8000 --strict-live` 当前返回 `EXIT:2`
- 当前环境 `300866 strict-live` 仍未 PASS，原因是 live 请求超时，错误为 `AData live request timeout, likely network/proxy blocked`
- 这表示当前代码契约已对齐，但当前机器仍不能对外宣称 “300866 live 已真跑通”
- `python backend/scripts/smoke_adata_api.py --base-url http://127.0.0.1:8001 --use-fixtures` 已 PASS，且 `sourceSummary` 明确包含 `Fixture-Only`
- 生产环境若设置 `APP_ENV=production` 且 `ADATA_USE_FIXTURES=true`，后端会直接抛出 `RuntimeError: 生产环境禁止启用 ADATA_USE_FIXTURES=true`
- `next start` 在当前仓库中文路径下仍存在不稳定风险；最终生产验收使用 ASCII 路径映射 `F:\qs_runtime\frontend`
- `F:\qs_runtime\frontend` 的 `npm run clean && npm run build && npm run start` 已通过，`http://127.0.0.1:4101` 可稳定访问
