# 阻塞问题

## 当前状态

No blocking issues for data-contract migration.

## 已解决的阻塞问题

| 问题 | 修复 | 版本 |
|------|------|------|
| missingFields 粒度过粗 | 改为具体字段名 | v1.1.0 |
| 999999 返回 PARTIAL | 改为 EMPTY | v1.1.0 |
| abc 返回 PARTIAL | 改为 ERROR | v1.1.0 |
| 导入方式不稳定 | 新增 pyproject.toml 支持 pip install | v1.2.0 |
| 契约不一致 | Python/TS/OpenAPI 三向对齐 | v1.2.0 |

## 非阻塞注意事项

- 东方财富 API 可能被企业代理拦截（需配置网络白名单）
- 同花顺数据源需额外安装 `py_mini_racer`（当前未使用）
- 行业字段本轮未封装
