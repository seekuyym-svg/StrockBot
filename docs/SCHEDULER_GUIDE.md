# 定时信号检查功能说明

## 🎯 功能概述

系统现已支持**自动定时检查ETF信号**，每5分钟自动获取sh.513120和sh.513050的交易信号，并根据信号类型进行不同的处理。

## ⚙️ 工作原理

### 自动执行流程

```
启动 main.py
    ↓
启动API服务 (FastAPI)
    ↓
启动定时任务调度器 (APScheduler)
    ↓
立即执行首次信号检查
    ↓
每隔5分钟自动检查一次
    ↓
根据信号类型处理：
  - BUY/ADD/SELL → 打印到控制台 + 持久化保存
  - WAIT → 仅打印到控制台（不保存）
  - STOP → 打印到控制台 + 持久化保存
```

## 📊 信号处理策略

### 1. 重要信号（BUY/ADD/SELL）

**处理方式:** ✅ 打印 + 💾 持久化

**控制台输出示例:**
```
============================================================
🟢 【重要信号】2026-04-13 15:30:00
============================================================
标的: 港股创新药ETF (sh.513120)
信号: BUY
价格: ¥1.272
涨跌幅: -0.78%
目标份额: 3,934
原因: 初始建仓信号
============================================================
```

**文件保存:**
- 路径: `signal/2026-04-13/sh_513120_153000.json`
- 内容: 完整的信号数据

### 2. 等待信号（WAIT）

**处理方式:** ℹ️ 仅打印（不持久化）

**控制台输出示例:**
```
⏸️  [2026-04-13 15:35:00] 港股创新药ETF(sh.513120): WAIT
   价格: ¥1.272, 涨跌幅: -0.78%
```

**特点:**
- 不占用磁盘空间
- 减少不必要的文件
- 仅在控制台显示，便于实时监控

### 3. 停止信号（STOP）

**处理方式:** 🔴 打印 + 💾 持久化

**控制台输出示例:**
```
🔔 [2026-04-13 15:40:00] 港股创新药ETF(sh.513120): STOP
   价格: ¥1.250, 涨跌幅: -2.50%
   原因: 触发止损条件
```

## 🚀 使用方法

### 方式1: 直接启动（推荐）

```bash
python main.py
```

系统会自动：
1. 启动API服务
2. 启动定时任务（每5分钟检查一次）
3. 立即执行首次信号检查

### 方式2: 自定义检查间隔

如果需要修改检查间隔（例如改为3分钟），可以修改 `main.py` 中的参数：

```python
# 在 main() 函数中
scheduler = start_signal_scheduler(interval_minutes=3)  # 改为3分钟
```

## 📋 控制台输出说明

### 启动时的输出

```
============================================================
ETF链接基金T+0马丁格尔量化交易系统启动
============================================================
交易标的: ['港股创新药ETF(sh.513120)', '中概互联网ETF(sh.513050)']
初始资金: 500000元
加仓次数: 5
...

============================================================
启动定时信号检查任务...
============================================================
✅ 定时任务调度器启动成功

🚀 立即执行首次信号检查...
============================================================
🔄 开始定时信号检查...
============================================================

🟢 【重要信号】2026-04-13 15:25:00
============================================================
标的: 港股创新药ETF (sh.513120)
信号: BUY
...

✅ 定时任务已启动，每5分钟自动检查信号
📅 下次检查时间: 2026-04-13 15:30:00
```

### 运行中的输出

**每5分钟自动输出:**
```
============================================================
🔄 开始定时信号检查...
============================================================

🟢 【重要信号】2026-04-13 15:30:00
============================================================
标的: 港股创新药ETF (sh.513120)
信号: BUY
...

⏸️  [2026-04-13 15:30:01] 中概互联网ETF(sh.513050): WAIT
   价格: ¥1.185, 涨跌幅: -1.90%

✅ 本轮信号检查完成
```

### 停止时的输出

```
🛑 接收到停止信号...
⏹️ 定时任务已停止
👋 系统已退出
```

## 🔍 查看历史信号

### 方法1: 通过API查询

```bash
# 查看今天的信号
curl http://localhost:8080/api/signals/today

# 查看最近7天的历史
curl "http://localhost:8080/api/signals/history?days=7"
```

