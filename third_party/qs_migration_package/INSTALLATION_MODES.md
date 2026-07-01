# 安装方式

## 方式 A：开发环境本地接入（AData 项目内）

```bash
cd F:/tools/2.2adata

# 1. 安装 AData
pip install -e .

# 2. 安装 bridge
pip install -e qs_migration_package/python

# 3. 验证
python -c "from qs_backend_bridge.stock_data_service import get_stock_data_bundle; print(get_stock_data_bundle('300866').dataStatus)"
```

## 方式 B：迁移到清数智算 backend

```bash
# 在清数智算项目根目录

# 1. 复制 bridge 到 integrations
cp -r F:/tools/2.2adata/qs_migration_package/python/qs_adapter backend/app/integrations/adata/
cp -r F:/tools/2.2adata/qs_migration_package/python/qs_backend_bridge backend/app/integrations/adata/

# 2. 安装依赖
cd backend/app/integrations/adata
pip install -r requirements-adata.txt

# 3. 确保 AData 可导入（pip install adata 或 pip install -e /path/to/adata）
pip install adata

# 4. 在 backend code 中 import
# from integrations.adata.qs_backend_bridge.stock_data_service import get_stock_data_bundle
```

## 关键依赖

- AData 本身必须可导入（`pip install adata` 或本地安装）
- 如果 AData 不可导入，所有数据接口将返回 ERROR
- 不推荐长期使用 `sys.path.insert` 方案
