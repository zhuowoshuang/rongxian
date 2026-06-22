# 融衔 — A股港股智能量化分析系统

> **融**者，通也；**衔**者，接也。融通数据，衔接策略。

一套完整的 A 股 + 港股中长期基本面选股与交易信号系统。不是简单的数据展示面板，而是一套从数据采集、量化评分、信号生成、报告撰写到策略回测的**端到端量化投资研究平台**。

**免责声明：本系统仅用于研究和辅助分析，不构成任何投资建议。股市有风险，投资需谨慎。**

---

## 目录

- [系统能做什么](#系统能做什么)
- [技术栈](#技术栈)
- [快速开始](#快速开始)
  - [Docker Compose 部署（推荐）](#docker-compose-部署推荐)
  - [本地开发环境](#本地开发环境)
  - [环境变量说明](#环境变量说明)
- [核心模型详解](#核心模型详解)
  - [五维评分模型](#五维评分模型)
  - [信号生成逻辑](#信号生成逻辑)
  - [股票池机制](#股票池机制)
  - [报告引擎](#报告引擎)
  - [回测引擎](#回测引擎)
- [数据源架构](#数据源架构)
- [项目结构](#项目结构)
- [API 接口文档](#api-接口文档)
- [前端架构](#前端架构)
- [安全机制](#安全机制)
- [部署指南](#部署指南)
- [开发指南](#开发指南)
- [测试](#测试)
- [已知限制与路线图](#已知限制与路线图)
- [许可证](#许可证)

---

## 系统能做什么

### 核心功能一览

| 功能 | 说明 |
|------|------|
| **五维评分** | 对每只股票从质量（30分）、估值（20分）、成长（20分）、趋势（20分）、风险（10分）五个维度打分，总分 100 分 |
| **交易信号** | 根据评分自动生成 BUY / ADD / WATCH / REDUCE / SELL 五级信号，每个信号附带入场价、目标价、止损价、建议仓位 |
| **8 类股票池** | 优质股、低估股、趋势股、高风险股、稳健型、进取型、保守型、高波动型 |
| **专业报告** | 每日策略报告（8000+字）、个股深度分析报告、三种风格化策略报告（稳健/进取/保守） |
| **策略回测** | 基于真实历史数据的策略回测，含交易成本（佣金+印花税+过户费+滑点）、涨跌停限制、月度收益分析 |
| **组合模拟** | 输入持仓明细，模拟历史表现，与基准对比 |
| **研报聚合** | 自动从东方财富采集券商研报，按股票关联展示 |
| **AI 增强** | 接入 DeepSeek 大模型生成市场洞察、个股分析、风格策略分析 |
| **多数据源** | 东方财富、雪球、Yahoo Finance、AKShare、baostock 五大数据源智能路由 |
| **定时任务** | 每个交易日 15:30 自动刷新数据、同步研报、推送通知 |
| **通知推送** | QQ 邮箱 + 飞书 Webhook 每日推送信号和报告 |
| **管理后台** | 用户/股票/评分/信号/数据库/API 配置全方位管理 |
| **中英双语** | 前端完整 i18n 支持，500+ 翻译 key |
| **深浅主题** | 深色（默认）+ 浅色主题，CSS 变量驱动 |

---

## 技术栈

### 后端

| 组件 | 技术 | 版本 | 用途 |
|------|------|------|------|
| Web 框架 | FastAPI | >=0.115 | 异步 API、自动 OpenAPI 文档 |
| ORM | SQLAlchemy | >=2.0 | 数据库模型、查询构建 |
| 数据库 | PostgreSQL | 16 | 生产环境（Docker） |
| 数据库 | SQLite | - | 本地开发（零配置） |
| 缓存 | Redis | 7 | 速率限制、仪表盘缓存（可选，支持内存回退） |
| 迁移 | Alembic | >=1.13 | 数据库 schema 迁移 |
| 任务调度 | APScheduler | >=3.10 | 定时数据刷新和通知 |
| 数据采集 | AKShare / baostock / yfinance | - | A股+港股行情、财务、研报 |
| HTTP 客户端 | requests | >=2.31 | 连接池 + 自动重试 + 国内代理绕过 |
| PDF 生成 | xhtml2pdf | >=0.2 | Markdown → PDF 报告导出 |
| AI | DeepSeek API | - | 市场洞察、个股分析 |
| 认证 | python-jose + bcrypt | - | JWT Token + 密码哈希 |

### 前端

| 组件 | 技术 | 版本 | 用途 |
|------|------|------|------|
| 框架 | Next.js (App Router) | 14.2 | SSR/SSG、API 代理、文件路由 |
| UI 库 | React | 18.3 | 组件化 UI |
| 语言 | TypeScript | 5.x | 类型安全 |
| 样式 | Tailwind CSS | 3.4 | 原子化 CSS、深浅主题 |
| 图表 | Recharts | 2.12 | 折线图、柱状图、饼图、雷达图 |
| 图标 | lucide-react | 0.44 | 300+ SVG 图标 |
| Markdown | react-markdown + remark-gfm | 9.0 | GFM 表格、任务列表、删除线 |
| 字体 | JetBrains Mono (next/font) | 5.2 | 数字等宽显示 |

### 基础设施

| 组件 | 说明 |
|------|------|
| Docker Compose | 一键启动 PostgreSQL + Redis + Backend + Frontend |
| GitHub Actions | CI：后端 pytest + 前端 tsc --noEmit + npm build |
| Alembic | 数据库迁移管理 |

---

## 快速开始

### Docker Compose 部署（推荐）

这是最简单的方式，一条命令启动所有服务，适合快速体验和生产部署。

```bash
# 1. 克隆仓库
git clone https://github.com/zhuowoshuang/rongxian.git
cd rongxian

# 2.（可选）设置 JWT 密钥，不设置则自动生成
export JWT_SECRET_KEY="your-super-secret-key-at-least-32-chars"

# 3. 启动所有服务
docker-compose up -d

# 4. 等待服务启动（首次需要下载镜像和安装依赖，约 2-5 分钟）
# 后端会自动运行 seed 脚本导入模拟数据

# 5. 访问
# 前端界面:  http://localhost:3000
# 后端 API:  http://localhost:8000
# API 文档:  http://localhost:8000/docs (Swagger UI)
# API 文档:  http://localhost:8000/redoc (ReDoc)
# 健康检查:  http://localhost:8000/api/health
```

**Docker Compose 启动的服务：**

| 服务 | 端口 | 说明 |
|------|------|------|
| `db` | 5432 | PostgreSQL 16 数据库 |
| `redis` | 6379 | Redis 7 缓存（可选） |
| `backend` | 8000 | FastAPI 后端 |
| `frontend` | 3000 | Next.js 前端 |

**默认账号（模拟数据模式）：**

| 用户名 | 密码 | 角色 |
|--------|------|------|
| `admin` | `admin123` | 管理员 |
| `demo` | `demo123` | 普通用户 |
| `analyst` | `analyst123` | 分析师 |
| `guest` | `guest123` | 访客（只读） |

> 注意：默认密码仅用于开发环境，生产环境务必修改或禁用。

### 本地开发环境

如果你不想用 Docker，或者需要调试代码，可以本地启动。

#### 后端

```bash
cd backend

# 1. 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 2. 安装依赖
pip install -r requirements.txt

# 3. 创建 .env 文件（可选，已有默认值）
cat > .env << EOF
DATABASE_URL=sqlite:///./stock_agent.db
DEBUG=true
MOCK_DATA=true
EOF

# 4. 导入模拟数据（约 500 只 A 股 + 港股，含行情/财务/评分/信号）
python -m app.seed --force

# 5. 启动开发服务器（自动重载）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 前端

```bash
cd frontend

# 1. 安装依赖
npm install

# 2. 创建环境变量文件
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local

# 3. 启动开发服务器
npm run dev
# 访问 http://localhost:3000
```

#### 运行测试

```bash
# 后端测试
cd backend
pytest tests/ -v

# 前端类型检查
cd frontend
npx tsc --noEmit
```

### 环境变量说明

#### 后端环境变量（`backend/.env`）

| 变量 | 必填 | 说明 | 默认值 |
|------|------|------|--------|
| `DATABASE_URL` | 否 | 数据库连接串 | `sqlite:///./stock_agent.db` |
| `REDIS_URL` | 否 | Redis 连接串（不设置则使用内存回退） | `None` |
| `JWT_SECRET_KEY` | 生产必填 | JWT 签名密钥（至少 32 字符） | 自动生成并持久化到 `.jwt_secret` |
| `MOCK_DATA` | 否 | 是否使用模拟数据（`true`/`false`） | `true` |
| `DEBUG` | 否 | 调试模式 | `true` |
| `TUSHARE_TOKEN` | 否 | Tushare API Token（当前未使用） | `None` |
| `FUTU_ACCESS_TOKEN` | 否 | 富途 API Token（当前未使用） | `None` |

#### 前端环境变量（`frontend/.env.local`）

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `NEXT_PUBLIC_API_URL` | 后端 API 地址 | `http://localhost:8000` |

---

## 核心模型详解

### 五维评分模型

评分系统是整个系统的核心，每只股票被从五个维度量化打分：

```
总分 = 质量(30) + 估值(20) + 成长(20) + 趋势(20) + 风险(10) = 100 分
```

#### 质量评分（满分 30 分）

考察公司的基本面质量，包括：

| 子项 | 满分 | 说明 |
|------|------|------|
| ROE | 10 | 净资产收益率，行业内百分位排名（前 20% 满分） |
| 毛利率 | 6 | 行业内百分位排名 |
| 净利率 | 4 | 绝对阈值：>20% 满分 |
| 资产负债率 | 4 | 反向指标，行业内百分位排名（低者优） |
| 经营现金流 | 6 | 正/负二分法（有则满分，无则零分） |

#### 估值评分（满分 20 分）

考察当前价格是否合理：

| 子项 | 满分 | 说明 |
|------|------|------|
| PE 市盈率 | 8 | 行业内百分位排名（低者优） |
| PB 市净率 | 6 | 行业内百分位排名（低者优） |
| 股息率 | 6 | 行业内百分位排名（高者优） |

#### 成长评分（满分 20 分）

考察公司的增长动能：

| 子项 | 满分 | 说明 |
|------|------|------|
| 营收同比增长 | 10 | >20% 满分，<0% 零分 |
| 净利润同比增长 | 10 | >20% 满分，<0% 零分 |

#### 趋势评分（满分 20 分）

考察技术面趋势：

| 子项 | 满分 | 说明 |
|------|------|------|
| MA20 方向 | 4 | 价格在 MA20 上方 |
| MA60 方向 | 6 | 价格在 MA60 上方 |
| MACD 金叉 | 4 | DIF > DEA |
| RSI14 适中 | 3 | 40-70 区间满分 |
| 布林带位置 | 3 | 价格在中轨上方 |

#### 风险评分（满分 10 分）

考察风险因素：

| 子项 | 满分 | 说明 |
|------|------|------|
| 波动率 | 5 | 60 日年化波动率，行业内百分位排名（低者优） |
| 负债率风险 | 3 | 资产负债率绝对值 |
| PE 极端值 | 2 | PE 是否在合理范围 |

#### 评级映射

| 总分区间 | 评级 | 含义 |
|----------|------|------|
| 85-100 | BUY | 强烈买入 |
| 70-84 | ADD | 建议加仓 |
| 55-69 | WATCH | 观望等待 |
| 40-54 | REDUCE | 建议减仓 |
| 0-39 | SELL | 建议卖出 |

#### 行业内百分位排名

评分系统不是使用全市场统一阈值，而是**按行业分组计算百分位排名**。例如，银行股的 ROE 中位数可能是 10%，而科技股可能是 20%。一只 ROE 15% 的银行股在银行行业内排名靠前（高分），但同样的 15% 在科技行业内排名靠后（低分）。

行业百分位覆盖的指标：PE、PB、股息率、ROE、毛利率、资产负债率、波动率。

### 信号生成逻辑

信号是评分的下游应用，将分数转化为可操作的交易建议。

#### 信号类型判定

```
BUY:   总分 >= 85 且 质量 >= 24 且 估值 >= 14 且 趋势 >= 14
ADD:   总分 >= 75 且 趋势 >= 12 且 风险 >= 7
WATCH: 总分 >= 65
REDUCE: 总分 >= 50
SELL:  总分 < 50
```

#### 目标价和止损价（波动率自适应）

系统不是对所有股票使用固定的目标/止损比例，而是**根据布林带宽度估算波动率，动态调整**：

```
波动率 = (布林上轨 - 布林下轨) / 当前价格
目标价 = 入场价 × (1 + 2 × 波动率)，限制在 +10% ~ +30%
止损价 = 入场价 × (1 - 波动率)，限制在 -5% ~ -12%
```

这意味着：
- 低波动股票（如银行股）：目标约 +12%，止损约 -6%
- 高波动股票（如科技股）：目标约 +25%，止损约 -10%

#### 仓位管理

建议仓位考虑两个集中度限制：
- **行业集中度**：同行业已持仓超过 25% 时，新信号仓位减半
- **总仓位**：总仓位超过 85% 时，新信号仓位减半

#### 信号输出

每个信号包含：
- `signal_type`: BUY / ADD / WATCH / REDUCE / SELL
- `signal_strength`: 1-5（强度）
- `suggested_position`: 建议仓位百分比
- `entry_price`: 入场价（当日收盘价）
- `target_price`: 目标价（波动率自适应）
- `stop_loss_price`: 止损价（波动率自适应）
- `holding_period`: 建议持有期
- `logic_json`: 信号逻辑说明（JSON）
- `risk_json`: 风险提示（JSON）

### 股票池机制

系统维护 8 类股票池，每类有不同的筛选逻辑：

| 股票池 | 筛选逻辑 |
|--------|----------|
| 优质股 | 质量评分 >= 24（满分 30 的 80%） |
| 低估股 | 估值评分 >= 16（满分 20 的 80%） |
| 趋势股 | 趋势评分 >= 16（满分 20 的 80%） |
| 高风险 | 风险评分 < 5（满分 10 的 50%） |
| 稳健型 | 按稳健型权重重新评分，取 Top 20 |
| 进取型 | 按进取型权重重新评分，取 Top 20 |
| 保守型 | 按保守型权重重新评分，取 Top 20 |
| 高波动 | 波动率排名前 20% |

### 报告引擎

系统可以生成三类专业投资报告：

#### 1. 每日策略报告（8000+ 字）

每日收盘后自动生成，内容包括：
- 市场情绪仪表盘（多空力量对比图）
- AI 生成的专家市场洞察（接入 DeepSeek 大模型）
- 信号分布全景（买入/加仓/观望/减仓/卖出数量和占比）
- 板块热度排行（按行业分组的平均评分和信号分布）
- Top 买入信号详评（每只股票的五维评分条形图 + 信号逻辑）
- 减仓/卖出预警（风险提示）
- A 股 / 港股分类统计
- 风格化版本（稳健型/进取型/保守型，按不同权重筛选和排序）

#### 2. 个股深度分析报告（8000+ 字）

针对单只股票的全面分析：
- 基本信息和行业定位
- 五维评分详解（每个子项的得分和点评）
- 行情走势（近 120 日 K 线数据）
- 财务分析（近 8 期财报关键指标）
- 技术指标解读（MA/MACD/RSI/布林带）
- 信号和操作建议
- AI 个股分析（接入 DeepSeek 大模型）
- 券商研报汇总

#### 3. 风格化策略报告（8000+ 字）

针对特定投资风格的策略报告：
- 稳健型：偏好低波动、高股息蓝筹，仓位上限 60%
- 进取型：偏好高成长、强趋势标的，仓位上限 90%
- 保守型：偏好低估值、高安全边际，仓位上限 40%

每种风格有独立的评分权重和筛选标准。

#### 报告格式

报告以 Markdown 格式存储，支持：
- 在线阅读（前端 MarkdownRenderer 渲染）
- PDF 导出（xhtml2pdf 转换，含封面页和专业排版）

### 回测引擎

基于真实历史数据的策略回测，尽可能贴近实盘环境。

#### 交易成本模型

| 费用 | 费率 | 说明 |
|------|------|------|
| 佣金 | 0.025% | 买卖双向，最低 5 元 |
| 印花税 | 0.05% | 仅卖出 |
| 过户费 | 0.001% | 沪市 |
| 滑点 | 0.1% | 买入加价、卖出减价 |

#### 涨跌停限制

- 主板（600xxx/000xxx）：±10%
- 创业板（300xxx/301xxx）：±20%
- 科创板（688xxx）：±20%

涨停时无法买入，跌停时无法卖出。

#### 调仓逻辑

1. 每个调仓日（月度/季度），按最新评分排序
2. 选出评分 Top N 的股票作为目标持仓
3. 卖出不在目标列表中的现有持仓
4. 买入目标列表中的新股票（等权分配）
5. 交易以收盘价执行，含滑点和交易成本

#### 基准对比

默认基准为所有股票的等权组合（与策略使用相同的股票池）。

#### 输出指标

| 指标 | 说明 |
|------|------|
| 总收益率 | 回测期间的累计收益 |
| 年化收益率 | 折算为年度收益 |
| 基准收益率 | 等权基准的同期收益 |
| 超额收益 | 策略收益 - 基准收益 |
| 最大回撤 | 最大峰谷跌幅 |
| 夏普比率 | 风险调整后收益 |
| 胜率 | 盈利交易占比 |
| 月度收益表 | 每月策略/基准/超额收益 |
| 权益曲线图 | 策略 vs 基准的净值走势 |
| 交易日志 | 每笔买卖的详细记录 |

---

## 数据源架构

系统采用**适配器模式 + 复合路由**，根据数据类型自动选择最优数据源。

### 数据源矩阵

| 数据源 | 行情 | 财务 | 估值 | 研报 | 说明 |
|--------|------|------|------|------|------|
| 东方财富 | A 股 | - | A 股 | ✓ | A 股行情主力源，研报唯一源 |
| 雪球 | - | ✓ | ✓ | - | 财务数据主力源 |
| AKShare | A 股+港股 | - | - | - | 股票列表同步、港股行情 |
| baostock | A 股 | - | - | - | A 股行情备选源（前复权） |
| Yahoo Finance | A 股+港股 | ✓ | ✓ | - | 国际数据备选源 |

### 路由策略

```
行情数据: 东方财富 → baostock → AKShare
财务数据: 雪球 → Yahoo Finance → 东方财富
估值数据: 雪球 → Yahoo Finance → 东方财富
研报数据: 东方财富（唯一源）
```

每个数据源都有独立的错误处理，上游失败时自动降级到下游。

### HTTP 客户端

所有外部请求通过统一的 `http_client.py`：
- 连接池复用（pool_connections=10, pool_maxsize=20）
- 自动重试（3 次，指数退避，覆盖连接错误和 5xx）
- 国内源自动绕过代理（东方财富、雪球等国内域名不走代理）
- 国际源走系统代理（Yahoo Finance）

---

## 项目结构

```text
rongxian/
├── .github/
│   └── workflows/
│       └── ci.yml                    # GitHub Actions CI（后端测试 + 前端构建）
│
├── backend/                          # Python 后端
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                   # FastAPI 入口（lifespan、CORS、路由注册）
│   │   ├── seed.py                   # 模拟数据生成器（500+ 只股票）
│   │   ├── batch_score.py            # 批量评分脚本
│   │   │
│   │   ├── core/
│   │   │   ├── config.py             # Settings（pydantic-settings，JWT 自动管理）
│   │   │   ├── constants.py          # 枚举常量（Market, SignalType, ReportType...）
│   │   │   └── redis.py              # Redis 客户端（速率限制 + 缓存，内存回退）
│   │   │
│   │   ├── db/
│   │   │   ├── base.py               # SQLAlchemy DeclarativeBase
│   │   │   └── session.py            # Engine + SessionLocal + get_db（含 rollback）
│   │   │
│   │   ├── models/                   # SQLAlchemy ORM 模型（13 个）
│   │   │   ├── stock.py              # 股票基本信息
│   │   │   ├── daily_price.py        # 日线行情（OHLCV + PE/PB/市值/股息率）
│   │   │   ├── financial_metric.py   # 财务指标（营收/利润/ROE/现金流/EPS...）
│   │   │   ├── technical_indicator.py # 技术指标（MA/MACD/RSI/布林带）
│   │   │   ├── stock_score.py        # 五维评分（含 CheckConstraint）
│   │   │   ├── trade_signal.py       # 交易信号
│   │   │   ├── report.py             # 报告
│   │   │   ├── portfolio.py          # 组合 + 持仓
│   │   │   ├── user.py               # 用户
│   │   │   ├── setting.py            # 系统设置
│   │   │   ├── research_report.py    # 券商研报
│   │   │   ├── api_config.py         # API 配置 + 用户配额 + 调用日志
│   │   │   └── stock_status_history.py # 股票状态变更历史（消除生存偏差）
│   │   │
│   │   ├── schemas/                  # Pydantic 请求/响应模型
│   │   │   ├── stock.py, price.py, financial.py, score.py
│   │   │   ├── signal.py, report.py, dashboard.py, backtest.py
│   │   │
│   │   ├── api/                      # FastAPI 路由（9 个模块）
│   │   │   ├── auth.py               # 登录/注册/Token（JWT + 速率限制）
│   │   │   ├── dashboard.py          # 仪表盘（带 Redis 缓存）
│   │   │   ├── stocks.py             # 股票搜索/同步/详情
│   │   │   ├── signals.py            # 信号列表（分页+筛选）
│   │   │   ├── pools.py              # 8 类股票池
│   │   │   ├── reports.py            # 报告生成/列表/PDF 导出
│   │   │   ├── backtest.py           # 策略回测 + 组合模拟
│   │   │   ├── settings.py           # 通知配置
│   │   │   └── admin.py              # 管理后台（用户/股票/评分/信号/数据库/API）
│   │   │
│   │   ├── services/                 # 业务逻辑层
│   │   │   ├── scoring.py            # 五维评分引擎（行业百分位 + N+1 优化）
│   │   │   ├── signal.py             # 信号生成（波动率自适应 + 仓位集中度）
│   │   │   ├── dashboard.py          # 仪表盘数据聚合
│   │   │   ├── backtest.py           # 回测引擎（滑点 + 涨跌停 + 交易成本）
│   │   │   ├── stock_sync.py         # 股票列表/研报同步
│   │   │   ├── notification.py       # 邮件 + 飞书推送（含重试 + HTML 转义）
│   │   │   ├── ai_service.py         # DeepSeek AI 集成（线程池）
│   │   │   ├── pdf_service.py        # Markdown → PDF
│   │   │   └── report/               # 报告生成包
│   │   │       ├── __init__.py       # 公开 API（generate_daily/stock/style_report）
│   │   │       ├── style_config.py   # 投资风格配置
│   │   │       ├── utils.py          # 工具函数（评分条、分布图...）
│   │   │       ├── daily.py          # 每日策略报告（含 AI 专家观点）
│   │   │       ├── stock.py          # 个股深度分析报告
│   │   │       └── style.py          # 风格化策略报告
│   │   │
│   │   ├── data_providers/           # 外部数据源适配器
│   │   │   ├── base.py               # DataProviderBase 抽象基类
│   │   │   ├── http_client.py        # 统一 HTTP 客户端（连接池 + 重试）
│   │   │   ├── eastmoney_provider.py # 东方财富（行情 + 估值 + 研报）
│   │   │   ├── xueqiu_provider.py    # 雪球（财务 + 估值）
│   │   │   ├── yahoo_provider.py     # Yahoo Finance（备选源）
│   │   │   ├── mock_provider.py      # 模拟数据（开发用）
│   │   │   └── composite_provider.py # 复合路由（自动选择最优源）
│   │   │
│   │   └── jobs/
│   │       └── scheduler.py          # APScheduler 定时任务（15:30 刷新 + 通知）
│   │
│   ├── alembic/                      # 数据库迁移
│   │   ├── env.py                    # 迁移环境配置
│   │   ├── script.py.mako            # 迁移脚本模板
│   │   └── versions/                 # 迁移版本文件
│   │
│   ├── tests/                        # pytest 测试
│   │   ├── conftest.py               # 共享 fixtures（内存 SQLite 测试 DB）
│   │   ├── test_scoring.py           # 评分服务测试（7 个用例）
│   │   ├── test_signal.py            # 信号服务测试（6 个用例）
│   │   ├── test_auth.py              # 认证服务测试（6 个用例）
│   │   └── test_redis.py             # Redis 模块测试（2 个用例）
│   │
│   ├── alembic.ini                   # Alembic 配置
│   ├── requirements.txt              # Python 依赖（19 个）
│   └── Dockerfile                    # 后端 Docker 镜像
│
├── frontend/                         # Next.js 前端
│   ├── src/
│   │   ├── app/                      # Next.js App Router 页面
│   │   │   ├── layout.tsx            # 根布局（Provider 链 + ErrorBoundary）
│   │   │   ├── page.tsx              # 首页（重定向到 /dashboard）
│   │   │   ├── globals.css           # 全局样式（CSS 变量 + 深浅主题）
│   │   │   ├── dashboard/page.tsx    # 策略总览仪表盘
│   │   │   ├── stocks/page.tsx       # 股票列表
│   │   │   ├── stocks/[symbol]/page.tsx # 个股详情（K线/财务/评分/信号/研报）
│   │   │   ├── signals/page.tsx      # 信号中心（分页+筛选）
│   │   │   ├── pools/page.tsx        # 股票池（8 类）
│   │   │   ├── reports/page.tsx      # 报告中心（系统报告 + 券商研报）
│   │   │   ├── backtest/page.tsx     # 策略回测 + 组合模拟
│   │   │   ├── settings/page.tsx     # 通知配置（邮件 + 飞书）
│   │   │   └── admin/page.tsx        # 管理后台（7 个 Tab）
│   │   │
│   │   ├── components/
│   │   │   ├── AuthGuard.tsx         # 认证守卫（未登录 → 登录页）
│   │   │   ├── LoginPage.tsx         # 登录/注册表单（含快速登录）
│   │   │   ├── Sidebar.tsx           # 侧边栏导航（可折叠 + 主题/语言切换）
│   │   │   ├── TopSearch.tsx         # 全局股票搜索（防抖）
│   │   │   ├── ErrorBoundary.tsx     # 全局错误边界
│   │   │   ├── StrategySummaryCard.tsx # 策略摘要卡片
│   │   │   ├── MarketOverviewCard.tsx  # 市场概览卡片
│   │   │   ├── SignalTable.tsx       # 信号表格
│   │   │   ├── SignalDistributionChart.tsx # 信号分布饼图
│   │   │   ├── PortfolioChart.tsx    # 组合收益曲线
│   │   │   ├── StockPoolCard.tsx     # 股票池卡片
│   │   │   ├── RiskAlertCard.tsx     # 风险预警卡片
│   │   │   ├── ScoreBreakdown.tsx    # 评分明细（雷达图 + 进度条）
│   │   │   └── ui/                   # 通用 UI 组件
│   │   │       ├── GlassCard.tsx     # 毛玻璃卡片
│   │   │       ├── Skeleton.tsx      # 骨架屏
│   │   │       ├── TabSwitch.tsx     # Tab 切换
│   │   │       ├── Toast.tsx         # Toast 通知
│   │   │       ├── EmptyState.tsx    # 空状态
│   │   │       ├── LoadingScreen.tsx # 全屏加载
│   │   │       ├── SignalBadge.tsx   # 信号标签
│   │   │       ├── NumberDisplay.tsx # 数字格式化显示
│   │   │       ├── MetricCard.tsx    # 指标卡片
│   │   │       ├── ChartTooltip.tsx  # 图表 Tooltip
│   │   │       └── MarkdownRenderer.tsx # Markdown 渲染（react-markdown）
│   │   │
│   │   ├── lib/
│   │   │   ├── api.ts                # API 客户端（全类型化，超时+重试+401处理）
│   │   │   ├── auth.tsx              # AuthProvider（JWT + localStorage）
│   │   │   ├── i18n.tsx              # LanguageProvider（中/英，500+ key）
│   │   │   ├── theme.tsx             # ThemeProvider（深/浅/系统）
│   │   │   ├── utils.ts              # 工具函数（格式化百分比/金额/市值...）
│   │   │   ├── chartColors.ts        # 图表配色
│   │   │   └── translations/
│   │   │       ├── zh.ts             # 中文翻译（500+ key）
│   │   │       └── en.ts             # 英文翻译（500+ key）
│   │   │
│   │   └── types/
│   │       └── index.ts              # TypeScript 类型定义（40+ 接口）
│   │
│   ├── tailwind.config.ts            # Tailwind 配置（自定义色板+动画）
│   ├── next.config.js                # Next.js 配置（API 代理）
│   ├── tsconfig.json                 # TypeScript 配置（strict 模式）
│   ├── package.json                  # 前端依赖
│   └── Dockerfile                    # 前端 Docker 镜像
│
├── infra/
│   └── init.sql                      # PostgreSQL 初始化脚本
│
├── docker-compose.yml                # Docker Compose 编排
├── .env.example                      # 环境变量示例
├── .gitignore                        # Git 忽略规则
└── README.md                         # 本文件
```

---

## API 接口文档

完整的交互式 API 文档在服务启动后访问：
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### 认证相关

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/api/auth/login` | 用户登录（返回 JWT Token） | ✗ |
| POST | `/api/auth/register` | 用户注册 | ✗ |
| GET | `/api/auth/me` | 获取当前用户信息 | ✓ |

### 数据查询

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/api/dashboard` | 仪表盘数据（市场概览+策略摘要+Top信号+股票池+风险预警） | ✗ |
| GET | `/api/stocks/search?keyword=茅台` | 搜索股票（代码/名称模糊匹配） | ✗ |
| GET | `/api/stocks/{symbol}` | 股票详情（行情+财务+评分+信号+研报） | ✗ |
| GET | `/api/stocks/count` | 数据库中的股票数量 | ✗ |
| GET | `/api/signals?page=1&page_size=20` | 交易信号列表（分页+按市场/类型筛选） | ✗ |
| GET | `/api/pools?type=quality` | 股票池（quality/undervalued/trend/risk/steady/aggressive/conservative/volatile） | ✗ |
| GET | `/api/reports?page=1` | 报告列表 | ✗ |
| GET | `/api/reports/{id}` | 报告详情（含 Markdown 内容） | ✗ |
| GET | `/api/reports/research?symbol=600519` | 券商研报列表 | ✗ |

### 操作类

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/api/stocks/sync?market=ALL` | 同步股票列表（admin） | ✓ admin |
| POST | `/api/stocks/data/fetch?symbol=600519` | 添加股票并获取数据 | ✓ member |
| POST | `/api/reports/generate?report_type=DAILY` | 生成报告 | ✓ |
| POST | `/api/reports/generate-style?style=steady` | 生成风格报告 | ✓ |
| GET | `/api/reports/{id}/pdf` | 下载报告 PDF | ✓ |
| POST | `/api/backtest/run` | 运行策略回测 | ✓ analyst |
| POST | `/api/backtest/simulate` | 组合模拟 | ✓ analyst |

### 管理后台

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/api/admin/stats` | 系统统计 | ✓ admin |
| GET | `/api/admin/users` | 用户列表 | ✓ admin |
| PUT | `/api/admin/users/{id}` | 修改用户角色/状态 | ✓ admin |
| GET | `/api/admin/tables` | 数据库表列表 | ✓ admin |
| GET | `/api/admin/tables/{name}` | 表数据浏览（分页） | ✓ admin |
| GET/PUT | `/api/admin/stocks` | 股票管理 | ✓ admin |
| GET/PUT | `/api/admin/scores` | 评分管理 | ✓ admin |
| GET/PUT/DELETE | `/api/admin/signals` | 信号管理 | ✓ admin |
| GET/POST/DELETE | `/api/admin/api-configs` | API 配置管理 | ✓ admin |
| GET/PUT | `/api/admin/user-quotas` | 用户配额管理 | ✓ admin |
| GET | `/api/admin/api-logs` | API 调用日志 | ✓ admin |

### 系统

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/api/health` | 健康检查（含数据库+Redis 状态） | ✗ |
| GET | `/api/settings` | 系统设置 | ✓ |
| POST | `/api/settings/notification` | 更新通知配置 | ✓ admin |
| POST | `/api/settings/test-notification?type=email` | 测试通知 | ✓ admin |

---

## 前端架构

### Provider 链

根布局的 Provider 嵌套顺序：

```
ErrorBoundary
  └── ThemeProvider (深/浅主题)
        └── LanguageProvider (中/英)
              └── AuthProvider (JWT 认证)
                    └── AuthGuard (未登录拦截)
                          └── 页面内容
```

### 状态管理

没有使用 Redux/Zustand 等全局状态库，采用三层状态：

1. **全局状态**（Context）：用户认证、主题、语言
2. **页面状态**（useState）：每个页面独立管理数据获取和 UI 状态
3. **服务端状态**（fetch + 缓存）：API 数据通过 `api.ts` 获取，仪表盘有 Redis 缓存

### 主题系统

采用 CSS 变量驱动的深浅主题：

```css
:root {
  --background: #0B1120;     /* 深色背景 */
  --card-bg: rgba(255,255,255,0.03);
  --text-primary: #FFFFFF;
  /* ... 25+ 变量 */
}

.light {
  --background: #F8FAFC;     /* 浅色背景 */
  --card-bg: rgba(255,255,255,0.9);
  --text-primary: #1E293B;
  /* ... 只需切换变量值 */
}
```

组件使用 `var(--xxx)` 引用颜色，`.light` 类只需改变量值，无需 `!important` 覆盖。

### 国际化

自定义 i18n 实现，支持参数插值：

```typescript
t("admin.confirmDeleteStock", { symbol: "600519", name: "贵州茅台" })
// → "确认删除 600519 贵州茅台？\n将同时删除关联的行情、财务、评分、信号数据。"
```

500+ 翻译 key 覆盖所有页面，`localStorage` 持久化语言偏好。

---

## 安全机制

### 认证与授权

- **JWT Token**：登录后返回 Token，有效期 8 小时
- **密码哈希**：bcrypt 加盐哈希，不可逆
- **密码策略**：至少 8 位，必须包含大小写字母和数字
- **速率限制**：登录 20 次/分钟，注册 10 次/小时（Redis 或内存回退）
- **角色控制**：admin（管理员）、analyst（分析师）、user（普通用户）、guest（访客）

### 数据安全

- **API Key 加密**：第三方 API Key 使用 Fernet 对称加密存储
- **敏感字段脱敏**：管理后台浏览数据库时，password_hash/api_key 等字段显示为 `***`
- **JWT 密钥管理**：自动生成并持久化到 `.jwt_secret` 文件（已在 `.gitignore` 中）

### 输入安全

- **SQL 注入防护**：Admin 表名白名单校验 + LIKE 特殊字符转义
- **HTML 注入防护**：邮件模板中用户数据使用 `html_escape()` 转义
- **CORS 配置**：仅允许指定的 localhost 端口

---

## 部署指南

### 生产环境部署

```bash
# 1. 克隆代码
git clone https://github.com/zhuowoshuang/rongxian.git
cd rongxian

# 2. 设置环境变量
export JWT_SECRET_KEY="$(openssl rand -base64 48)"

# 3. 修改 docker-compose.yml 中的数据库密码
# 将 POSTGRES_PASSWORD 改为强密码

# 4. 构建并启动
docker-compose up -d --build

# 5. 检查服务状态
docker-compose ps
curl http://localhost:8000/api/health
```

### 生产环境注意事项

1. **必须设置 `JWT_SECRET_KEY`**：不设置则每次重启生成新密钥，所有已发 Token 失效
2. **修改数据库密码**：`docker-compose.yml` 中的 `POSTGRES_PASSWORD` 默认是 `postgres`
3. **配置反向代理**：建议在前端加 Nginx/Caddy 做 HTTPS 终结
4. **配置 Redis**：设置 `REDIS_URL` 启用 Redis，否则速率限制和缓存使用内存（多实例不共享）
5. **关闭调试模式**：设置 `DEBUG=false`

---

## 开发指南

### 添加新的数据源

1. 在 `backend/app/data_providers/` 创建新文件，继承 `DataProviderBase`
2. 实现 `fetch_daily_prices`、`fetch_financial_metrics` 等方法
3. 在 `composite_provider.py` 中注册新数据源到路由链

### 添加新的评分维度

1. 在 `scoring.py` 中添加新的 `calculate_xxx_score` 函数
2. 在 `score_stock` 中调用新函数并累加到 `total_score`
3. 更新 `StockScore` 模型（添加新字段）
4. 运行 Alembic 迁移：`alembic revision --autogenerate -m "add xxx score"`

### 添加新的翻译

1. 在 `frontend/src/lib/translations/zh.ts` 添加中文 key
2. 在 `frontend/src/lib/translations/en.ts` 添加英文 key
3. 在组件中使用 `t("your.key")`

---

## 测试

```bash
# 运行所有后端测试
cd backend
pytest tests/ -v

# 运行特定测试
pytest tests/test_scoring.py -v

# 前端类型检查
cd frontend
npx tsc --noEmit

# 前端构建检查
npm run build
```

### 测试覆盖

| 模块 | 测试文件 | 用例数 | 覆盖内容 |
|------|----------|--------|----------|
| 评分服务 | test_scoring.py | 7 | 质量/估值/成长评分 + 评级映射 |
| 信号服务 | test_signal.py | 6 | 信号类型判定 + 仓位计算 |
| 认证服务 | test_auth.py | 6 | 密码哈希/验证 + Token 创建/验证/过期 |
| Redis 模块 | test_redis.py | 2 | 内存回退速率限制 + 窗口过期 |

---

## 已知限制与路线图

### 已知限制

| 项目 | 说明 |
|------|------|
| 生存偏差 | 回测已使用历史状态表缓解，但历史退市数据仍需补充 |
| 滑点模型 | 使用固定 0.1% 滑点，未按流动性分层 |
| 仓位管理 | 行业集中度限制基于信号数近似，非精确持仓金额 |
| 数据覆盖 | 模拟数据约 500 只股票，真实数据需配置数据源 API |
| 实时行情 | 系统为 T+1 批量分析，不提供盘中实时行情 |

### 路线图

- [ ] 补充历史退市股票数据
- [ ] 按流动性分层的滑点模型
- [ ] 精确的持仓金额集中度计算
- [ ] 盘中实时行情推送（WebSocket）
- [ ] 更多 AI 功能（自然语言查询、智能选股）
- [ ] 移动端适配
- [ ] 多用户协作（团队版）

---

## 许可证

本系统仅用于研究和辅助分析，不构成任何投资建议。使用者需自行承担投资风险。

---

<p align="center">
  <sub>Built with ❤️ for quantitative research</sub>
</p>