### 方法2: 直接查看文件

```bash
# 查看今天的信号文件
ls signal/2026-04-13/

# 查看特定信号
cat signal/2026-04-13/sh_513120_153000.json
```

## ⚙️ 配置选项

### 修改检查间隔和交易时间

在 `config.yaml` 文件中修改定时任务配置：

```
# 定时任务配置
scheduler:
  # 信号检查间隔（分钟）
  signal_check_interval: 5
  # 是否在启动时立即执行首次检查
  run_immediately_on_start: true
  # 是否启用定时任务
  enabled: true
  # 交易时间配置（24小时制）
  trading_hours:
    # 交易日（周一到周五：1=周一, 2=周二, ..., 5=周五, 6=周六, 7=周日）
    trading_days: [1, 2, 3, 4, 5]
    # 交易时间段列表（支持多个时间段，如上午和下午）
    sessions:
      - start_time: "09:30"  # 上午开盘
        end_time: "11:30"    # 上午收盘
      - start_time: "13:00"  # 下午开盘
        end_time: "15:00"    # 下午收盘
```

**配置说明：**
- `signal_check_interval`: 检查间隔时间（分钟），默认5分钟
- `run_immediately_on_start`: 启动时是否立即执行首次检查，默认true
- `enabled`: 是否启用定时任务，默认true
- `trading_hours.trading_days`: 交易日列表，1-7分别代表周一到周日
- `trading_hours.sessions`: 交易时间段列表，支持配置多个时间段
  - `start_time`: 时段开始时间，格式"HH:MM"
  - `end_time`: 时段结束时间，格式"HH:MM"

**智能行为：**
- ✅ **交易时间内**: 检查ETF信号，BUY/SELL信号会持久化保存并发送飞书通知
- ℹ️ **非交易时间**: 仅输出上证指数点数（INFO级别日志）

**A股标准配置（推荐）：**
```yaml
scheduler:
  signal_check_interval: 5
  trading_hours:
    trading_days: [1, 2, 3, 4, 5]  # 周一到周五
    sessions:
      - start_time: "09:30"         # 上午开盘
        end_time: "11:30"           # 上午收盘
      - start_time: "13:00"         # 下午开盘
        end_time: "15:00"           # 下午收盘
```

**其他市场示例：**

港股交易时间（无午休）：
```
scheduler:
  signal_check_interval: 5
  trading_hours:
    trading_days: [1, 2, 3, 4, 5]
    sessions:
      - start_time: "09:30"
        end_time: "16:00"
```

美股交易时间（北京时间）：
```
scheduler:
  signal_check_interval: 10
  trading_hours:
    trading_days: [1, 2, 3, 4, 5]
    sessions:
      - start_time: "21:30"         # 美东9:30 = 北京21:30
        end_time: "04:00"           # 次日凌晨4点（需特殊处理跨天）
```

全天监控（加密货币等）：
```yaml
scheduler:
  signal_check_interval: 5
  trading_hours:
    trading_days: [1, 2, 3, 4, 5, 6, 7]  # 每天
    sessions:
      - start_time: "00:00"
        end_time: "23:59"
```

### 禁用定时任务

如果暂时不需要自动检查功能，可以在 `config.yaml` 中设置：

```
scheduler:
  enabled: false  # 禁用定时任务
```

## 💡 使用场景

### 1. 实时监控

保持程序运行，实时接收信号通知：
- 打开终端运行 `python main.py`
- 观察控制台输出
- 出现BUY/SELL信号时会醒目显示

### 2. 后台运行

在服务器上后台运行：
```bash
# Linux/Mac
nohup python main.py > stockbot.log 2>&1 &

# Windows (使用PowerShell)
Start-Process python -ArgumentList "main.py" -WindowStyle Hidden
```

### 3. 日志记录

将输出重定向到日志文件：
```bash
python main.py > logs/$(date +%Y%m%d).log 2>&1
```

### 4. 配合告警系统

可以通过解析日志文件实现邮件/短信告警：
```python
# 监控日志文件，发现BUY/SELL信号时发送通知
import re

def monitor_log_file(log_path):
    with open(log_path, 'r') as f:
        for line in f:
            if '【重要信号】' in line:
                send_alert(line)
```

