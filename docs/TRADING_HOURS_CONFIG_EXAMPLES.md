# A股交易时间配置示例

## 📋 配置文件位置

`config.yaml` 中的 `scheduler.trading_hours` 部分

## 🎯 配置项说明

### trading_days（交易日）

**类型**: 整数列表  
**默认值**: [1, 2, 3, 4, 5]（周一到周五）  
**取值范围**: 1-7（1=周一, 2=周二, ..., 7=周日）

**作用**: 定义哪些天需要检查ETF信号

---

### sessions（交易时间段列表）

**类型**: 对象列表，每个对象包含 `start_time` 和 `end_time`  
**默认值**: 两个时间段（上午和下午）

**作用**: 定义每天的多个交易时间段，支持A股午休等特殊情况

**结构：**
```yaml
sessions:
  - start_time: "HH:MM"  # 时段开始时间
    end_time: "HH:MM"    # 时段结束时间
  - start_time: "HH:MM"  # 第二个时段
    end_time: "HH:MM"
  # ... 可以添加更多时段
```

---

## 💡 完整配置示例

### 示例1: 标准A股交易时间（推荐）

```yaml
scheduler:
  signal_check_interval: 5
  run_immediately_on_start: true
  enabled: true
  trading_hours:
    trading_days: [1, 2, 3, 4, 5]  # 周一到周五
    sessions:
      - start_time: "09:30"         # 上午开盘
        end_time: "11:30"           # 上午收盘
      - start_time: "13:00"         # 下午开盘
        end_time: "15:00"           # 下午收盘
```

**适用场景**: 标准A股ETF交易

**行为：**
- ✅ 周一至周五 09:30-11:30：检查ETF信号
- ❌ 11:30-13:00：午休时间，仅输出上证指数
- ✅ 13:00-15:00：检查ETF信号
- ℹ️ 其他时间：仅输出上证指数

**交易时间统计：**
- 上午：2小时
- 下午：2小时
- 总计：4小时

---

### 示例2: 延长监控时间（含盘前盘后）

```yaml
scheduler:
  signal_check_interval: 5
  trading_hours:
    trading_days: [1, 2, 3, 4, 5]
    sessions:
      - start_time: "09:15"         # 集合竞价开始
        end_time: "11:30"
      - start_time: "13:00"
        end_time: "15:30"           # 延后30分钟
```

**适用场景**: 希望捕捉盘前集合竞价和盘后波动

---

### 示例3: 仅核心交易时段

```yaml
scheduler:
  signal_check_interval: 3          # 高频检查
  trading_hours:
    trading_days: [1, 2, 3, 4, 5]
    sessions:
      - start_time: "10:00"         # 避开开盘波动
        end_time: "11:30"
      - start_time: "13:30"         # 避开午后开盘
        end_time: "14:30"           # 避开收盘波动
```

**适用场景**: 避开开盘和收盘的剧烈波动，专注中间稳定时段

---

### 示例4: 港股交易时间（无午休）

```yaml
scheduler:
  signal_check_interval: 5
  trading_hours:
    trading_days: [1, 2, 3, 4, 5]
    sessions:
      - start_time: "09:30"         # 连续交易
        end_time: "16:00"
```

**适用场景**: 港股市场（无午休）

---

### 示例5: 美股交易时间（北京时间）

```yaml
scheduler:
  signal_check_interval: 10
  trading_hours:
    trading_days: [1, 2, 3, 4, 5]
    sessions:
      - start_time: "21:30"         # 美东9:30 = 北京21:30
        end_time: "23:59"           # 当天结束
      - start_time: "00:00"         # 次日凌晨
        end_time: "04:00"           # 美东16:00 = 北京04:00
```

**适用场景**: 美股市场（跨天交易）

**注意**: 当前版本支持跨天配置，通过两个时间段实现

---

### 示例6: 全天候监控（加密货币）

```yaml
scheduler:
  signal_check_interval: 5
  trading_hours:
    trading_days: [1, 2, 3, 4, 5, 6, 7]  # 每天
    sessions:
      - start_time: "00:00"
        end_time: "23:59"
```

**适用场景**: 加密货币等7x24小时交易市场

---

### 示例7: 自定义多时段（特殊需求）

```yaml
scheduler:
  signal_check_interval: 5
  trading_hours:
    trading_days: [1, 2, 3, 4, 5]
    sessions:
      - start_time: "09:30"         # 早盘
        end_time: "10:30"
      - start_time: "11:00"         # 午盘前
        end_time: "11:30"
      - start_time: "13:00"         # 午后
        end_time: "14:00"
      - start_time: "14:30"         # 尾盘
        end_time: "15:00"
```

**适用场景**: 分段监控，重点关注特定时段

---

## 🔧 动态修改配置

### 方法1: 修改配置文件后重启

1. 编辑 `config.yaml` 文件
2. 保存更改
3. 重启服务：`python main.py`

启动时会看到配置信息：
```
交易时间配置: 周[1, 2, 3, 4, 5]
  时段1: 09:30 - 11:30
  时段2: 13:00 - 15:00
```

---

## ⚠️ 注意事项

### 1. 时间段顺序

建议按时间顺序排列时间段，虽然不是强制要求，但便于阅读和维护。

**推荐：**
```yaml
sessions:
  - start_time: "09:30"
    end_time: "11:30"
  - start_time: "13:00"
    end_time: "15:00"
```

### 2. 时间段重叠

避免时间段重叠，否则可能导致逻辑混乱。

**错误示例：**
```yaml
sessions:
  - start_time: "09:30"
    end_time: "12:00"     # ❌ 与下一时段重叠
  - start_time: "11:00"   # ❌ 与上一时段重叠
    end_time: "15:00"
```

