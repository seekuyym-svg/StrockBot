# StockBot 快速参考卡片

## 🚀 5分钟快速启动

### 第1步: 设置环境（首次使用）

```bash
# Windows
setup_env.bat

# Linux/Mac
chmod +x setup_env.sh && ./setup_env.sh
```

### 第2步: 激活环境（每次使用前）

```bash
conda activate stockbot-py312
```

### 第3步: 启动服务

```bash
python main.py
```

---

## 📋 常用命令速查

### 环境管理

```bash
# 创建环境
conda env create -f environment.yml -n stockbot-py312

# 激活环境
conda activate stockbot-py312

# 退出环境
conda deactivate

# 删除环境
conda env remove -n stockbot-py312

# 查看Python版本
python --version

# 检查环境一致性
python check_python_version.py
```

### 依赖管理

```bash
# 安装依赖
pip install -r requirements.txt

# 更新依赖
pip install --upgrade -r requirements.txt

# 导出当前依赖
pip freeze > requirements.txt

# 查看已安装的包
pip list
```

### 运行程序

```bash
# 启动主服务
python main.py

# 运行测试
python test_etf_system.py

# 检查信号调度器
python test_scheduler.py

# 测试飞书通知
python test_feishu_notification.py

# 测试交易时间判断
python test_a_share_trading_hours.py
```

### Git操作

```bash
# 查看状态
git status

# 提交更改
git add .
git commit -m "描述你的更改"
git push

# 拉取最新代码
git pull
```

---

## 🔧 配置文件位置

| 文件 | 用途 |
|------|------|
| `config.yaml` | 主配置文件（策略参数、API密钥等） |
| `environment.yml` | Conda环境配置 |
| `.python-version` | Python版本指定 |
| `requirements.txt` | Pip依赖列表 |

---

## 📊 关键端口和地址

- **Web服务**: http://localhost:8000
- **API文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/health

---

## 🐛 故障排查

### 问题1: 找不到conda命令

**解决：**
```bash
# 检查conda是否安装
conda --version

# 如果未安装，下载Miniconda
# https://docs.conda.io/en/latest/miniconda.html
```

### 问题2: Python版本不对

**解决：**
```bash
# 查看当前版本
python --version

# 应该显示 Python 3.12.3
# 如果不是，重新激活环境
conda deactivate
conda activate stockbot-py312
```

### 问题3: 缺少依赖包

**解决：**
```bash
# 重新安装所有依赖
pip install -r requirements.txt --force-reinstall
```

### 问题4: 端口被占用

**解决：**
```bash
# Windows: 查找占用8000端口的进程
netstat -ano | findstr :8000

# Linux/Mac: 
lsof -i :8000

# 杀死进程后重新启动
python main.py
```

### 问题5: 飞书通知不工作

**检查清单：**
- [ ] config.yaml中enabled设为true
- [ ] webhook_url配置正确
- [ ] 网络连接正常
- [ ] 运行测试脚本验证

```bash
python test_feishu_notification.py
```

---

## 📊 BOLL布林带价差功能

### 功能说明

系统会自动计算并显示交易信号价格与BOLL布林带轨道的价差信息：

**买入/加仓信号（BUY/ADD）：**
- 计算买入价与BOLL下轨的价差绝对值
- 计算价差百分比 = (价差 / 买入价格) × 100%
- 显示价格相对BOLL下轨的位置（上方/下方）

**卖出信号（SELL）：**
- 计算卖出价与BOLL上轨的价差绝对值
- 计算价差百分比 = (价差 / 卖出价格) × 100%
- 显示价格相对BOLL上轨的位置（上方/下方）

### 输出示例

```
🟢 【重要信号】2026-04-14 13:45:30
============================================================
标的: 港股创新药ETF (sh.513120)
信号: BUY
价格: ¥1.280
涨跌幅: +0.79%
目标份额: 1,000
平均成本: ¥1.280
📊 BOLL下轨价差: ¥0.030 (2.34%, 上方)
原因: 初始建仓：买入1000份，成本1.280元/份
============================================================
```

### 应用场景

- **判断技术位置**：快速了解当前价格相对布林带的位置
- **跨标的比较**：百分比形式便于不同价格标的之间的比较
- **辅助决策**：结合价差信息优化买卖时机

---

**最后更新**: 2026-04-14  
**版本**: v1.1.0

---

## 📖 文档索引

| 文档 | 说明 |
|------|------|
| [README.md](README.md) | 项目完整文档 |
| [QUICKSTART.md](QUICKSTART.md) | 快速开始指南 |
| [ENVIRONMENT_GUIDE.md](ENVIRONMENT_GUIDE.md) | 环境管理详细指南 |
| [SCHEDULER_GUIDE.md](SCHEDULER_GUIDE.md) | 定时任务配置指南 |
| [FEISHU_NOTIFICATION_GUIDE.md](FEISHU_NOTIFICATION_GUIDE.md) | 飞书通知配置指南 |
| [SIGNAL_STORAGE_GUIDE.md](SIGNAL_STORAGE_GUIDE.md) | 信号存储说明 |

---

## 💡 实用技巧

### 1. 后台运行（Linux）

```bash
# 使用nohup后台运行
nohup python main.py > output.log 2>&1 &

# 查看日志
tail -f output.log

# 停止服务
pkill -f "python main.py"
```

### 2. 使用tmux保持会话

```bash
# 创建新会话
tmux new -s stockbot

# 运行服务
python main.py

# 分离会话: Ctrl+B, D

# 重新连接
tmux attach -t stockbot

# 关闭会话
tmux kill-session -t stockbot
```

### 3. 定期备份配置

```bash
# 备份配置文件
cp config.yaml config.yaml.backup.$(date +%Y%m%d)

# 备份环境配置
conda env export > environment_backup_$(date +%Y%m%d).yml
```

### 4. 查看实时日志

```bash
# 使用loguru的日志文件
tail -f logs/stockbot.log

# 或者查看控制台输出
python main.py 2>&1 | tee output.log
```

---

## 🎯 开发工作流

```bash
# 1. 拉取最新代码
git pull

# 2. 激活环境
conda activate stockbot-py312

# 3. 安装新依赖（如果有）
pip install -r requirements.txt

# 4. 运行测试
python test_etf_system.py

# 5. 启动服务
python main.py

# 6. 访问API文档
# 浏览器打开: http://localhost:8000/docs
```

---

## 📞 获取帮助

1. **查看日志输出** - 大多数问题会在日志中显示
2. **运行诊断脚本** - `python check_python_version.py`
3. **查阅文档** - 查看相关功能的GUIDE文档
4. **检查配置** - 确认config.yaml配置正确
5. **重启服务** - 很多临时问题可以通过重启解决

---

**最后更新**: 2026-04-13  
**版本**: v1.0.0
