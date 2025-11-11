# 投资交易指令分发系统 v0.3 - 部署与使用指南

## 📋 目录
- [系统架构](#系统架构)
- [快速开始](#快速开始)
- [Docker部署](#docker部署)
- [功能说明](#功能说明)
- [API文档](#api文档)
- [运维指南](#运维指南)

---

## 🏗️ 系统架构

### 技术栈
- **后端框架**: FastAPI 0.115.4
- **数据库**: PostgreSQL 15 / SQLite (开发)
- **缓存/消息队列**: Redis 7
- **实时通信**: WebSocket
- **认证**: JWT (JSON Web Token)
- **日志**: Python logging + RotatingFileHandler
- **容器化**: Docker + Docker Compose

### 核心功能
✅ **第一阶段 - 核心功能**
- [x] 三类用户权限控制(投资经理/交易员/管理员)
- [x] 指令创建、撤销、执行
- [x] 交易员回执功能(接收/执行中/完成/失败)
- [x] 操作日志审计追踪
- [x] WebSocket实时推送
- [x] 浏览器通知 + 音频提醒

✅ **第二阶段 - 稳定性提升**
- [x] PostgreSQL生产数据库支持
- [x] Redis缓存与离线消息队列
- [x] 结构化日志系统
- [x] 异常告警(钉钉/企业微信)
- [x] Docker容器化部署
- [x] 数据库迁移工具(Alembic)

---

## 🚀 快速开始

### 方式一: 本地开发(SQLite)

#### 1. 安装依赖
```powershell
# 创建虚拟环境
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 安装依赖
pip install -r requirements.txt
```

#### 2. 启动服务
```powershell
cd backend
uvicorn app.main:app --reload --port 8000
```

#### 3. 访问系统
- **Web界面**: http://localhost:8000/app/index_enhanced.html
- **API文档**: http://localhost:8000/docs
- **原版界面**: http://localhost:8000/app/index.html

#### 4. 测试账户
| 角色 | 用户名 | 密码 |
|------|--------|------|
| 投资经理 | im1 | test123 |
| 交易员 | trader1 | test123 |
| 管理员 | admin1 | test123 |

---

## 🐳 Docker部署

### 方式二: Docker Compose(推荐生产环境)

#### 1. 准备配置文件
```powershell
cd backend

# 复制环境变量模板
cp .env.example .env

# 编辑.env文件,修改密码等配置
notepad .env
```

#### 2. 启动所有服务
```powershell
# 构建并启动(后台运行)
docker-compose up -d --build

# 查看日志
docker-compose logs -f web

# 查看所有容器状态
docker-compose ps
```

#### 3. 初始化数据库(首次运行)
```powershell
# 进入容器
docker-compose exec web bash

# 运行迁移(如果使用Alembic)
alembic upgrade head

# 退出容器
exit
```

#### 4. 停止服务
```powershell
# 停止所有容器
docker-compose stop

# 停止并删除容器
docker-compose down

# 删除所有数据(包括数据库)
docker-compose down -v
```

### 服务端口说明
| 服务 | 端口 | 说明 |
|------|------|------|
| Web应用 | 8000 | FastAPI主服务 |
| PostgreSQL | 5432 | 数据库 |
| Redis | 6379 | 缓存/消息队列 |
| Nginx | 80/443 | 反向代理(可选) |

---

## 📖 功能说明

### 1. 投资经理功能
- **创建指令**: 填写标的、数量、价格等信息
- **查看自己的指令**: 实时查看状态变化
- **撤销指令**: 撤销未执行的指令
- **紧急程度**: 标记HIGH/NORMAL/LOW
- **备注说明**: 添加额外信息

### 2. 交易员功能
- **接收指令推送**: WebSocket实时接收
- **浏览器通知**: 新指令桌面通知+音频提醒
- **回执操作**:
  - 已接收(RECEIVED)
  - 执行中(IN_PROGRESS)
  - 执行完成(COMPLETED) - 可填写成交价格/数量
  - 执行失败(FAILED)
- **离线消息**: 重新连接后接收离线期间的指令

### 3. 管理员功能
- **查看所有指令**: 全局视图
- **审计日志**: 查看操作历史
- **系统监控**: 实时消息推送

---

## 🔌 API文档

### 认证接口
```http
POST /auth/token
Content-Type: application/x-www-form-urlencoded

username=im1&password=test123

# 响应
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

### 指令操作接口

#### 创建指令(投资经理)
```http
POST /instructions
Authorization: Bearer {token}
Content-Type: application/json

{
  "title": "买入浦发银行",
  "asset_code": "600000.SH",
  "side": "BUY",
  "qty": 100,
  "price_type": "LIMIT",
  "limit_price": 10.50,
  "urgency": "HIGH",
  "remarks": "仓位调整"
}
```

#### 撤销指令(投资经理)
```http
POST /instructions/{id}/cancel
Authorization: Bearer {token}
```

#### 交易员回执
```http
POST /instructions/{id}/ack
Authorization: Bearer {token}
Content-Type: application/json

{
  "ack_type": "COMPLETED",
  "execution_price": 10.48,
  "execution_qty": 100,
  "execution_time": "2025-11-04T14:30:00Z"
}
```

#### 查看指令日志
```http
GET /instructions/{id}/logs
Authorization: Bearer {token}
```

#### 查看回执记录
```http
GET /instructions/{id}/acknowledgments
Authorization: Bearer {token}
```

### WebSocket连接
```javascript
const ws = new WebSocket('ws://localhost:8000/ws?token={jwt_token}');

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  console.log('收到消息:', msg.type, msg.data);
};

// 消息类型:
// - instruction.created: 新指令
// - instruction.acknowledged: 回执
// - instruction.cancelled: 撤销
```

---

## 🛠️ 运维指南

### 日志管理
日志文件位置: `backend/logs/`
- `app.log`: 应用日志(自动轮转,最多5个10MB文件)
- `error.log`: 错误日志

查看实时日志:
```powershell
# 本地
Get-Content -Path logs/app.log -Wait -Tail 50

# Docker
docker-compose logs -f web
```

### 数据库备份
```powershell
# PostgreSQL备份
docker-compose exec db pg_dump -U trading_user trading_system > backup_$(Get-Date -Format 'yyyyMMdd_HHmmss').sql

# 恢复
docker-compose exec -T db psql -U trading_user trading_system < backup_20251104_120000.sql
```

### 性能监控
访问 http://localhost:8000/docs 查看API性能

### 告警配置
在 `.env` 中配置钉钉Webhook:
```env
ALERT_WEBHOOK_URL=https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN
```

系统将在以下情况发送告警:
- 系统启动/关闭
- 数据库连接失败
- Redis连接失败
- 关键错误

---

## 🔧 数据库迁移(Alembic)

### 初始化Alembic
```powershell
cd backend
alembic init alembic
```

### 创建迁移脚本
```powershell
# 自动生成迁移
alembic revision --autogenerate -m "add new tables"

# 手动创建迁移
alembic revision -m "custom migration"
```

### 执行迁移
```powershell
# 升级到最新版本
alembic upgrade head

# 降级一个版本
alembic downgrade -1

# 查看迁移历史
alembic history
```

---

## 🔐 安全建议

1. **修改默认密码**: 更改 `.env` 中的数据库和Redis密码
2. **使用HTTPS**: 生产环境启用SSL证书
3. **JWT密钥**: 修改 `SECRET_KEY` 为强随机字符串
4. **IP白名单**: 在Nginx配置中限制访问IP
5. **定期备份**: 配置自动备份任务
6. **日志审计**: 定期检查操作日志

---

## 📞 技术支持

如有问题,请查看:
- API文档: http://localhost:8000/docs
- 系统日志: `backend/logs/app.log`
- Docker日志: `docker-compose logs`

---

## 📝 更新日志

### v0.3.0 (2025-11-04)
- ✅ 添加指令日志审计
- ✅ 交易员回执增强
- ✅ 指令撤销功能
- ✅ 浏览器通知+音频提醒
- ✅ PostgreSQL支持
- ✅ Redis集成
- ✅ 日志系统
- ✅ Docker部署

### v0.2.0
- 基础MVP功能
- WebSocket推送
- JWT认证

---

**祝使用愉快! 🎉**
