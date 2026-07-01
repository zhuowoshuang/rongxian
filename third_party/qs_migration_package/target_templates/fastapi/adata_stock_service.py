"""
清数智算 Backend — AData 服务层 vendored 集成

如果不想依赖 sys.path.insert 方式引入 qs_backend_bridge，
可以将 qs_migration_package/python/qs_adapter/ 和 qs_backend_bridge/
复制到 backend 内部作为 vendored 包。

用法：
  from .vendored.qs_backend_bridge import get_stock_data_bundle
  bundle = get_stock_data_bundle("300866")
"""

# Vendored integration 路径示例：
# backend/
#   vendored/
#     qs_adapter/
#     qs_backend_bridge/
#   services/
#     adata_stock_service.py  ← 本文件
