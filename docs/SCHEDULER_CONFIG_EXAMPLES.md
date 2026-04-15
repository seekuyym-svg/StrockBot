# 定时任务配置示例

## 📋 配置文件位置

`config.yaml` 中的 `scheduler` 部分

## 🎯 配置项说明

### 1. signal_check_interval（信号检查间隔）

**类型**: 整数（分钟）  
**默认值**: 5  
**取值范围**: 1-60

**作用**: 控制自动检查ETF信号的时间间隔

**示例配置:**

```yaml
# 每3分钟检查一次（高频监控）
scheduler:
  signal_check_interval: 3

# 每5分钟检查一次（推荐）
scheduler:
  signal_check_interval: 5

# 每10分钟检查一次（低频监控）
scheduler:
  signal_check_interval: 10

# 每30分钟检查一次（极低频）
scheduler:
  signal_check_interval: 30
```

**选择建议:**
- **短线交易者**: 3-5分钟，快速捕捉交易机会
- **中线交易者**: 10-15分钟，减少噪音
- **长线投资者**: 30-60分钟，关注大趋势

---

### 2. run_immediately_on_start（启动时立即执行）

**类型**: 布尔值  
**默认值**: true

**作用**: 系统启动时是否立即执行首次信号检查

**示例配置:**

```yaml
# 启动后立即检查（推荐）
scheduler:
  run_immediately_on_start: true

# 启动后等待第一个周期再检查
scheduler:
  run_immediately_on_start: false
```

**使用场景:**
- ✅ **设置为true**: 希望系统启动后立即获取最新信号
- ❌ **设置为false**: 希望系统先预热，等待一个完整周期后再检查

---

### 3. enabled（启用开关）

**类型**: 布尔值  
**默认值**: true

**作用**: 控制是否启用定时任务功能

**示例配置:**

```yaml
# 启用定时任务（默认）
scheduler:
  enabled: true

# 禁用定时任务
scheduler:
  enabled: false
```

**使用场景:**
- ✅ **设置为true**: 正常使用自动检查功能
- ❌ **设置为false**: 
  - 临时关闭自动检查
  - 仅通过API手动查询信号
  - 调试或维护期间

---

## 💡 完整配置示例

### 示例1: 标准配置（推荐）

```yaml
# 定时任务配置
scheduler:
  signal_check_interval: 5              # 每5分钟检查一次
  run_immediately_on_start: true        # 启动时立即执行
  enabled: true                         # 启用定时任务
```

**适用场景**: 日常交易监控

---

### 示例2: 高频监控配置

```yaml
# 定时任务配置
scheduler:
  signal_check_interval: 2              # 每2分钟检查一次
  run_immediately_on_start: true        # 启动时立即执行
  enabled: true                         # 启用定时任务
```

**适用场景**: 波动剧烈的市场行情，需要快速响应

---

### 示例3: 低频监控配置

```yaml
# 定时任务配置
scheduler:
  signal_check_interval: 15             # 每15分钟检查一次
  run_immediately_on_start: true        # 启动时立即执行
  enabled: true                         # 启用定时任务
```

**适用场景**: 平稳行情，减少不必要的API调用

---

### 示例4: 仅手动查询配置

```yaml
# 定时任务配置
scheduler:
  signal_check_interval: 5              # 保留配置但不起作用
  run_immediately_on_start: false       # 不自动执行
  enabled: false                        # 禁用定时任务
```

**适用场景**: 
- 只想通过API手动查询信号
- 不想让系统自动运行
- 测试或开发环境

---

### 示例5: 延迟启动配置

```yaml
# 定时任务配置
scheduler:
  signal_check_interval: 5              # 每5分钟检查一次
  run_immediately_on_start: false       # 等待5分钟后首次检查
  enabled: true                         # 启用定时任务
```

**适用场景**: 希望系统先预热，等待数据稳定后再开始检查

---

## 🔧 动态修改配置

### 方法1: 修改配置文件后重启

1. 编辑 `config.yaml` 文件
2. 保存更改
3. 重启服务：`python main.py`

### 方法2: 通过环境变量覆盖（高级）

