# 清数智算迁移包

版本：1.0.0 | 生成日期：2026-06-30 | 数据源：AData

## 包说明

本文件夹是清数智算项目从 AData 开源项目（`https://github.com/1nchaos/adata`）提取的完整数据迁移包。

包含：
- **数据适配层**（`python/qs_adapter/`）—— 封装 AData 原生 API，输出统一数据结构
- **后端桥接层**（`python/qs_backend_bridge/`）—— fallback、名称补齐、camelCase 输出
- **前端契约**（`frontend_contract/`）—— TypeScript 类型 + 示例 API 调用 + UI 策略
- **样例数据**（`examples/`）—— 300866 安克创新真实数据（6 个 JSON）
- **文档**（`docs/`）—— 接入指南、API 契约、数据源审计、迁移清单、已知限制

## 快速开始

```bash
# 安装依赖
pip install -r python/requirements-adata.txt

# 验证
python python/qs_backend_bridge/smoke_test.py --symbol 300866
```

## 核心 API

```python
from qs_backend_bridge import get_stock_data_bundle
bundle = get_stock_data_bundle("300866")
print(bundle.quote.price)      # 104.50
print(len(bundle.kline.items)) # 1416
print(len(bundle.financials))  # 37
```

## 文件清单

详见 `package_manifest.json`
