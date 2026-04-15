# 动态检查间隔功能说明

## 📋 功能概述

系统现已支持**交易时间**和**非交易时间**使用不同的信号检查间隔，实现智能化的资源调度。

- **交易时间**: 高频检查（默认1分钟），及时捕捉交易机会
- **非交易时间**: 低频检查（默认10分钟），仅监控指数状态

## ⚙️ 配置方法

### 配置文件: `config.yaml`

```yaml
scheduler:
  # 交易时间检查间隔（分钟）
  trading_check_interval: 1
  
  # 非交易时间检查间隔（分钟）
  non_trading_check_interval: 10
  
  # 兼容旧配置（已废弃，保留用于向后兼容）
  signal_check_interval: 5
  
  # 其他配置...
  run_immediately_on_start: true
  enabled: true
  trading_hours:
    trading_days: [1, 2, 3, 4, 5]
    sessions:
      - start_time: "09:15"
        end_time: "11:30"
      - start_time: "13:00"
        end_time: "22:00"
```

### 配置项说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `trading_check_interval` | int | 1 | 交易时间检查间隔（分钟） |
| `non_trading_check_interval` | int | 10 | 非交易时间检查间隔（分钟） |
| `signal_check_interval` | int | 5 | 兼容旧配置，已废弃 |

## 🎯 工作原理

### 1. 智能判断交易时间

系统根据以下规则判断当前是否为交易时间：

1. **交易日检查**: 当前日期是否在配置的 `trading_days` 中
2. **时段检查**: 当前时间是否在任一配置的 `sessions` 时间段内

**示例:**
- 周三 10:30 → ✅ 交易时间（在09:15-11:30时段内）
- 周三 12:00 → ❌ 非交易时间（午休）
- 周日 10:00 → ❌ 非交易时间（非交易日）

### 2. 动态调整检查间隔

调度器每1分钟触发一次检查任务，但会根据当前时间状态决定是否执行：

```python
# 伪代码逻辑
def _scheduled_check_with_dynamic_interval():
    is_trading = is_trading_time()
    expected_interval = trading_check_interval if is_trading else non_trading_check_interval
    
    time_since_last_check = now - last_check_time
    
    if time_since_last_check >= expected_interval:
        check_all_signals()  # 执行检查
    else:
        return  # 跳过本次检查
```

### 3. 启动日志输出

```
信号调度器已初始化
  交易时间检查间隔: 1分钟
  非交易时间检查间隔: 10分钟
交易时间配置: 周[1, 2, 3, 4, 5]
  时段1: 09:15 - 11:30
  时段2: 13:00 - 22:00
✅ 定时任务已启动（智能间隔: 交易时间1分钟 / 非交易时间10分钟）
```

## 📊 实际效果

### 交易时间（1分钟检查）

```
============================================================
🔄 【交易时间】开始信号检查...
============================================================

🟢 【重要信号】2026-04-15 10:30:00
============================================================
标的: 港股创新药ETF广发 (sh.513120)
信号: BUY
价格: ¥1.281
涨跌幅: +0.71%
💡 研判: 回调 - RSI超买且价格接近BOLL上轨，市场可能过热，存在回调风险 ⚠️
============================================================

✅ 本轮信号检查完成
```

**特点:**
- 每分钟检查一次
- 及时发现交易信号
- 快速响应市场变化

### 非交易时间（10分钟检查）

```
⏰ [2026-04-15 12:00:00] 非交易时间 | 上证指数: 3250.50
⏰ [2026-04-15 12:10:00] 非交易时间 | 上证指数: 3251.20
⏰ [2026-04-15 12:20:00] 非交易时间 | 上证指数: 3249.80
```

**特点:**
- 每10分钟检查一次
- 仅输出上证指数信息
- 节省系统资源和API调用

## 💡 配置建议

### 场景1: A股标准交易（推荐）

```yaml
scheduler:
  trading_check_interval: 1           # 交易时间1分钟
  non_trading_check_interval: 10      # 非交易时间10分钟
  trading_hours:
    trading_days: [1, 2, 3, 4, 5]
    sessions:
      - start_time: "09:30"
        end_time: "11:30"
      - start_time: "13:00"
        end_time: "15:00"
```

**适用**: 标准A股交易，平衡及时性和资源消耗

### 场景2: 高频交易监控

```yaml
scheduler:
  trading_check_interval: 1           # 交易时间1分钟
  non_trading_check_interval: 5       # 非交易时间5分钟
```

**适用**: 需要更频繁监控指数的场景

### 场景3: 节能模式

```yaml
scheduler:
  trading_check_interval: 3           # 交易时间3分钟
  non_trading_check_interval: 30      # 非交易时间30分钟
```

**适用**: 服务器资源有限，降低API调用频率

### 场景4: 港股/美股延长交易

```yaml
scheduler:
  trading_check_interval: 1
  non_trading_check_interval: 10
  trading_hours:
    trading_days: [1, 2, 3, 4, 5]
    sessions:
      - start_time: "09:30"
        end_time: "16:00"  # 港股无午休
```

