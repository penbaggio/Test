# 投资交易指令分发系统（v0.3 增强版）

## 🎯 系统概述

专业的投资指令实时分发系统，支持投资经理下达指令、交易员实时接收执行、管理员审计监控。

### ✨ 核心特性

**第一阶段 - 核心功能完善 ✅**
- ✅ 指令操作日志审计追踪（完整记录所有操作）
- ✅ 交易员回执功能增强（接收/执行中/完成/失败，记录成交价格数量）
- ✅ 指令撤销功能（投资经理可撤销未执行指令）
- ✅ 前端浏览器通知 + 音频提醒（新指令实时桌面通知）

**第二阶段 - 稳定性提升 ✅**
- ✅ PostgreSQL 生产数据库支持（环境变量切换）
- ✅ Redis 缓存 + 离线消息队列（用户离线消息保存）
- ✅ 结构化日志系统 + 异常告警（钉钉/企业微信通知）
- ✅ Docker 完整部署方案（一键启动所有服务）

### 🏗️ 技术架构

```
├── FastAPI (后端框架)
├── SQLAlchemy + PostgreSQL/SQLite (数据持久化)
├── Redis (缓存 + 消息队列)
├── WebSocket (实时推送)
├── JWT (用户认证)
├── Docker + Docker Compose (容器化部署)
└── Alembic (数据库迁移)
```

## 📦 快速开始

### 方式一：本地开发（SQLite）

```powershell
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动服务
uvicorn app.main:app --reload --port 8000

# 3. 访问系统
# Web界面(增强版): http://localhost:8000/app/index_enhanced.html
# API文档: http://localhost:8000/docs
```

### 方式二：Docker 部署（推荐）

```powershell
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env 修改密码等配置

# 2. 启动所有服务
docker-compose up -d --build

# 3. 查看日志
docker-compose logs -f web

# 4. 访问系统
# http://localhost:8000/app/index_enhanced.html
```

## 👥 测试账户

| 角色 | 用户名 | 密码 | 权限说明 |
|------|--------|------|---------|
| 投资经理 | im1 | test123 | 创建/撤销指令、查看自己的指令 |
| 交易员 | trader1 | test123 | 接收指令、执行回报 |
| 管理员 | admin1 | test123 | 查看所有指令、审计日志 |

## 🔧 环境变量配置

创建 `.env` 文件（参考 `.env.example`）：

```env
# 数据库
DATABASE_URL=postgresql://trading_user:password@localhost:5432/trading_system

# Redis
REDIS_URL=redis://:password@localhost:6379/0
REDIS_ENABLED=true

# 日志
LOG_LEVEL=INFO

# 告警(可选)
ALERT_WEBHOOK_URL=https://oapi.dingtalk.com/robot/send?access_token=xxx
```

## 📡 API 端点

### 指令管理
- `POST /instructions` - 创建指令 (投资经理)
- `GET /instructions` - 查询指令列表
- `POST /instructions/{id}/cancel` - 撤销指令 (投资经理)
- `POST /instructions/{id}/ack` - 回执指令 (交易员)
- `GET /instructions/{id}/logs` - 查看操作日志
- `GET /instructions/{id}/acknowledgments` - 查看回执记录

### WebSocket
- `WS /ws?token={jwt}` - 实时消息推送

详细文档: [DEPLOYMENT.md](./DEPLOYMENT.md)

## 🐳 Docker 服务说明

| 服务 | 端口 | 说明 |
|------|------|------|
| web | 8000 | FastAPI 应用 |
| db | 5432 | PostgreSQL 数据库 |
| redis | 6379 | Redis 缓存 |

## 📊 数据库结构

### 核心表
- `users` - 用户表
- `instructions` - 指令表（新增字段: urgency, deadline, remarks, target_traders）
- `instruction_logs` - 操作日志表（审计追踪）
- `instruction_acknowledgments` - 回执记录表（执行详情）

### 数据库迁移

```powershell
# 生成迁移脚本
alembic revision --autogenerate -m "description"

# 执行迁移
alembic upgrade head

# 回滚
alembic downgrade -1
```

## 📝 开发路线图

### ✅ 已完成
- [x] 基础认证与权限控制
- [x] WebSocket 实时推送
- [x] 指令CRUD操作
- [x] 操作日志审计
- [x] 交易员回执增强
- [x] 指令撤销功能
- [x] 浏览器通知+音频
- [x] PostgreSQL 支持
- [x] Redis 集成
- [x] Docker 部署
- [x] 日志系统

### 🔜 计划中
- [ ] 指令模板功能
- [ ] 批量指令操作
- [ ] 定向推送给指定交易员
- [ ] 数据统计报表
- [ ] 移动端适配
- [ ] 单元测试覆盖

## 🛠️ 运维命令

### 日志管理
```powershell
# 查看应用日志
Get-Content logs/app.log -Tail 100 -Wait

# Docker 日志
docker-compose logs -f web
```

### 数据备份
```powershell
# PostgreSQL 备份
docker-compose exec db pg_dump -U trading_user trading_system > backup.sql

# 恢复
docker-compose exec -T db psql -U trading_user trading_system < backup.sql
```

## 📞 技术支持

- **API文档**: http://localhost:8000/docs
- **部署文档**: [DEPLOYMENT.md](./DEPLOYMENT.md)
- **问题反馈**: 查看 logs/error.log

## 📄 许可证

内部系统，仅供授权用户使用。

---

**Version**: 0.3.0  
**更新时间**: 2025-11-04  
**维护者**: AI Copilot
