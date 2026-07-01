# 已知限制

## 1. 非交易时段行情

- 实时行情 API 在非交易时段（工作日 15:00 后、周末、节假日）返回空
- **已处理**：qs_backend_bridge 自动用最新 K 线构造延迟行情
- 延迟行情 `isRealtime=false`，`source="AData-Kline-Fallback"`
- 前端需标注"延迟行情"

## 2. 股票名称可能缺失

- AData `all_code()` 当前因百度 API 变更而失败
- **已处理**：stock_name_resolver 按 search → quote → code.csv 顺序补齐
- 三者均无时返回 `name=null`，`missingFields=["name"]`

## 3. 行业字段暂缺

- AData 有申万行业接口（`get_industry_sw`），但当前 adapter 未封装
- searchItem.industry 始终为 `null`
- `missingFields` 中包含 `"industry"`

## 4. 概念板块未接入

- AData 有 `concept_constituent_east` 和 `get_concept_east`
- 本轮迁移层未封装板块数据
- 后续可新增 `qs_adapter/plate_adapter.py`

## 5. 财务数据为核心指标

- 数据来源：东方财富 F10 核心指标
- 包含 EPS、ROE、营收、净利、毛利率等
- **不是**完整三大报表（资产负债表、利润表、现金流量表）
- 如需要完整报表，AData 有 `balance.py`、`profit.py`、`cash_flow.py`

## 6. 无 WebSocket 实时推送

- 所有数据通过 HTTP 请求获取
- 前端需要设置轮询间隔（建议行情 5s、K线 60s、财务 3600s）

## 7. 不构成投资建议

- AData 和本迁移包仅提供行情数据
- 不提供评分、策略、买卖建议
- 清数智算的评分模块如仍为 demo，必须明确标注"演示评分"

## 8. 网络依赖

- 所有数据依赖外部公开 API
- 东方财富、新浪、腾讯等数据源可能限流或变更 API
- 建议后端增加 Redis 缓存层
