# UI 状态映射 — 清数智算个股页面

## 页面数据对应关系

| 页面区域 | 数据来源 | 说明 |
|----------|----------|------|
| 顶部价格卡 | `StockQuote` | 显示 price / change / changePct / open / high / low / preClose |
| 行情走势图 | `StockKline` | K 线蜡烛图，period 控制周期 |
| 财务指标表 | `FinancialMetric[]` | 表格展示 revenue / netProfit / roe / eps 等 |
| 基本信息栏 | `StockSearchItem` | symbol / name / exchange / industry |
| 数据来源提示 | `SourceSummary` | 底部小字：数据来源: xxx |
| 缺失提示 | `missingFields` + `dataStatus` | 非 OK 状态时顶部 banner |

## StockQuote → 价格卡映射

```
┌──────────────────────────────────┐
│  平安银行  000001                │  ← name / symbol
│  ¥ 10.06  -1.76%  -0.18         │  ← price / changePct / change
│  开 10.22  高 10.22              │  ← open / high
│  低 10.04  昨收 10.24            │  ← low / preClose
│  成交量 97.99万  换手 0.35%      │  ← volume / turnoverRate
│  [延迟行情]                      │  ← 当 isRealtime=false
│  [部分字段缺失: industry]        │  ← 当 dataStatus=PARTIAL
└──────────────────────────────────┘
```

## StockKline → K线图映射

- `items[].date` → X 轴日期
- `items[].open/high/low/close` → 蜡烛图
- `items[].volume` → 成交量柱
- `period` → 图表标题后缀（日K/周K/月K）

## FinancialMetric → 财务表映射

| 字段 | 表格列 |
|------|--------|
| period | 报告期 |
| revenue | 营业总收入 |
| revenueYoy | 营收同比(%) |
| netProfit | 归母净利润 |
| profitYoy | 净利同比(%) |
| grossMargin | 毛利率(%) |
| netMargin | 净利率(%) |
| roe | ROE(%) |
| debtRatio | 资产负债率(%) |
| eps | EPS(元) |

## 评分模块（当前为 Demo）

如果清数智算评分模块仍未接入真实评分算法：
- 评分卡片必须标记为"演示评分"
- 不允许把固定值当作真实评分
- score 字段标为 scoreStatus: "DEMO"

## 空状态

- K 线无数据 → 图表区域显示"暂无K线数据"
- 财务无数据 → 表格区域显示"暂无财务数据"
- 行情无数据 → 价格卡显示"--"，标注"非交易时段"
