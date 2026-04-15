# 时区问题修复说明

## ❌ 问题描述

运行时出现以下错误：

```python
TypeError: can't subtract offset-naive and offset-aware datetimes
```

**错误位置**: `src/utils/scheduler.py` 第386行

**错误原因**: 
- `datetime.now()` 返回的是**无时区信息的时间对象**（naive datetime）
- APScheduler 的 `job.next_run_time` 是**带时区信息的时间对象**（aware datetime）
- Python不允许直接对这两种类型进行减法运算

## ✅ 解决方案

### 修改前（有问题）

```python
def _scheduled_check_with_dynamic_interval(self):
    now = datetime.now()  # ❌ naive datetime，无时区信息
    
    last_job = self.scheduler.get_job('signal_check_job')
    if last_job and last_job.next_run_time:
        time_since_last_check = (now - last_job.next_run_time).total_seconds() / 60
        # ❌ TypeError: 不能减去 aware 和 naive datetime
```

### 修改后（已修复）

```python
def _scheduled_check_with_dynamic_interval(self):
    from datetime import timezone
    
    now = datetime.now(timezone.utc)  # ✅ aware datetime，带UTC时区
    
    last_job = self.scheduler.get_job('signal_check_job')
    if last_job and last_job.next_run_time:
        next_run = last_job.next_run_time
        if next_run.tzinfo is None:
            # 如果next_run不带时区，假设为UTC
            next_run = next_run.replace(tzinfo=timezone.utc)
        
        time_since_last_check = (now - next_run).total_seconds() / 60
        # ✅ 两者都是aware datetime，可以正常计算
```

## 🔧 技术要点

### 1. Naive vs Aware Datetime

**Naive Datetime（无时区）:**
```python
from datetime import datetime

dt_naive = datetime.now()
print(dt_naive.tzinfo)  # None
```

**Aware Datetime（带时区）:**
```python
from datetime import datetime, timezone

dt_aware = datetime.now(timezone.utc)
print(dt_aware.tzinfo)  # UTC
```

### 2. APScheduler的行为

APScheduler 默认使用**带时区的时间对象**来管理任务调度：
- `job.next_run_time` 通常是 aware datetime
- 时区取决于调度器的配置（默认为UTC或本地时区）

### 3. 最佳实践

**原则**: 在进行时间计算时，确保所有datetime对象都具有相同的时区处理方式。

**推荐做法**:
```python
# 方法1: 统一使用UTC（推荐）
from datetime import datetime, timezone

now = datetime.now(timezone.utc)
next_run = job.next_run_time
if next_run.tzinfo is None:
    next_run = next_run.replace(tzinfo=timezone.utc)

diff = (now - next_run).total_seconds()
```

**方法2: 统一转换为本地时区**
```python
from datetime import datetime
import pytz

local_tz = pytz.timezone('Asia/Shanghai')
now = datetime.now(local_tz)
next_run = job.next_run_time.astimezone(local_tz)

diff = (now - next_run).total_seconds()
```

## 📝 相关知识点

### Python时区处理演进

**Python 3.9之前:**
```python
# 需要使用第三方库
import pytz
dt = datetime.now(pytz.UTC)
```

**Python 3.9+:**
```python
# 内置timezone支持
from datetime import datetime, timezone
dt = datetime.now(timezone.utc)
```

**Python 3.11+:**
```python
# 更简洁的ZoneInfo
from datetime import datetime, zoneinfo
dt = datetime.now(zoneinfo.ZoneInfo("Asia/Shanghai"))
```

### 常见错误场景

1. **混合使用时区**:
   ```python
   # ❌ 错误
   dt1 = datetime.now()  # naive
   dt2 = datetime.now(timezone.utc)  # aware
   diff = dt2 - dt1  # TypeError!
   ```

2. **数据库存储**:
   ```python
   # ❌ 存储naive datetime到数据库
   record.created_at = datetime.now()
   
   # ✅ 存储aware datetime
   record.created_at = datetime.now(timezone.utc)
   ```

3. **JSON序列化**:
   ```python
   # aware datetime序列化时需要特殊处理
   import json
   from datetime import datetime, timezone
   
   data = {"time": datetime.now(timezone.utc)}
   json.dumps(data, default=str)  # 转换为ISO格式字符串
   ```

## 🎯 预防措施

### 1. 代码审查检查点

在涉及时间计算的代码中，检查：
- [ ] 所有datetime对象是否都有明确的时区
- [ ] 是否混用了naive和aware datetime
- [ ] 时间比较/减法操作是否安全

### 2. 单元测试覆盖

```python
def test_timezone_handling():
    """测试时区处理是否正确"""
    from datetime import datetime, timezone
    
    # 模拟APScheduler的行为
    next_run = datetime.now(timezone.utc)
    
    # 测试当前实现
    now = datetime.now(timezone.utc)
    diff = (now - next_run).total_seconds()
    
    assert isinstance(diff, float)
    assert diff >= 0
```

### 3. 日志记录

在关键时间点添加日志，便于排查时区问题：

```python
logger.debug(f"当前时间: {now} (时区: {now.tzinfo})")
logger.debug(f"下次运行: {next_run} (时区: {next_run.tzinfo})")
```

## 📚 参考资料

- [Python官方文档 - datetime](https://docs.python.org/3/library/datetime.html)
- [PEP 615 - Support for the IANA Time Zone Database](https://peps.python.org/pep-0615/)
- [APScheduler时区配置](https://apscheduler.readthedocs.io/en/latest/userguide.html#configuring-the-scheduler)

---

**修复版本**: v2.2.1  
**修复日期**: 2026-04-15  
**问题类型**: 时区兼容性错误