## 🎨 信号图标说明

| 图标 | 含义 | 信号类型 | 处理方式 |
|------|------|----------|----------|
| 🟢 | 买入信号 | BUY | 打印 + 持久化 |
| 🔵 | 加仓信号 | ADD | 打印 + 持久化 |
| 🔴 | 卖出信号 | SELL | 打印 + 持久化 |
| ⏸️ | 观望信号 | WAIT | 仅打印 |
| 🔔 | 其他信号 | STOP等 | 打印 + 持久化 |

## ⚠️ 注意事项

### 1. 资源占用

- **内存**: 约50-100MB
- **CPU**: 每次检查约0.5-1秒
- **网络**: 每次检查约2-4次API请求
- **磁盘**: 每天约10-50个信号文件（取决于信号频率）

### 2. 网络要求

- 需要稳定的网络连接
- 建议在网络良好的环境下运行
- 如遇网络故障，会自动重试

### 3. 交易时间

- **最佳运行时间**: 交易日 9:30-15:00
- 非交易时间也可以运行，但数据可能不准确
- 建议在交易时间段内重点关注

### 4. 磁盘空间

- WAIT信号不会保存，节省空间
- 建议定期清理旧数据（如30天前）
- 可以使用脚本自动清理

## 🔧 故障排查

### 问题1: 定时任务未启动

**现象:** 启动后没有看到"定时任务已启动"的提示

**解决方法:**
```python
# 检查 main.py 中是否有以下代码
scheduler = start_signal_scheduler(interval_minutes=5)
```

### 问题2: 信号检查失败

**现象:** 控制台显示"未获取到信号"

**可能原因:**
- 网络问题
- API限流
- 非交易时间

**解决方法:**
- 检查网络连接
- 稍后重试
- 查看错误日志

### 问题3: 文件未生成

**现象:** 有BUY/SELL信号但没有生成文件

**可能原因:**
- 目录权限不足
- 磁盘空间不足

**解决方法:**
```bash
# 检查目录权限
ls -la signal/

# 检查磁盘空间
df -h
```

## 📈 最佳实践

### 1. 定期清理旧数据

创建清理脚本 `cleanup_signals.py`:

```python
from pathlib import Path
import shutil
from datetime import datetime, timedelta

def cleanup_old_signals(keep_days=30):
    """清理30天前的信号数据"""
    base_dir = Path("signal")
    cutoff_date = datetime.now() - timedelta(days=keep_days)
    
    deleted_count = 0
    for date_dir in base_dir.iterdir():
        if date_dir.is_dir():
            try:
                dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d")
                if dir_date < cutoff_date:
                    shutil.rmtree(date_dir)
                    print(f"已删除: {date_dir}")
                    deleted_count += 1
            except ValueError:
                pass
    
    print(f"共删除 {deleted_count} 个日期目录")

if __name__ == "__main__":
    cleanup_old_signals()
```

### 2. 设置日志轮转

修改日志配置，避免日志文件过大：

```python
from loguru import logger

# 配置日志轮转
logger.add(
    "logs/stockbot_{time:YYYY-MM-DD}.log",
    rotation="00:00",  # 每天午夜轮转
    retention="30 days",  # 保留30天
    compression="zip"  # 压缩旧日志
)
```

### 3. 监控运行状态

创建健康检查脚本：

```python
import requests
from datetime import datetime

def check_system_health():
    """检查系统健康状态"""
    try:
        # 检查API服务
        response = requests.get("http://localhost:8080/api/health", timeout=5)
        if response.status_code == 200:
            print(f"✅ API服务正常 ({datetime.now()})")
        else:
            print(f"❌ API服务异常: {response.status_code}")
    except Exception as e:
        print(f"❌ API服务不可达: {e}")

if __name__ == "__main__":
    check_system_health()
```

## 📝 相关文件

- **核心实现**: `src/utils/scheduler.py`
- **主程序**: `main.py`
- **测试脚本**: `test_scheduler.py`
- **存储目录**: `signal/`

---

**功能版本**: v1.0.0  
**更新日期**: 2026-04-13  
**作者**: AI Assistant








