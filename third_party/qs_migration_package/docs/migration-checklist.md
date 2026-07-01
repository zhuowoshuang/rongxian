# 清数智算迁移检查清单

## 环境检查

- [ ] Python 3.11+ 或 3.12+（需 setuptools>=68）
- [ ] `pip install -r qs_migration_package/python/requirements-adata.txt` 成功
- [ ] `pip install -e /path/to/adata` 成功
- [ ] `import qs_adapter` 不报错
- [ ] `import qs_backend_bridge` 不报错

## Smoke Test

- [ ] `python qs_migration_package/python/qs_backend_bridge/smoke_test.py --symbol 300866` 全部通过
- [ ] search_stocks("300866") 返回至少 1 条
- [ ] get_stock_quote("300866") 返回 OK 或 PARTIAL（不允许 ERROR）
- [ ] get_stock_kline("300866") items >= 1000
- [ ] get_stock_financials("300866") 返回期数 >= 10
- [ ] get_stock_data_bundle("300866") 包含 quote + kline + financials + sourceSummary
- [ ] 错误码 999999 返回 ERROR 状态，不崩溃

## 前端检查

- [ ] TypeScript 类型编译通过（复制 stock-data-types.ts 后）
- [ ] 个股页显示 quote 价格卡
- [ ] K 线图正常渲染
- [ ] 财务表正常渲染
- [ ] 缺失字段在页面上有提示（非静默吞掉）
- [ ] 评分模块仍标记为"演示"（如仍是 demo）
- [ ] 非交易时段显示延迟行情提示
- [ ] 数据来源标签正确显示

## 构建检查

- [ ] `npm run build` 通过（前端）
- [ ] Docker 构建通过（后端）
- [ ] Staging 环境 300866 页面可访问

## 已知限制确认

- [ ] 确认前端不依赖实时 websocket
- [ ] 确认财务只有核心指标（不是三大报表）
- [ ] 确认行业字段可能为空
- [ ] 确认板块数据本轮未接入
- [ ] 确认不构成投资建议的免责声明
