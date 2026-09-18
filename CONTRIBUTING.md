# 贡献指南

感谢关注机床售后技术支持工作台。提交变更前，请先确认问题属于知识协同、故障辅助或工程治理范围；库存、财务、远程控制和自动修改机床参数不属于本项目边界。

## 本地检查

后端：

```bash
cd backend
python -m pip install -r requirements-dev.txt
ruff check app tests alembic
pytest -q
```

前端：

```bash
cd frontend
npm ci
npm run typecheck
npm run build
```

涉及数据模型时必须新增 Alembic 迁移，并在 SQLite 测试库和 PostgreSQL 环境验证升级。禁止提交真实企业资料、账号密钥、设备序列号或未经脱敏的维修记录。
