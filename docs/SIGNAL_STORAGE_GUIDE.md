# 信号数据持久化功能说明

## 🎯 功能概述

系统现已支持自动将交易信号数据持久化保存到本地文件系统，按日期分类存储，便于后续分析和回溯。

## 📁 存储结构

```
signal/                          # 信号数据根目录
├── 2026-04-13/                 # 按日期分类
│   ├── sh_513120_152343.json  # 单个信号文件（时:分:秒）
│   ├── sh_513050_152345.json
│   └── all_signals_152350.json # 所有信号汇总文件
├── 2026-04-14/
│   ├── ...
└── ...
```

### 文件命名规则

**单个信号文件:**
```
{symbol}_{HHMMSS}.json
示例: sh_513120_152343.json
```

**汇总信号文件:**
```
all_signals_{HHMMSS}.json
示例: all_signals_152350.json
```

## 🔧 自动触发机制

### 1. 获取所有信号时自动保存

**API端点:** `GET /api/signals`

**行为:**
- 获取所有ETF的交易信号
- 自动保存到 `signal/YYYY-MM-DD/all_signals_HHMMSS.json`
- 返回结果中包含存储路径信息

**响应示例:**
```json
{
  "code": 0,
  "message": "success",
  "data": [...],
  "storage": {
    "saved": true,
    "path": "signal\\2026-04-13\\all_signals_152350.json"
  }
}
```

### 2. 获取单个信号时自动保存

**API端点:** `GET /api/signal/{symbol}`

**行为:**
- 获取指定ETF的交易信号
- 自动保存到 `signal/YYYY-MM-DD/sh_XXXXXX_HHMMSS.json`
- 返回结果中包含存储路径信息

**响应示例:**
```json
{
  "code": 0,
  "message": "success",
  "data": {...},
  "storage": {
    "saved": true,
    "path": "signal\\2026-04-13\\sh_513120_152343.json"
  }
}
```

## 📊 新增API端点

### 1. 查询历史信号记录

**端点:** `GET /api/signals/history?days=7`

**参数:**
- `days`: 查询最近几天的数据（默认7天）

**响应示例:**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "count": 15,
    "days": 7,
    "records": [
      {
        "file": "signal\\2026-04-13\\all_signals_152350.json",
        "filename": "all_signals_152350.json",
        "date": "2026-04-13",
        "data": {...}
      }
    ]
  }
}
```

### 2. 查询今日信号记录

**端点:** `GET /api/signals/today`

**响应示例:**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "date": "2026-04-13",
    "count": 3,
    "records": [
      {
        "file": "signal\\2026-04-13\\sh_513120_152343.json",
        "filename": "sh_513120_152343.json",
        "data": {...}
      }
    ]
  }
}
```

## 💾 数据格式

### 单个信号文件格式

```json
{
  "symbol": "sh.513120",
  "name": "港股创新药ETF",
  "signal_type": "BUY",
  "price": 1.272,
  "change_pct": -0.78,
  "reason": "初始建仓信号",
  "target_shares": 3934,
  "position_count": 0,
  "avg_cost": 0,
  "position_value": 0,
  "saved_at": "2026-04-13T15:23:43.471139"
}
```

### 汇总信号文件格式

```json
{
  "saved_at": "2026-04-13T15:23:50.123456",
  "date": "2026-04-13",
  "count": 2,
  "signals": [
    {
      "symbol": "sh.513120",
      "name": "港股创新药ETF",
      "signal_type": "BUY",
      ...
    },
    {
      "symbol": "sh.513050",
      "name": "中概互联网ETF",
      "signal_type": "WAIT",
      ...
    }
  ]
}
```

## 🛠️ 使用场景

### 1. 日常监控

```bash
# 查看今天的信号
curl http://localhost:8080/api/signals/today

# 查看最近7天的历史
curl http://localhost:8080/api/signals/history?days=7
```

### 2. 数据分析

```python
import json
from pathlib import Path

# 读取某天的所有信号
signal_dir = Path("signal/2026-04-13")
for file in signal_dir.glob("*.json"):
    with open(file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        print(f"{file.name}: {data}")
```

### 3. 策略回测

```python
# 收集历史信号进行回测分析
from datetime import datetime, timedelta

def collect_historical_signals(days=30):
    """收集最近N天的信号数据"""
    signals = []
    base_dir = Path("signal")
    
    for i in range(days):
        date = datetime.now() - timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        date_dir = base_dir / date_str
        
        if date_dir.exists():
            for file in date_dir.glob("all_signals_*.json"):
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    signals.extend(data.get('signals', []))
    
    return signals
```

