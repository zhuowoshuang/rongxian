# 前端迁移模板

## 文件说明

| 文件 | 用途 |
|------|------|
| `stockData.ts` | TypeScript 类型定义（与 OpenAPI 契约一致） |
| `adataStockApi.ts` | API 客户端（只调用 /api/adata/...） |
| `StockDataStateView.example.tsx` | 四种 DataStatus 渲染示例 |

## 使用方式

1. 复制 `stockData.ts` 到前端 `types/` 目录
2. 复制 `adataStockApi.ts` 到前端 `api/` 目录
3. 参考 `StockDataStateView.example.tsx` 实现状态渲染

## 四种状态展示要求

| 状态 | 展示 |
|------|------|
| OK | 正常渲染数据 |
| PARTIAL | 展示数据 + 顶部 banner 提示缺失/延迟 |
| EMPTY | 空状态占位，不显示假数据 |
| ERROR | 错误信息 + 重试按钮 |

## 评分模块

如评分仍为 demo，必须显式标注"演示评分"，不写死数值。
