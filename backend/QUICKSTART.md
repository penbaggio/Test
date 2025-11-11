# 🚀 快速启动指南

## ⚡ 5分钟快速体验

### 方式一：本地SQLite版本（最简单）

```powershell
# 1. 进入后端目录
cd backend

# 2. 启动服务（会自动创建SQLite数据库和测试账户）
uvicorn app.main:app --reload --port 8000

# 3. 打开浏览器访问增强版界面
# http://localhost:8000/app/index_enhanced.html

# 4. 使用测试账户登录
# 投资经理: im1 / test123
# 交易员: trader1 / test123
```

**测试流程：**
1. 打开两个浏览器窗口
2. 窗口A：使用 `trader1` 登录，点击"连接推送"
3. 窗口B：使用 `im1` 登录，创建一条新指令
4. 观察窗口A：会立即收到通知+音频提醒
5. 在窗口A中点击"执行完成"按钮，填写成交价格和数量
6. 观察窗口B：指令状态实时更新

---

## 🐳 Docker完整版（推荐生产环境）

### 前置要求
- 已安装 Docker Desktop for Windows
- 已安装 Docker Compose

### 启动步骤

```powershell
# 1. 进入后端目录
cd backend

# 2. 创建环境变量文件
Copy-Item .env.example .env

# 3. 一键启动所有服务（PostgreSQL + Redis + FastAPI）
docker-compose up -d --build

# 4. 查看启动日志
docker-compose logs -f web

# 5. 等待所有服务启动完成（约30秒）
# 看到 "✅ 系统启动完成" 即可

# 6. 访问系统
# http://localhost:8000/app/index_enhanced.html
```

### 验证服务状态

```powershell
# 查看所有容器状态
docker-compose ps

# 应该看到3个容器都是 "Up" 状态:
# - trading_db (PostgreSQL)
# - trading_redis (Redis)
# - trading_web (FastAPI)
```

---

## 🧪 运行自动化测试

```powershell
# 确保系统已启动
python test_system.py

# 会自动测试:
# ✅ 用户登录
# ✅ 创建指令
# ✅ 查询指令
# ✅ 交易员回执
# ✅ 查看日志
# ✅ 撤销指令
```

---

## 📱 功能演示路径

### 投资经理工作流
1. 登录系统 (im1 / test123)
2. 填写指令信息（标的、数量、价格等）
3. 选择紧急程度（普通/紧急/不急）
4. 添加备注说明
5. 提交指令 → 自动推送给所有交易员
6. 查看指令状态更新
7. 如需撤销，点击"撤销"按钮

### 交易员工作流
1. 登录系统 (trader1 / test123)
2. 点击"连接推送"按钮
3. 允许浏览器通知权限（会弹出提示）
4. 等待新指令到达（会有桌面通知+音频提醒）
5. 点击"已接收"确认收到指令
6. 点击"执行中"开始执行
7. 执行完成后点击"执行完成"，填写：
   - 实际成交价格
   - 实际成交数量
8. 如果执行失败，点击"执行失败"并说明原因

### 管理员工作流
1. 登录系统 (admin1 / test123)
2. 点击"连接推送"
3. 查看所有历史指令
4. 监控系统实时状态

---

## 🔍 查看系统状态

### 日志文件位置
```
backend/logs/
├── app.log     # 应用日志
└── error.log   # 错误日志
```

### 查看实时日志
```powershell
# 本地模式
Get-Content logs/app.log -Wait -Tail 50

# Docker模式
docker-compose logs -f web
```

### API文档
访问 http://localhost:8000/docs 查看完整API文档（Swagger UI）

---

## 🛑 停止服务

### 本地模式
按 `Ctrl + C` 停止 uvicorn

### Docker模式
```powershell
# 停止所有服务
docker-compose stop

# 完全删除（包括数据）
docker-compose down -v
```

---

## ❓ 常见问题

### Q: 启动失败，提示端口被占用？
**A:** 修改端口号
```powershell
# 本地模式
uvicorn app.main:app --reload --port 8001

# Docker模式: 修改 docker-compose.yml 中的端口映射
# ports:
#   - "8001:8000"
```

### Q: Redis连接失败？
**A:** Redis是可选的，系统会自动降级
```
⚠️ Redis连接失败: ...
系统将继续运行，但不支持离线消息功能
```

### Q: 如何重置数据库？
**A:** 
```powershell
# SQLite模式：删除数据文件
Remove-Item data.db

# Docker模式：重建数据卷
docker-compose down -v
docker-compose up -d
```

### Q: WebSocket连接失败？
**A:** 检查浏览器控制台，确保：
1. 已成功登录
2. Token有效
3. 网络连接正常
4. 浏览器支持WebSocket

---

## 📞 获取帮助

- **查看完整文档**: [README.md](README.md)
- **部署指南**: [DEPLOYMENT.md](DEPLOYMENT.md)
- **API文档**: http://localhost:8000/docs

---

**祝使用愉快！** 🎉