```bash
# Linux/Mac
export SCHEDULER_SIGNAL_CHECK_INTERVAL=3
python main.py

# Windows PowerShell
$env:SCHEDULER_SIGNAL_CHECK_INTERVAL=3
python main.py
```

---

## ⚠️ 注意事项

### 1. 检查间隔选择

**过短间隔（<2分钟）的风险:**
- API调用过于频繁，可能被限流
- 增加服务器负载
- 信号变化不大，意义有限

**过长间隔（>30分钟）的风险:**
- 可能错过最佳交易时机
- T+0策略的灵活性降低
- 无法及时止盈止损

**推荐间隔:**
- 交易时间（9:30-15:00）: 3-10分钟
- 非交易时间: 可以更长或禁用

### 2. 资源消耗估算

| 检查间隔 | 每天检查次数 | API调用次数 | 预计生成文件数 |
|---------|------------|-----------|--------------|
| 2分钟   | ~375次     | ~750次    | 50-150个     |
| 5分钟   | ~150次     | ~300次    | 20-60个      |
| 10分钟  | ~75次      | ~150次    | 10-30个      |
| 30分钟  | ~25次      | ~50次     | 5-15个       |

*注：假设交易日约12.5小时，每个ETF每次检查产生1-2个文件*

### 3. 网络要求

- 确保网络连接稳定
- 如经常遇到超时，可适当增加检查间隔
- 建议在交易时间段内重点关注

### 4. 磁盘空间

- WAIT信号不会保存文件
- 只有BUY/ADD/SELL/STOP信号会持久化
- 建议定期清理30天前的数据

---

## 📊 配置效果验证

### 验证当前配置

启动系统后，观察日志输出：

```
============================================================
启动定时信号检查任务...
============================================================
✅ 定时任务调度器启动成功 (间隔: 5分钟)
🚀 已执行首次信号检查
```

如果看到上述信息，说明配置生效。

### 查看下次检查时间

系统会在日志中显示下次检查时间：

```
✅ 定时任务已启动，每5分钟自动检查信号
📅 下次检查时间: 2026-04-13 16:10:00
```

---

## 🎓 最佳实践

### 1. 根据市场波动调整

```yaml
# 高波动市场（如财报季、政策发布期）
scheduler:
  signal_check_interval: 3

# 正常市场
scheduler:
  signal_check_interval: 5

# 低波动市场（如节假日前后）
scheduler:
  signal_check_interval: 10
```

### 2. 配合交易时间

```yaml
# 仅在交易时间启用
# 可以通过外部脚本在9:30启动，15:00停止
scheduler:
  enabled: true
  signal_check_interval: 5
```

### 3. 分级监控策略

对于多个账户或策略：

```yaml
# 主账户：高频监控
account_main:
  scheduler:
    signal_check_interval: 3

# 测试账户：低频监控
account_test:
  scheduler:
    signal_check_interval: 15
```

---

## 🔍 故障排查

### 问题1: 配置不生效

**现象**: 修改了config.yaml但间隔时间没变

**解决方法**:
1. 确认文件格式正确（YAML格式）
2. 确认缩进正确（2空格）
3. 重启服务使配置生效
4. 查看启动日志确认读取的配置值

### 问题2: 定时任务未启动

**现象**: 启动后没有看到定时任务相关日志

**可能原因**:
- `enabled: false` 禁用了定时任务
- 配置文件路径错误
- 配置格式有误

**解决方法**:
```yaml
# 确认配置正确
scheduler:
  enabled: true  # 确保为true
  signal_check_interval: 5
  run_immediately_on_start: true
```

### 问题3: 检查频率异常

**现象**: 实际检查间隔与配置不符

**可能原因**:
- 系统负载过高导致延迟
- 网络请求超时重试占用时间
- 数据处理耗时较长

**解决方法**:
- 适当增加检查间隔
- 优化网络环境
- 查看日志中的时间戳分析延迟原因

---

## 📝 相关文件

- **配置文件**: `config.yaml`
- **配置模型**: `src/utils/config.py`
- **调度器实现**: `src/utils/scheduler.py`
- **主程序**: `main.py`
- **使用指南**: `SCHEDULER_GUIDE.md`

---

**配置版本**: v1.0.0  
**更新日期**: 2026-04-13  
**作者**: AI Assistant
