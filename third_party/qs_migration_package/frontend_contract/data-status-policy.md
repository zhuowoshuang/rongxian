# 数据状态展示策略

## DataStatus 四态说明

| 状态 | 含义 | 前端展示 |
|------|------|----------|
| `OK` | 数据完整，正常使用 | 正常渲染图表、表格、卡片 |
| `PARTIAL` | 部分字段缺失，已尽力补齐 | 正常展示已有数据，缺失字段灰显占位；卡片上方提示"部分数据缺失/延迟行情" |
| `EMPTY` | 数据源无此数据 | 展示空状态占位图，不渲染假数据；财务为 `[]` 时显示"暂无财务数据" |
| `ERROR` | 接口调用失败 | 展示错误态 + 重试按钮 + errorMessage |

## missingFields 处理

- `missingFields` 列出缺失的字段名（camelCase），如 `["realtimeQuote", "name", "industry"]`
- 前端可在数据卡片底部显示："以下字段暂缺：xxx"
- 缺失数值字段统一为 `null`，前端不得将 `null` 渲染为 `0`

## isRealtime 处理

- `isRealtime: true` → 显示"实时行情"
- `isRealtime: false` → 显示"延迟行情（基于最近K线）" + 数据时间

## source 处理

- 每类数据展示其 `source` 标签
- 例：`AData-Kline-Fallback` → 显示"数据来源：AData（K线推算）"
- 例：`adata-realtime` → 显示"数据来源：AData 实时"

## 错误重试

- `ERROR` 状态页面显示"数据加载失败" + `errorMessage`
- 提供"重试"按钮，点击后重新调用 API
- 3 次重试仍失败 → 显示"暂时无法获取数据，请稍后再试"

## 非交易时段

- 行情卡片显示"当前非交易时段"
- 如果触发了 K线 fallback，显示"以下为最近交易日收盘数据"
