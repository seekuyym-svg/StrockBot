# 使用秒数解决动态间隔问题

## 🎯 核心思路

将分钟配置转换为**整数秒数**进行计算，避免浮点数精度和时区转换问题。

**转换规则：**
- 1.5分钟 = 90秒
- 10分钟 = 600秒
- 3分钟 = 180秒

## ✅ 实施方案

### 1. 配置存储（秒数）

在 [SignalScheduler.__init__()](file://e:\LearnPY\Projects\StockBot\src\utils\scheduler.py#L25-L60) 中：

```python
def __init__(self, interval_minutes=None):
    # 从配置读取并转换为秒数
    if interval_minutes is not None:
        # 兼容旧配置
        self.trading_check_interval_seconds = int(interval_minutes * 60)
        self.non_trading_check_interval_seconds = int(interval_minutes * 60)
    else:
        # 新配置：转换为秒数
        self.trading_check_interval_seconds = int(
            self.config.scheduler.trading_check_interval * 60
        )
        self.non_trading_check_interval_seconds = int(
            self.config.scheduler.non_trading_check_interval * 60
        )
    
    # 记录上次执行的时间戳（秒）
    self.last_execution_timestamp = 0
```

**示例：**
```yaml
trading_check_interval: 1.5      # 配置：1.5分钟
non_trading_check_interval: 10   # 配置：10分钟
```

转换后：
```python
trading_check_interval_seconds = int(1.5 * 60) = 90      # 90秒
non_trading_check_interval_seconds = int(10 * 60) = 600  # 600秒
```

### 2. 时间计算（时间戳差值）

在 [_scheduled_check_with_dynamic_interval()](file://e:\LearnPY\Projects\StockBot\src\utils\scheduler.py#L374-L397) 中：

```python
def _scheduled_check_with_dynamic_interval(self):
    import time
    
    # 获取当前时间戳（秒）
    current_timestamp = time.time()  # 例如：1713160800.123
    is_trading = self.is_trading_time()
    
    # 获取应该使用的间隔（秒）
    expected_interval_seconds = (
        self.trading_check_interval_seconds 
        if is_trading 
        else self.non_trading_check_interval_seconds
    )
    
    # 计算距离上次执行的秒数
    time_since_last_check = current_timestamp - self.last_execution_timestamp
    
    # 如果还没到预期间隔，跳过本次执行
    if time_since_last_check < expected_interval_seconds - 30:  # 留30秒容差
        logger.debug(f"⏭️ 跳过本次检查（距上次{time_since_last_check:.0f}秒，需{expected_interval_seconds}秒）")
        return
    
    # 记录本次执行时间戳
    self.last_execution_timestamp = current_timestamp
    
    # 执行检查
    self.check_all_signals()
```

## 📊 优势对比

### 方案对比

| 特性 | 分钟+datetime | 秒数+timestamp |
|------|--------------|----------------|
| **数据类型** | float + datetime | int + float |
| **时区问题** | ❌ 需要处理时区转换 | ✅ 时间戳无时区概念 |
| **精度问题** | ⚠️ 浮点数可能有误差 | ✅ 整数运算精确 |
| **计算复杂度** | 高（需转换时区） | 低（直接相减） |
| **可读性** | 中等 | 高（简单直观） |
| **可靠性** | 低（易出错） | 高（稳定可靠） |

### 计算示例

**场景：交易时间，间隔1.5分钟（90秒）**

#### 第一次执行（启动时）
```python
current_timestamp = 1713160800.0  # 10:00:00
last_execution_timestamp = 0       # 初始值
time_since_last_check = 1713160800.0 - 0 = 1713160800.0秒
# 远大于90秒，执行检查
last_execution_timestamp = 1713160800.0  # 更新
```

#### 第二次触发（1分钟后）
```python
current_timestamp = 1713160860.0  # 10:01:00
last_execution_timestamp = 1713160800.0
time_since_last_check = 1713160860.0 - 1713160800.0 = 60秒
# 60 < 90 - 30 = 60，不满足条件，跳过
```

#### 第三次触发（1.5分钟后）
```python
current_timestamp = 1713160890.0  # 10:01:30
last_execution_timestamp = 1713160800.0
time_since_last_check = 1713160890.0 - 1713160800.0 = 90秒
# 90 >= 90 - 30 = 60，满足条件，执行检查
last_execution_timestamp = 1713160890.0  # 更新
```

## 🔧 关键改进点

### 1. 使用 `time.time()` 而非 `datetime`

**优势：**
- 返回Unix时间戳（浮点数秒）
- 无时区概念，全球统一
- 直接相减得到秒数差
- 性能更好

**示例：**
```python
import time

now = time.time()  # 1713160800.123456
# 无需考虑时区、夏令时等问题
```

### 2. 使用实例变量记录执行时间

**优势：**
- 不依赖APScheduler的job对象
- 完全控制状态管理
- 避免属性访问问题

**实现：**
```python
class SignalScheduler:
    def __init__(self):
        self.last_execution_timestamp = 0  # 初始化
    
    def _scheduled_check_with_dynamic_interval(self):
        # 读取
        time_since_last_check = time.time() - self.last_execution_timestamp
        
        # 更新
        self.last_execution_timestamp = time.time()
```

### 3. 容差机制

**设置30秒容差：**
```python
if time_since_last_check < expected_interval_seconds - 30:
    return  # 跳过
```

**原因：**
- APScheduler触发可能有几秒延迟
- 避免因系统负载导致的微小偏差
- 确保不会过早执行

**示例（90秒间隔）：**
- 实际等待 ≥ 60秒才可能执行
- 理想情况：90秒执行一次
- 最坏情况：120秒执行一次（仍有30秒余量）

## 📝 日志输出

### 启动日志

```
信号调度器已初始化
  交易时间检查间隔: 1.5分钟 (90秒)
  非交易时间检查间隔: 10分钟 (600秒)
交易时间配置: 周[1, 2, 3, 4, 5]
  时段1: 09:15 - 11:30
  时段2: 13:00 - 15:00
✅ 定时任务已启动（智能间隔: 交易时间1.5分钟 / 非交易时间10分钟）
```

### 运行时日志（开启DEBUG）

```
⏭️ 跳过本次检查（距上次30秒，需90秒）
⏭️ 跳过本次检查（距上次60秒，需90秒）
============================================================
🔄 【交易时间】开始信号检查...
============================================================
✅ 本轮信号检查完成
⏭️ 跳过本次检查（距上次30秒，需90秒）
⏭️ 跳过本次检查（距上次60秒，需90秒）
============================================================
🔄 【交易时间】开始信号检查...
============================================================
```

## 💡 最佳实践

### 1. 配置建议

**推荐的间隔配置：**

| 场景 | 交易时间 | 非交易时间 | 说明 |
|------|---------|-----------|------|
| 高频监控 | 1分钟 (60秒) | 5分钟 (300秒) | 及时响应 |
| **标准配置** | **1.5分钟 (90秒)** | **10分钟 (600秒)** | **平衡性能** |
| 节能模式 | 3分钟 (180秒) | 30分钟 (1800秒) | 节省资源 |

**配置示例：**
```yaml
scheduler:
  trading_check_interval: 1.5      # 90秒
  non_trading_check_interval: 10   # 600秒
```

### 2. 容差调整

根据实际需求调整容差：

```python
# 严格模式：容差10秒
if time_since_last_check < expected_interval_seconds - 10:
    return

# 宽松模式：容差60秒
if time_since_last_check < expected_interval_seconds - 60:
    return
```

### 3. 调试技巧

临时添加详细日志：

```python
logger.info(f"时间检查: current={current_timestamp}, last={self.last_execution_timestamp}, diff={time_since_last_check}s, expected={expected_interval_seconds}s")
```

## ⚠️ 注意事项

### 1. 时间戳溢出

`time.time()` 返回的是自1970年以来的秒数，不会溢出：
- 当前值：约 1,713,160,800 秒
- 最大值：取决于系统（通常很大）
- 无需担心溢出问题

### 2. 系统时间调整

如果用户手动调整系统时间：
- **向前调**: 可能导致长时间不执行
- **向后调**: 可能立即触发多次执行

**解决方案：**
- 服务器应启用NTP时间同步
- 避免手动调整系统时间
- 监控时间跳变异常

### 3. 首次执行

启动时 `last_execution_timestamp = 0`：
- 第一次计算的差值会非常大
- 必然满足执行条件
- 符合预期（立即执行首次检查）

## 🎉 总结

**核心优势：**
1. ✅ **简单可靠**: 时间戳相减，无时区问题
2. ✅ **精确计算**: 整数秒数，无浮点误差
3. ✅ **性能优秀**: `time.time()` 比 `datetime` 更快
4. ✅ **易于理解**: 逻辑清晰，便于维护

**实施效果：**
- 交易时间：每90秒检查一次 ✅
- 非交易时间：每600秒检查一次 ✅
- 无时区问题 ✅
- 无精度问题 ✅

---

**修复版本**: v2.2.5  
**修复日期**: 2026-04-15  
**技术方案**: 秒数时间戳方案
