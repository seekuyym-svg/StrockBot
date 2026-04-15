# 动态间隔配置未生效问题修复

## ❌ 问题描述

**用户反馈：**
> "我配置的是交易时间1.5分钟检查一次信号，非交易时间10分钟检查打印一次上证指数，但是我启动main之后，显示都是5分钟，不符合预期。"

**现象：**
- 配置文件 `config.yaml` 中设置了：
  ```yaml
  trading_check_interval: 1.5
  non_trading_check_interval: 10
  signal_check_interval: 5
  ```
- 但启动后日志显示：
  ```
  信号调度器已初始化
    交易时间检查间隔: 5分钟  # ❌ 应该是1.5分钟
    非交易时间检查间隔: 5分钟  # ❌ 应该是10分钟
  ```

## 🔍 问题分析

### 根本原因

在 [main.py](file://e:\LearnPY\Projects\StockBot\main.py) 第309-311行，调用 [start_signal_scheduler()](file://e:\LearnPY\Projects\StockBot\src\utils\scheduler.py#L432-L440) 时传递了固定参数：

```python
scheduler = start_signal_scheduler(
    interval_minutes=scheduler_config.signal_check_interval  # ❌ 传递了5
)
```

### 执行流程

1. **main.py 调用**:
   ```python
   start_signal_scheduler(interval_minutes=5)
   ```

2. **scheduler.py 接收**:
   ```python
   def start_signal_scheduler(interval_minutes=5):  # 默认值也是5
       scheduler = get_signal_scheduler(interval_minutes)
       scheduler.start()
   ```

3. **SignalScheduler 初始化**:
   ```python
   def __init__(self, interval_minutes=None):
       if interval_minutes is not None:  # ✅ 条件为True（值为5）
           # 触发兼容旧配置逻辑
           self.trading_check_interval = interval_minutes  # 设置为5
           self.non_trading_check_interval = interval_minutes  # 设置为5
       else:
           # 新配置逻辑（永远不会执行）
           self.trading_check_interval = config.scheduler.trading_check_interval
           self.non_trading_check_interval = config.scheduler.non_trading_check_interval
   ```

### 问题总结

- ✅ 配置文件中正确设置了动态间隔参数
- ❌ 但 [main.py](file://e:\LearnPY\Projects\StockBot\main.py) 仍然使用旧的调用方式，传递了固定的 [signal_check_interval](file://e:\LearnPY\Projects\StockBot\src\utils\config.py#L0-L0)
- ❌ 导致 [SignalScheduler](file://e:\LearnPY\Projects\StockBot\src\utils\scheduler.py#L23-L60) 进入兼容模式，忽略了新的动态间隔配置

## ✅ 解决方案

### 修改1: main.py - 移除固定参数传递

**文件**: [main.py](file://e:\LearnPY\Projects\StockBot\main.py#L307-L318)

**修改前:**
```python
scheduler = start_signal_scheduler(
    interval_minutes=scheduler_config.signal_check_interval
)
logger.info(f"✅ 定时任务调度器启动成功 (间隔: {scheduler_config.signal_check_interval}分钟)")
```

**修改后:**
```python
# 使用新的动态间隔配置，不传递interval_minutes参数
scheduler = start_signal_scheduler()  # 不传参数，从配置读取动态间隔
logger.info(f"✅ 定时任务调度器启动成功")
logger.info(f"   交易时间检查间隔: {scheduler_config.trading_check_interval}分钟")
logger.info(f"   非交易时间检查间隔: {scheduler_config.non_trading_check_interval}分钟")
```

### 修改2: scheduler.py - 调整默认参数

**文件**: [src/utils/scheduler.py](file://e:\LearnPY\Projects\StockBot\src\utils\scheduler.py#L423-L440)

**修改前:**
```python
def get_signal_scheduler(interval_minutes=5):
    """获取信号调度器单例"""
    global _scheduler
    if _scheduler is None:
        _scheduler = SignalScheduler(interval_minutes)
    return _scheduler

def start_signal_scheduler(interval_minutes=5):
    """启动信号调度器"""
    scheduler = get_signal_scheduler(interval_minutes)
    scheduler.start()
    return scheduler
```

**修改后:**
```python
def get_signal_scheduler(interval_minutes=None):
    """获取信号调度器单例
    
    Args:
        interval_minutes: 检查间隔（分钟），默认为None，从配置读取动态间隔
                         如果提供此参数，将使用固定间隔（兼容旧配置）
    """
    global _scheduler
    if _scheduler is None:
        _scheduler = SignalScheduler(interval_minutes)
    return _scheduler

def start_signal_scheduler(interval_minutes=None):
    """启动信号调度器
    
    Args:
        interval_minutes: 检查间隔（分钟），默认为None，从配置读取动态间隔
                         如果提供此参数，将使用固定间隔（兼容旧配置）
    """
    scheduler = get_signal_scheduler(interval_minutes)
    scheduler.start()
    return scheduler
```

## 🎯 修复效果

### 修复前

```
信号调度器已初始化
  交易时间检查间隔: 5分钟  # ❌ 错误
  非交易时间检查间隔: 5分钟  # ❌ 错误
✅ 定时任务调度器启动成功 (间隔: 5分钟)
```

### 修复后

```
信号调度器已初始化
  交易时间检查间隔: 1.5分钟  # ✅ 正确
  非交易时间检查间隔: 10分钟  # ✅ 正确
✅ 定时任务调度器启动成功
   交易时间检查间隔: 1.5分钟
   非交易时间检查间隔: 10分钟
```

## 📊 验证测试

运行系统后，观察以下行为：

### 交易时间（如 10:00-11:30）

```
============================================================
🔄 【交易时间】开始信号检查...
============================================================
（1.5分钟后）
============================================================
🔄 【交易时间】开始信号检查...
============================================================
（1.5分钟后）
============================================================
🔄 【交易时间】开始信号检查...
============================================================
```

**预期**: 每1.5分钟检查一次

### 非交易时间（如 12:00-13:00 午休）

```
⏰ [2026-04-15 12:00:00] 非交易时间 | 上证指数: 3250.50
（10分钟后）
⏰ [2026-04-15 12:10:00] 非交易时间 | 上证指数: 3251.20
（10分钟后）
⏰ [2026-04-15 12:20:00] 非交易时间 | 上证指数: 3249.80
```

**预期**: 每10分钟输出一次指数

## 💡 兼容性说明

### 向后兼容

修复后的代码仍然支持旧的固定间隔配置方式：

**方式1: 使用新的动态间隔（推荐）**
```python
# main.py
scheduler = start_signal_scheduler()  # 不传参数
```

**方式2: 使用旧的固定间隔（兼容）**
```python
# 如果需要临时使用固定间隔
scheduler = start_signal_scheduler(interval_minutes=3)
```

### 配置优先级

1. **优先使用**: 如果调用时传递了 [interval_minutes](file://e:\LearnPY\Projects\StockBot\src\utils\scheduler.py#L0-L0)，使用该固定值
2. **降级使用**: 如果未传递参数，从配置文件读取动态间隔
3. **最终回退**: 如果配置也未设置，使用默认值（1分钟/10分钟）

## ⚠️ 注意事项

### 1. 浮点数间隔

配置中可以使用小数：
```yaml
trading_check_interval: 1.5  # 1分30秒
```

APScheduler 支持浮点数间隔，会自动处理。

### 2. 最小间隔建议

- 交易时间: ≥ 1分钟
- 非交易时间: ≥ 5分钟
- 避免过短间隔导致API限流

### 3. 配置验证

启动后务必检查日志输出，确认间隔配置正确：
```
信号调度器已初始化
  交易时间检查间隔: X分钟  # 确认是否正确
  非交易时间检查间隔: Y分钟  # 确认是否正确
```

## 📝 相关文件

- **配置文件**: [config.yaml](file://e:\LearnPY\Projects\StockBot\config.yaml)
- **主程序**: [main.py](file://e:\LearnPY\Projects\StockBot\main.py)
- **调度器**: [src/utils/scheduler.py](file://e:\LearnPY\Projects\StockBot\src\utils\scheduler.py)
- **配置模型**: [src/utils/config.py](file://e:\LearnPY\Projects\StockBot\src\utils\config.py)

## 🎉 总结

**问题根源**: 
- [main.py](file://e:\LearnPY\Projects\StockBot\main.py) 仍使用旧的调用方式，传递了固定的 [signal_check_interval](file://e:\LearnPY\Projects\StockBot\src\utils\config.py#L0-L0) 参数
- 导致 [SignalScheduler](file://e:\LearnPY\Projects\StockBot\src\utils\scheduler.py#L23-L60) 进入兼容模式，忽略了新的动态间隔配置

**解决方案**:
- 修改 [main.py](file://e:\LearnPY\Projects\StockBot\main.py)，调用时不传递参数
- 修改 [scheduler.py](file://e:\LearnPY\Projects\StockBot\src\utils\scheduler.py)，将默认参数改为 `None`
- 保持向后兼容性，支持两种调用方式

**修复结果**:
- ✅ 交易时间按配置的1.5分钟检查
- ✅ 非交易时间按配置的10分钟检查
- ✅ 日志清晰显示当前使用的间隔
- ✅ 保持向后兼容

---

**修复版本**: v2.2.2  
**修复日期**: 2026-04-15  
**问题类型**: 配置未生效
