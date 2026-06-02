# 截图指南

请按照以下步骤截取系统页面截图，用于 README 展示。

## 启动系统

```bash
# 方式一：Docker Compose（推荐）
docker-compose up --build

# 方式二：本地开发
# 终端1：启动后端
cd backend
python -m app.seed
uvicorn app.main:app --reload --port 8000

# 终端2：启动前端
cd frontend
npm run dev
```

## 截取页面

访问 http://localhost:3000，使用默认账号登录（admin/admin），截取以下页面：

### 1. 策略总览仪表盘 (`/dashboard`)

- 文件名：`dashboard.png`
- 截取完整页面，包含市场概览、信号分布、股票池等

### 2. 信号中心 (`/signals`)

- 文件名：`signals.png`
- 截取信号列表表格

### 3. 股票分析详情 (`/stocks/000001`)

- 文件名：`stock-detail.png`
- 截取股票详情页，包含价格走势和评分

### 4. 股票池 (`/pools`)

- 文件名：`pools.png`
- 截取股票池页面

### 5. 回测中心 (`/backtest`)

- 文件名：`backtest.png`
- 截取回测页面（可先运行一次回测）

### 6. 报告中心 (`/reports`)

- 文件名：`reports.png`
- 截取报告列表页面

## 保存位置

将所有截图保存到 `docs/screenshots/` 目录：

```text
docs/
└── screenshots/
    ├── dashboard.png
    ├── signals.png
    ├── stock-detail.png
    ├── pools.png
    ├── backtest.png
    └── reports.png
```

## 截图技巧

- 使用浏览器全屏模式（F11）
- 窗口宽度建议 1440px 或 1920px
- 确保页面数据已加载完成
- 可以使用浏览器开发者工具的截图功能（Ctrl+Shift+P → "Capture full size screenshot"）

## 提交截图

```bash
cd docs/screenshots
# 将截图文件放在此目录后
git add .
git commit -m "docs: 添加系统页面截图"
git push
```