### 3. 时间格式要求

- 必须使用24小时制
- 格式必须为 "HH:MM"（如 "09:30"、"13:00"）
- 小时和分钟都需要两位数

**正确示例:**
```yaml
start_time: "09:30"   # ✅
end_time: "15:00"     # ✅
```

**错误示例:**
```yaml
start_time: "9:30"    # ❌ 格式错误
end_time: "3:00pm"    # ❌ 不支持12小时制
```

### 4. 时段数量限制

理论上没有时段数量限制，但建议不超过5个时段，避免配置过于复杂。

### 5. 边界时间处理

- `start_time`: 包含该时间点（>=）
- `end_time`: 包含该时间点（<=）

**示例:**
```yaml
sessions:
  - start_time: "09:30"
    end_time: "11:30"
```

- 09:30:00 ✅ 交易时间
- 11:30:00 ✅ 交易时间
- 11:30:01 ❌ 非交易时间（进入午休）

### 6. 跨天交易时间

如果需要支持跨天（如美股），可以通过两个时间段实现：

```yaml
sessions:
  - start_time: "21:30"   # 第一天晚上
    end_time: "23:59"
  - start_time: "00:00"   # 第二天凌晨
    end_time: "04:00"
```

---

## 📊 配置效果验证

### 验证当前配置

启动系统后，观察日志输出：

```
============================================================
启动定时信号检查任务...
============================================================
✅ 定时任务调度器启动成功 (间隔: 5分钟)
交易时间配置: 周[1, 2, 3, 4, 5]
  时段1: 09:30 - 11:30
  时段2: 13:00 - 15:00
🚀 立即执行首次信号检查
```

### 查看实际行为

**交易时间内（上午）:**
```
============================================================
🔄 【交易时间】开始信号检查...
============================================================
🟢 【重要信号】2026-04-13 10:30:00
标的: 港股创新药ETF (sh.513120)
信号: BUY
...
```

**午休时间:**
```
⏰ [2026-04-13 12:00:00] 非交易时间 | 上证指数: 3988.56
⏰ [2026-04-13 12:05:00] 非交易时间 | 上证指数: 3988.62
```

**交易时间内（下午）:**
```
============================================================
🔄 【交易时间】开始信号检查...
============================================================
🔴 【重要信号】2026-04-13 14:30:00
标的: 中概互联网ETF (sh.513050)
信号: SELL
...
```

**收盘后:**
```
⏰ [2026-04-13 15:30:00] 非交易时间 | 上证指数: 3989.12
```

---

## 🎓 最佳实践

### 1. 根据市场特点配置

**A股市场（标准）:**
```yaml
trading_hours:
  trading_days: [1, 2, 3, 4, 5]
  sessions:
    - start_time: "09:30"
      end_time: "11:30"
    - start_time: "13:00"
      end_time: "15:00"
```

**港股市场（无午休）:**
```yaml
trading_hours:
  trading_days: [1, 2, 3, 4, 5]
  sessions:
    - start_time: "09:30"
      end_time: "16:00"
```

**期货市场（有夜盘）:**
```yaml
trading_hours:
  trading_days: [1, 2, 3, 4, 5]
  sessions:
    - start_time: "09:00"
      end_time: "11:30"
    - start_time: "13:30"
      end_time: "15:00"
    - start_time: "21:00"         # 夜盘
      end_time: "23:00"
```

### 2. 配合检查间隔

**高频交易:**
```yaml
signal_check_interval: 2
trading_hours:
  sessions:
    - start_time: "09:30"
      end_time: "11:30"
    - start_time: "13:00"
      end_time: "15:00"
```

**低频监控:**
```yaml
signal_check_interval: 15
trading_hours:
  sessions:
    - start_time: "09:30"
      end_time: "11:30"
    - start_time: "13:00"
      end_time: "15:00"
```

### 3. 资源优化

合理配置交易时间可以避免在非交易时间浪费资源：
- 减少不必要的API调用
- 降低服务器负载
- 节省网络流量

---

## 🔍 故障排查

### 问题1: 午休时间仍在检查信号

**现象**: 11:30-13:00期间仍在检查ETF信号

**可能原因:**
- 配置的时间段有误
- 时间段结束时间设置过晚

**解决方法:**
```yaml
# 确认配置正确
sessions:
  - start_time: "09:30"
    end_time: "11:30"     # ✅ 确保是11:30而不是12:00
  - start_time: "13:00"
    end_time: "15:00"
```

### 问题2: 某个时段未生效

**现象**: 配置的第二个时段没有被识别

**可能原因:**
- YAML缩进错误
- 时段格式不正确

**解决方法:**
```bash
# 检查YAML格式
cat config.yaml | grep -A 10 sessions

# 运行测试脚本
python test_a_share_trading_hours.py
```

### 问题3: 时间段判断不准确

**现象**: 边界时间判断错误

**可能原因:**
- 服务器时间不准确
- 时区设置错误

**解决方法:**
```bash
# 检查服务器时间
date

# 同步时间
# Windows: 右键任务栏时间 -> 调整日期/时间 -> 立即同步
# Linux: sudo ntpdate pool.ntp.org
```

---

## 📝 相关文件

- **配置文件**: `config.yaml`
- **配置模型**: `src/utils/config.py`
- **调度器实现**: `src/utils/scheduler.py`
- **测试脚本**: `test_a_share_trading_hours.py`
- **主程序**: `main.py`
- **使用指南**: `SCHEDULER_GUIDE.md`

---

**配置版本**: v1.2.0  
**更新日期**: 2026-04-13  
**作者**: AI Assistant
