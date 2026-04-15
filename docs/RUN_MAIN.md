# 🚀 运行 StockBot 主程序指南

## ✅ 前置条件检查

在运行主程序之前，请确认已完成以下配置：

### 1. 依赖安装 ✅
```bash
pip install -r requirements.txt
```

**核心依赖：**
- ✅ baostock - A 股数据源（完全免费）
- ✅ fastapi >=0.104.0 - Web 框架
- ✅ uvicorn - ASGI 服务器
- ✅ pandas - 数据处理
- ✅ pydantic - 数据校验
- ✅ loguru - 日志记录

### 2. 测试验证 ✅
所有测试已通过：
```bash
python test_baostock.py
```

**测试结果：**
- ✅ BaoStock 安装和登录
- ✅ 股票基本信息获取
- ✅ 日 K 线数据获取
- ✅ 实时行情获取
- ✅ 上证指数获取
- ✅ 集成数据提供者

---

## 🎯 启动主程序

### 方法一：直接运行（推荐）

```bash
python main.py
```

**预期输出：**
```
2026-03-19 23:XX:XX | INFO     | 加载配置文件：config.yaml
2026-03-19 23:XX:XX | INFO     | 初始化策略引擎...
2026-03-19 23:XX:XX | INFO     | 启动 FastAPI 服务...
INFO:     Started server process [XXXX]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

### 方法二：使用 Uvicorn 直接启动

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**参数说明：**
- `--host 0.0.0.0` - 允许外部访问
- `--port 8000` - 指定端口
- `--reload` - 代码变更自动重启（开发环境）

---

## 📡 API 接口

服务启动后，可以访问以下接口：

### 1. API 文档（推荐）
```
http://127.0.0.1:8000/docs
```
交互式 API 测试界面（Swagger UI）

### 2. 备用文档
```
http://127.0.0.1:8000/redoc
```
ReDoc 文档界面

### 3. 健康检查
```bash
curl http://127.0.0.1:8000/health
```

### 4. 获取市场数据
```bash
# 获取贵州茅台数据
curl http://127.0.0.1:8000/api/market/600519

# 获取盐湖股份数据
curl http://127.0.0.1:8000/api/market/000792

# 获取中国海油数据
curl http://127.0.0.1:8000/api/market/600938
```

### 5. 获取交易信号
```bash
# 获取所有监控股票的信号
curl http://127.0.0.1:8000/api/signals

# 获取单只股票信号
curl http://127.0.0.1:8000/api/signals/600519
```

### 6. 获取上证指数
```bash
curl http://127.0.0.1:8000/api/sh_index
```

---

## 🔍 验证服务正常

### 浏览器访问

打开浏览器访问：
```
http://127.0.0.1:8000/docs
```

你应该看到完整的 API 文档界面，包含以下接口：
- `GET /health` - 健康检查
- `GET /api/market/{symbol}` - 获取市场数据
- `GET /api/signals` - 获取交易信号
- `GET /api/signals/{symbol}` - 获取单只股票信号
- `GET /api/sh_index` - 获取上证指数

### 命令行测试

```bash
# 测试健康检查
curl http://127.0.0.1:8000/health

# 预期响应：
# {"status":"healthy","timestamp":"2026-03-19T23:XX:XX"}
```

```bash
# 测试获取贵州茅台数据
curl http://127.0.0.1:8000/api/market/600519

# 预期响应（示例）：
# {
#   "symbol": "600519",
#   "name": "贵州茅台",
#   "current_price": 1452.87,
#   "change_pct": 1.23,
#   "ema_20": 1430.50,
#   "rsi": 55.2,
#   ...
# }
```

---

## 🛠️ 常见问题

### 问题 1: 端口被占用
```
Error: [Errno 10048] error while attempting to bind on address ('0.0.0.0', 8000)
```

**解决方案：**
```bash
# 方案 1: 更换端口
uvicorn main:app --port 8001

# 方案 2: 查找并关闭占用进程
netstat -ano | findstr :8000
taskkill /F /PID <进程 ID>
```

### 问题 2: BaoStock 连接失败
```
❌ 登录失败：网络连接错误
```

**解决方案：**
1. 检查网络连接
2. 访问 http://baostock.com/ 确认服务正常
3. 检查防火墙设置
4. 稍后重试

### 问题 3: 配置文件缺失
```
FileNotFoundError: config.yaml not found
```

**解决方案：**
```bash
# 复制示例配置
copy config.example.yaml config.yaml

# 或创建基本配置
cat > config.yaml << EOF
symbols:
  - code: "600519"
    name: "贵州茅台"
    enabled: true
  - code: "000792"
    name: "盐湖股份"
    enabled: true
EOF
```

### 问题 4: 模块导入错误
```
ModuleNotFoundError: No module named 'xxx'
```

**解决方案：**
```bash
# 重新安装依赖
pip install -r requirements.txt --upgrade

# 或在虚拟环境中安装
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

---

## 📊 性能优化建议

### 1. 使用生产级服务器

开发环境使用 uvicorn 足够，生产环境建议使用 gunicorn + uvicorn workers：

```bash
pip install gunicorn

gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### 2. 启用 HTTPS

生产环境必须启用 HTTPS：

```bash
# 使用 Let's Encrypt 证书
uvicorn main:app --ssl-keyfile=./key.pem --ssl-certfile=./cert.pem
```

### 3. 添加认证

目前 API 无认证，生产环境应添加：

```python
# 在 main.py 中添加
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

@app.get("/api/protected")
async def protected_route(credentials: HTTPAuthorizationCredentials = Depends(security)):
    # 验证 token
    pass
```

### 4. 数据库优化

当前使用 SQLite，高并发场景建议切换到 PostgreSQL：

```python
# 修改 src/utils/database.py
DATABASE_URL = "postgresql://user:password@localhost/stockbot"
```

---

## 🎉 成功标志

当你看到以下输出时，说明系统运行正常：

```
✅ 终端显示 "Uvicorn running on http://127.0.0.1:8000"
✅ 浏览器可以访问 http://127.0.0.1:8000/docs
✅ API 测试返回正确的股票数据
✅ 日志正常记录，无 ERROR 级别错误
```

---

## 📝 下一步

系统正常运行后，可以：

1. **测试交易信号生成**
   ```bash
   curl http://127.0.0.1:8000/api/signals
   ```

2. **配置更多股票**
   编辑 `config.yaml`，添加更多监控标的

3. **回测历史表现**
   ```bash
   curl http://127.0.0.1:8000/api/backtest?symbol=600519&start=2025-01-01&end=2026-03-19
   ```

4. **部署到生产环境**
   - 使用 Docker 容器化部署
   - 配置 Nginx 反向代理
   - 设置 systemd 服务自动启动

---

*文档更新时间：2026-03-19*  
*版本：v1.0.0*
