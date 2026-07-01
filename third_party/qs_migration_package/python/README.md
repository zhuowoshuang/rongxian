# QS-AData Bridge — Python 安装与使用

## 安装

```bash
# 方式 A：开发环境（在 AData 项目根目录）
cd F:/tools/2.2adata
pip install -e .                           # 安装 AData
pip install -e qs_migration_package/python  # 以可编辑模式安装 bridge

# 方式 B：迁移到清数智算（不需要 AData 源码）
# 将 python/ 目录内容复制到 backend/app/integrations/adata/
# 然后在清数智算 backend 中 import
```

## 使用

```python
from qs_backend_bridge.stock_data_service import get_stock_data_bundle
bundle = get_stock_data_bundle("300866")
print(bundle.quote.price)
```

## 依赖

- Python >= 3.10
- setuptools >= 68.0
- 运行时需 AData 可导入：`pip install adata` 或 `pip install -e /path/to/adata`