## 🔧 技术实现

### 核心模块

**文件**: `src/utils/scheduler.py`

**关键方法:**

1. **[__init__()](file://e:\LearnPY\Projects\StockBot\src\utils\scheduler.py#L25-L60)** - 初始化时读取配置
   ```python
   self.trading_check_interval = config.scheduler.trading_check_interval
   self.non_trading_check_interval = config.scheduler.non_trading_check_interval
   ```

2. **[is_trading_time()](file://e:\LearnPY\Projects\StockBot\src\utils\scheduler.py#L75-L95)** - 判断是否为交易时间
   ```python
   def is_trading_time(self):
       # 检查交易日和交易时段
       return True/False
   ```

3. **[start()](file://e:\LearnPY\Projects\StockBot\src\utils\scheduler.py#L358-L378)** - 启动时使用基础间隔1分钟
   ```python
   self.scheduler.add_job(
       func=self._scheduled_check_with_dynamic_interval,
       trigger=IntervalTrigger(minutes=1),
       ...
   )
   ```

4. **[_scheduled_check_with_dynamic_interval()](file://e:\LearnPY\Projects\StockBot\src\utils\scheduler.py#L380-L395)** - 动态判断是否执行
   ```python
   def _scheduled_check_with_dynamic_interval(self):
       is_trading = self.is_trading_time()
       expected_interval = self.trading_check_interval if is_trading else self.non_trading_check_interval
       
       if time_since_last_check >= expected_interval:
           self.check_all_signals()
   ```

### 配置模型

**文件**: `src/utils/config.py`

```python
class SchedulerConfig(BaseModel):
    signal_check_interval: int = 5  # 兼容旧配置
    trading_check_interval: int = 1  # 交易时间间隔
    non_trading_check_interval: int = 10  # 非交易时间间隔
    run_immediately_on_start: bool = True
    enabled: bool = True
    trading_hours: TradingHoursConfig = TradingHoursConfig()
```

## 🧪 测试验证

运行测试脚本：

```bash
python test_dynamic_interval.py
```

**测试覆盖:**
- ✅ 配置加载正确
- ✅ 交易时间判断准确
- ✅ 不同时段使用不同间隔
- ✅ 边界情况处理（午休、周末）

## ⚠️ 注意事项

### 1. 兼容性

- `signal_check_interval` 仍保留用于向后兼容
- 如果使用该参数，会同时设置交易时间和非交易时间间隔
- 建议使用新的 `trading_check_interval` 和 `non_trading_check_interval`

### 2. 最小间隔

- 建议交易时间间隔 ≥ 1分钟
- 过短的间隔可能导致API限流
- 飞书通知有频率限制（每分钟20条）

### 3. 资源消耗

**交易时间（1分钟）:**
- 每次检查约2-4次API请求
- 每小时约120-240次API调用
- 内存占用稳定

**非交易时间（10分钟）:**
- 每次检查仅获取上证指数
- 每小时约6次API调用
- 显著降低资源消耗

### 4. 时间同步

- 确保服务器时间准确
- 建议使用NTP时间同步服务
- 时区设置为 Asia/Shanghai

## 📈 性能对比

| 配置方案 | 交易时间间隔 | 非交易时间间隔 | API调用/天 | 资源消耗 |
|---------|-------------|---------------|-----------|---------|
| 固定5分钟 | 5分钟 | 5分钟 | ~576次 | 中等 |
| **动态间隔（推荐）** | **1分钟** | **10分钟** | **~216次** | **低** |
| 高频模式 | 1分钟 | 5分钟 | ~336次 | 中高 |
| 节能模式 | 3分钟 | 30分钟 | ~96次 | 极低 |

**计算假设:**
- 交易时间: 6.5小时（09:15-11:30 + 13:00-22:00）
- 非交易时间: 17.5小时
- 每次检查2个ETF标的

## 🎯 最佳实践

1. **生产环境推荐配置**:
   ```yaml
   trading_check_interval: 1
   non_trading_check_interval: 10
   ```

2. **监控API调用量**:
   - 定期检查数据源API配额
   - 观察日志中的调用频率
   - 根据实际情况调整间隔

3. **结合飞书通知**:
   - 交易时间频繁通知可能刷屏
   - 建议在 `notify_signals` 中只包含关键信号
   - 或增加飞书通知的频率控制

4. **异常处理**:
   - 网络故障时自动重试
   - API限流时等待后重试
   - 记录详细的错误日志

## 📝 更新日志

### v2.2.0 (2026-04-15)

**新增功能:**
- ✨ 支持交易时间和非交易时间使用不同的检查间隔
- ✨ 智能判断交易时间，自动切换检查频率
- ✨ 非交易时间仅监控指数，节省资源

**优化改进:**
- 🔧 重构调度器启动逻辑，支持动态间隔
- 🔧 保留旧配置参数用于向后兼容
- 🔧 完善启动日志，清晰显示配置信息

---

**功能版本**: v1.0.0  
**更新日期**: 2026-04-15  
**作者**: AI Assistant
