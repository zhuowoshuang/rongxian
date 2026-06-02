# 融衔 RongXian

<div align="center">

### A股 + 港股智能量化分析平台

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14+-black.svg)](https://nextjs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-blue.svg)](https://www.typescriptlang.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-blue.svg)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue.svg)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

> ⚠️ **免责声明**：本系统仅用于研究和辅助分析，不构成任何投资建议。投资有风险，入市需谨慎。

---

## 系统预览

| 策略总览 | 信号中心 | 股票分析 |
|:--------:|:--------:|:--------:|
| ![策略总览](https://raw.githubusercontent.com/zhuowoshuang/rongxian/main/docs/screenshots/dashboard.png) | ![信号中心](https://raw.githubusercontent.com/zhuowoshuang/rongxian/main/docs/screenshots/signals.png) | ![股票分析](https://raw.githubusercontent.com/zhuowoshuang/rongxian/main/docs/screenshots/stock-detail.png) |

| 股票池 | 回测中心 | 报告中心 |
|:------:|:--------:|:--------:|
| ![股票池](https://raw.githubusercontent.com/zhuowoshuang/rongxian/main/docs/screenshots/pools.png) | ![回测中心](https://raw.githubusercontent.com/zhuowoshuang/rongxian/main/docs/screenshots/backtest.png) | ![报告中心](https://raw.githubusercontent.com/zhuowoshuang/rongxian/main/docs/screenshots/reports.png) |

## 产品定位

这是一个 **金融分析 Agent**，不直接下单，专注于生成：

1. 市场状态判断
2. 中长期基本面选股信号
3. 个股深度分析报告
4. 组合仓位建议
5. 风险预警
6. 策略回测结果
7. 风格化投资策略报告（稳健 / 进取 / 保守）
8. 模拟买入回测

**核心逻辑**：基本面筛选 → 估值判断 → 趋势确认 → 生成报告

## 技术栈

| 层       | 技术                                   |
| -------- | -------------------------------------- |
| 前端     | Next.js 14 + TypeScript + Tailwind CSS |
| 图表     | Recharts                               |
| 后端     | FastAPI + Python 3.11                  |
| 数据库   | PostgreSQL 16 / SQLite（开发）         |
| ORM      | SQLAlchemy 2.0                         |
| 定时任务 | APScheduler                            |
| 数据处理 | Pandas / NumPy                         |
| PDF生成  | xhtml2pdf                              |
| 数据源   | AKShare / Yahoo Finance / 东方财富     |
| 缓存     | Redis（可选）                          |
| 部署     | Docker Compose                         |

## 快速启动

### 方式一：Docker Compose（推荐）

```bash
git clone https://github.com/zhuowoshuang/rongxian.git
cd rongxian
cp .env.example .env
docker-compose up --build
```

- 前端：http://localhost:3000
- 后端 API 文档：http://localhost:8000/docs

### 方式二：本地开发

#### 后端

```bash
cd backend

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt

# 初始化数据库并导入 Mock 数据
python -m app.seed

# 启动后端服务
uvicorn app.main:app --reload --port 8000
```

#### 前端

```bash
cd frontend

npm install
npm run dev

# 访问 http://localhost:3000
```

### 默认账号

| 角色     | 用户名   | 密码   |
| -------- | -------- | ------ |
| 管理员   | admin    | admin  |
| 演示用户 | demo     | demo   |
| 分析师   | analyst  | analyst |

## 功能模块

### 策略总览（仪表盘）

- 市场指数实时概览（上证 / 深证 / 恒生）
- 策略摘要：市场状态、核心策略、建议仓位
- 今日信号 TOP 5 精选
- 信号分布饼图
- 四大股票池快览（优质 / 低估值 / 趋势 / 风险）
- 风险预警提示

### 信号中心

- 按市场（A股 / 港股）、信号类型、评分筛选
- 信号详情：入场价、目标价、止损价
- 信号强度星级展示
- 建议仓位百分比
- 支持分页浏览

### 股票分析

- 行情走势图（近120日 + MA20均线）
- 五维评分雷达图（质量 / 估值 / 成长 / 趋势 / 风险）
- 财务指标表格（营收、利润、ROE、负债率等）
- 信号逻辑解释
- 风险提示
- 券商研报关联（来源：东方财富）

### 股票池

8 种策略股票池：

| 池类型       | 说明           | 筛选条件                          |
| ------------ | -------------- | --------------------------------- |
| 质量优选     | 高质量公司     | quality_score ≥ 22                |
| 估值洼地     | 低估值标的     | valuation_score ≥ 15              |
| 趋势向好     | 技术面强势     | trend_score ≥ 15                  |
| 风险警示     | 高风险标的     | risk_score < 5                    |
| 稳健优选     | 低波动蓝筹     | quality ≥ 20, risk ≥ 6, PE < 60  |
| 进取优选     | 高成长标的     | growth ≥ 15, trend ≥ 15          |
| 保守优选     | 高安全边际     | valuation ≥ 15, quality ≥ 18     |
| 周波动 > 2%  | 近5日活跃标的  | 周振幅 ≥ 2%                       |

### 报告中心

#### 系统报告

- **每日策略报告**：市场综述、信号分布、重点推荐、风险预警、操作建议
- **个股深度分析**：行情、技术面、财务、估值、评分、同业比较

#### 风格化策略报告

| 风格         | 特点                 | 仓位上限 | 适合人群               |
| ------------ | -------------------- | -------- | ---------------------- |
| 🛡️ 稳健型   | 低波动、高股息、蓝筹 | 60%      | 风险厌恶型、退休人群   |
| 🚀 进取型   | 高成长、强趋势       | 90%      | 年轻人、专业投资者     |
| 🏦 保守型   | 低估值、高安全边际   | 40%      | 大资金保守配置         |

#### 其他功能

- 券商研报搜索（来源：东方财富）
- 所有报告支持一键下载 PDF（专业 A4 排版）

### 回测中心

#### 策略回测

- 基于评分的选股策略历史回测
- 权益曲线（策略 vs 沪深300基准）
- 月度超额收益柱状图
- 核心指标：总收益、年化收益、超额收益、最大回撤、夏普比率、胜率

#### 模拟买入

- 输入持仓列表（股票代码 + 买入日期 + 股数）
- 使用真实历史价格计算收益
- 个股盈亏明细
- 组合权益曲线和月度收益对比

### 系统设置

- 股票数据同步（A股 / 港股代码）
- QQ 邮箱 SMTP 推送配置
- 飞书 Webhook 推送配置
- 每日收盘后自动推送信号摘要

### 管理后台

- 系统统计（股票数、信号数、用户数、报告数）
- 用户管理（角色分配、状态管理）
- 数据库表浏览

## 评分模型

总分 100 分，五维评估：

```
total = quality(30) + valuation(20) + growth(20) + trend(20) + risk(10)
```

### 评级规则

| 分数区间 | 评级   | 含义 |
| -------- | ------ | ---- |
| ≥ 85     | BUY    | 买入 |
| 75-84    | ADD    | 加仓 |
| 65-74    | WATCH  | 观察 |
| 50-64    | REDUCE | 减仓 |
| < 50     | SELL   | 卖出 |

### 信号生成规则

- **BUY**：总分 ≥ 85，质量 ≥ 24，估值 ≥ 14，趋势 ≥ 14
- **ADD**：总分 ≥ 75，趋势确认，风险分 ≥ 7
- **WATCH**：基本面好但趋势未确认
- **REDUCE**：估值过高 / 趋势转弱 / 风险升高
- **SELL**：基本面恶化 / 评分极低

## 项目结构

```text
rongxian/
├── backend/                    # Python 后端
│   ├── app/
│   │   ├── api/                # API 路由
│   │   │   ├── dashboard.py    # 仪表盘
│   │   │   ├── stocks.py       # 股票查询
│   │   │   ├── signals.py      # 信号列表
│   │   │   ├── pools.py        # 股票池
│   │   │   ├── reports.py      # 报告生成与下载
│   │   │   ├── backtest.py     # 回测引擎
│   │   │   ├── auth.py         # 认证授权
│   │   │   ├── settings.py     # 系统设置
│   │   │   └── admin.py        # 管理后台
│   │   ├── models/             # SQLAlchemy 数据模型
│   │   ├── schemas/            # Pydantic 请求/响应模式
│   │   ├── services/           # 业务逻辑层
│   │   │   ├── scoring.py      # 五维评分模型
│   │   │   ├── signal.py       # 信号生成引擎
│   │   │   ├── report.py       # 报告生成（含风格化）
│   │   │   ├── backtest.py     # 回测服务
│   │   │   ├── pdf_service.py  # PDF 导出
│   │   │   └── dashboard.py    # 仪表盘聚合
│   │   ├── data_providers/     # 数据源适配器
│   │   ├── core/               # 配置与常量
│   │   ├── db/                 # 数据库连接
│   │   ├── seed.py             # 种子数据
│   │   └── main.py             # FastAPI 入口
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                   # Next.js 前端
│   ├── src/
│   │   ├── app/                # 页面路由
│   │   ├── components/         # React 组件
│   │   ├── lib/                # 工具函数与 API 客户端
│   │   └── types/              # TypeScript 类型定义
│   ├── Dockerfile
│   └── package.json
├── infra/
│   └── init.sql                # 数据库初始化脚本
├── docs/
│   └── screenshots/            # 系统截图
├── docker-compose.yml
├── .env.example
├── LICENSE
└── README.md
```

## API 文档

启动后端后访问 Swagger UI：http://localhost:8000/docs

### 核心接口

| 方法 | 路径                           | 说明                   |
| ---- | ------------------------------ | ---------------------- |
| GET  | `/api/dashboard`               | 仪表盘聚合数据         |
| GET  | `/api/stocks/search?keyword=`  | 搜索股票               |
| GET  | `/api/stocks/{symbol}`         | 股票详情（行情+财务）  |
| GET  | `/api/signals`                 | 信号列表（支持筛选）   |
| GET  | `/api/pools?type=`             | 股票池（8种类型）      |
| GET  | `/api/reports`                 | 报告列表               |
| GET  | `/api/reports/{id}`            | 报告详情               |
| GET  | `/api/reports/{id}/pdf`        | 下载报告 PDF           |
| POST | `/api/reports/generate`        | 生成策略/个股报告      |
| POST | `/api/reports/generate-style`  | 生成风格化策略报告     |
| GET  | `/api/reports/research`        | 券商研报列表           |
| POST | `/api/backtest/run`            | 运行策略回测           |
| POST | `/api/backtest/simulate`       | 模拟买入回测           |

### 认证接口

| 方法 | 路径                 | 说明     |
| ---- | -------------------- | -------- |
| POST | `/api/auth/login`    | 用户登录 |
| POST | `/api/auth/register` | 用户注册 |
| GET  | `/api/auth/me`       | 当前用户 |

## 参与贡献

欢迎贡献代码、报告问题或提出改进建议！

1. Fork 本仓库
2. 创建功能分支：`git checkout -b feature/your-feature`
3. 提交更改：`git commit -m 'feat: add some feature'`
4. 推送分支：`git push origin feature/your-feature`
5. 创建 Pull Request

## 开源协议

本项目采用 [MIT License](LICENSE) 开源。

## 后续规划

- [x] 接入真实数据源（AKShare / Yahoo Finance / 东方财富）
- [x] 完善回测引擎（月度超额收益、模拟买入）
- [x] 风格化投资策略报告（稳健 / 进取 / 保守）
- [x] PDF 报告下载
- [x] 8 种股票池（含风格池和波动池）
- [x] QQ 邮箱 / 飞书 Webhook 推送
- [ ] API 密钥管理（管理员配置，控制所有用户的 API 调用）
- [ ] AI 报告生成（LLM 集成）
- [ ] 多周期回测对比
- [ ] 组合管理（实时持仓跟踪）
- [ ] 移动端适配