### 4. 信号统计

```python
# 统计信号类型分布
from collections import Counter

def analyze_signal_distribution(days=7):
    """分析信号类型分布"""
    signals = collect_historical_signals(days)
    types = [s['signal_type'] for s in signals]
    distribution = Counter(types)
    
    print("信号类型分布:")
    for signal_type, count in distribution.items():
        print(f"  {signal_type}: {count}次")
```

## ⚙️ 配置选项

信号存储模块位于 `src/utils/signal_storage.py`，可通过修改以下参数自定义行为：

### 修改存储目录

```python
# 在 main.py 或配置文件中
from src.utils.signal_storage import SignalStorage

# 自定义存储目录
storage = SignalStorage(base_dir="my_signals")
```

### 手动保存信号

```python
from src.utils.signal_storage import save_signal_to_file, save_all_signals_to_file

# 保存单个信号
save_signal_to_file("sh.513120", signal_data)

# 保存所有信号
save_all_signals_to_file(signals_list)
```

## 🔍 故障排查

### 问题1: 信号文件未生成

**可能原因:**
- 目录权限不足
- 磁盘空间不足
- API调用失败

**解决方法:**
```bash
# 检查目录是否存在
ls -la signal/

# 检查磁盘空间
df -h

# 查看日志
tail -f logs/app.log
```

### 问题2: 文件内容不完整

**可能原因:**
- JSON序列化错误
- 数据字段缺失

**解决方法:**
```python
# 验证JSON格式
import json
with open("signal/2026-04-13/test.json", 'r') as f:
    try:
        data = json.load(f)
        print("JSON格式正确")
    except json.JSONDecodeError as e:
        print(f"JSON格式错误: {e}")
```

### 问题3: 历史查询返回空

**可能原因:**
- 指定天数内无数据
- 日期目录不存在

**解决方法:**
```bash
# 查看所有日期目录
ls signal/

# 检查特定日期的文件
ls signal/2026-04-13/
```

## 📈 最佳实践

### 1. 定期清理旧数据

```python
# 清理30天前的数据
import shutil
from datetime import datetime, timedelta

def cleanup_old_signals(keep_days=30):
    """清理旧信号数据"""
    base_dir = Path("signal")
    cutoff_date = datetime.now() - timedelta(days=keep_days)
    
    for date_dir in base_dir.iterdir():
        if date_dir.is_dir():
            try:
                dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d")
                if dir_date < cutoff_date:
                    shutil.rmtree(date_dir)
                    print(f"已删除: {date_dir}")
            except ValueError:
                pass
```

### 2. 数据备份

```bash
# 压缩备份信号数据
tar -czf signals_backup_$(date +%Y%m%d).tar.gz signal/

# 或使用Python
import zipfile
from pathlib import Path

def backup_signals():
    """备份信号数据"""
    backup_file = f"signal_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    
    with zipfile.ZipFile(backup_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file in Path("signal").rglob("*.json"):
            zipf.write(file)
    
    print(f"备份完成: {backup_file}")
```

### 3. 数据导出

```python
import pandas as pd
from pathlib import Path

def export_to_csv(days=30):
    """导出信号数据到CSV"""
    signals = collect_historical_signals(days)
    
    df = pd.DataFrame(signals)
    df.to_csv(f"signals_export_{datetime.now().strftime('%Y%m%d')}.csv", 
              index=False, encoding='utf-8-sig')
    
    print(f"导出完成: {len(df)}条记录")
```

## 🎓 技术实现

### 核心类: SignalStorage

**主要方法:**
- `save_signal(symbol, signal_data)`: 保存单个信号
- `save_all_signals(signals_data)`: 保存所有信号
- `get_today_signals()`: 获取今日信号文件列表
- `get_signal_history(days)`: 获取历史信号文件列表
- `load_signal_file(filepath)`: 加载信号文件

### 设计特点

1. **单例模式**: 全局唯一实例，避免重复创建
2. **自动建目录**: 按需创建日期目录
3. **时间戳命名**: 避免文件名冲突
4. **UTF-8编码**: 支持中文内容
5. **异常处理**: 完善的错误捕获和日志记录

## 📝 相关文件

- **核心实现**: `src/utils/signal_storage.py`
- **API路由**: `main.py` (第70-120行)
- **测试脚本**: `test_signal_storage.py`
- **存储目录**: `signal/`

---

**功能版本**: v1.0.0  
**更新日期**: 2026-04-13  
**作者**: AI Assistant


