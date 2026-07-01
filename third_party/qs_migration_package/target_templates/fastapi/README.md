# FastAPI 路由模板

## 使用方式

1. 复制 `adata_stock_routes.py` 到清数智算 backend 的 routers 目录
2. 调整 `from qs_backend_bridge...` 的 import 路径
3. 在 FastAPI app 中注册：

```python
from fastapi import FastAPI
from .routers.adata_stock_routes import router as adata_router

app = FastAPI()
app.include_router(adata_router, prefix="/api/adata")
```

4. 确保 `qs_migration_package/python/` 在 Python path 中。

## 非 FastAPI 项目

如果清数智算使用 Express/Next.js/Flask 等其他框架：
- 路由路径和返回结构仍然完全适用
- 只需用对应框架的语法实现相同的 5 个端点
- API 契约以 `openapi/qs_adata_api.openapi.json` 为准
