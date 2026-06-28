# 清算 — A股港股智能量化分析系统

> 清数智算创新团队出品

一套完整的 A 股 + 港股中长期基本面选股与交易信号系统。从数据采集、量化评分、信号生成、报告撰写到策略回测的**端到端量化投资研究平台**。

**免责声明：本系统仅用于研究和辅助分析，不构成任何投资建议。股市有风险，投资需谨慎。**

---

## 功能特性

| 功能     | 说明                                              |
| -------- | ------------------------------------------------- |
| 五维评分 | 质量(30)+估值(20)+成长(20)+趋势(20)+风险(10)=100分 |
| 交易信号 | BUY/ADD/WATCH/REDUCE/SELL 五级信号                 |
| 股票池   | 8类：优质、低估、趋势、风险、稳健、进取、保守、高波动 |
| 报告引擎 | 每日策略、个股深度、风格化策略报告                  |
| 策略回测 | 含交易成本、滑点、涨跌停限制、月度收益分析          |
| AI 增强  | DeepSeek 大模型生成市场洞察和个股分析              |
| 多数据源 | 东方财富、雪球、Yahoo Finance、AKShare、baostock    |
| 通知推送 | QQ 邮箱 + 飞书 Webhook                            |

## 快速开始

```bash
# Docker Compose
docker-compose up -d

# 本地开发
cd backend && pip install -r requirements.txt && python -m app.seed --force && uvicorn app.main:app --reload
cd frontend && npm install && npm run dev
```

## 技术栈

| 层     | 技术                                      |
| ------ | ----------------------------------------- |
| 后端   | Python 3.11 + FastAPI + SQLAlchemy 2.0    |
| 前端   | Next.js 14 + React 18 + TypeScript        |
| 数据库 | PostgreSQL 16 / SQLite                    |
| 缓存   | Redis 7（可选）                           |
| 图表   | Recharts                                  |
| 部署   | Docker Compose                            |

## 许可证

本系统仅用于研究和辅助分析，不构成任何投资建议。

---

清数智算创新团队 · Built for quantitative research
