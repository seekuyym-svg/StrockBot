# 飞书通知频率限制解决方案

## ❌ 问题描述

服务器运行时出现错误：
```
❌ 飞书API返回错误: {'code': 11232, 'data': {}, 'msg': 'frequency limited psm[lark.oapi.app_platform_runtime]appID[1500]'}
```

**原因**：触发了飞书Webhook的频率限制。

## 📊 飞书API限流规则

- **单个机器人**：每分钟最多发送 **20条消息**
- **超过限制**：返回 `code: 11232` 错误
- **限流级别**：应用级别（appID）

## ✅ 已实施的解决方案

### 1. 自动频率控制

在 `FeishuNotifier` 中添加了智能频率控制机制：

**核心逻辑：**
```python
# 同一标的同类型信号最小间隔60秒
self.min_interval_seconds = 60

# 检查频率控制
current_time = datetime.now().timestamp()
last_send_time = self.last_send_time.get(symbol_signal_type, 0)
time_since_last_send = current_time - last_send_time

if time_since_last_send < self.min_interval_seconds:
    remaining_time = self.min_interval_seconds - time_since_last_send
    logger.warning(f"⚠️ 飞书通知频率限制：{symbol} {signal_type} 距上次发送仅 {time_since_last_send:.0f}秒，还需等待 {remaining_time:.0f}秒")
    return False
```

**特点：**
- ✅ 按 **标的 + 信号类型** 分别计时（如 `sh.513120_BUY`）
- ✅ 默认最小间隔 **60秒**
- ✅ 自动跳过超限请求，记录警告日志
- ✅ 发送成功后更新时间戳

### 2. 错误处理优化

特别处理频率限制错误：
```python
if error_code == 11232:
    logger.warning(f"⚠️ 飞书API频率限制（code: {error_code}）：{error_msg}")
    logger.warning(f"💡 建议：增加 min_interval_seconds 配置或检查是否有多个实例运行")
```

## 🔧 配置调整建议

### 方案1：调整最小间隔时间（推荐）

如果60秒仍然太频繁，可以修改 `src/utils/notification.py` 中的配置：

```python
# 在 __init__ 方法中
self.min_interval_seconds = 120  # 改为120秒（2分钟）
```

**建议值：**
- 保守策略：120秒（2分钟）
- 正常策略：60秒（1分钟）
- 激进策略：30秒（30秒）

### 方案2：检查多实例运行

确保服务器上只有一个程序实例在运行：

```bash
# 查找所有运行的Python进程
ps aux | grep python

# 如果有多个main.py实例，停止多余的
kill -9 <PID>

# 或使用pm2管理进程
pm2 list
pm2 stop all
pm2 start main.py --name stockbot
```

### 方案3：减少通知信号类型

在 `config.yaml` 中减少需要通知的信号类型：

```yaml
notification:
  feishu:
    enabled: true
    webhook_url: "https://open.feishu.cn/open-apis/bot/v2/hook/xxxxx"
    notify_signals: ["BUY", "SELL"]  # 只通知买卖，不通知加仓
```

**可选值：**
- `["BUY", "SELL"]` - 仅重要信号（最省流量）
- `["BUY", "SELL", "ADD"]` - 包含加仓
- `["BUY", "SELL", "ADD", "STOP"]` - 全部信号（默认）

## 📝 日志示例

### 正常发送
```
✅ 飞书通知已启用，将通知以下信号类型: ['BUY', 'SELL', 'ADD', 'STOP']
⏱️ 频率控制：同一标的同类型信号最小间隔 60 秒
📱 飞书通知发送成功: sh.513120 - BUY
```

### 频率限制触发
```
⚠️ 飞书通知频率限制：sh.513120 BUY 距上次发送仅 15秒，还需等待 45秒
```

### API限流错误
```
⚠️ 飞书API频率限制（code: 11232）：frequency limited psm[lark.oapi.app_platform_runtime]appID[1500]
💡 建议：增加 min_interval_seconds 配置或检查是否有多个实例运行
```

## 🚀 部署检查清单

在服务器上部署前，请确认：

1. ✅ 只有一个程序实例运行
   ```bash
   ps aux | grep "python main.py"
   ```

2. ✅ 检查飞书Webhook URL是否正确
   ```bash
   grep webhook_url config.yaml
   ```

3. ✅ 查看最近的日志
   ```bash
   tail -f logs/latest.log | grep -i feishu
   ```

4. ✅ 测试通知功能
   ```python
   from src.utils.notification import test_feishu_notification
   test_feishu_notification()
   ```

## 💡 最佳实践

1. **生产环境建议**：
   - 设置 `min_interval_seconds = 120`（2分钟）
   - 只通知 `["BUY", "SELL"]` 关键信号
   - 使用进程管理器（如 pm2、systemd）避免多实例

2. **开发环境建议**：
   - 可以临时禁用飞书通知：`enabled: false`
   - 或使用测试Webhook URL

3. **监控建议**：
   - 定期检查日志中的频率限制警告
   - 如果频繁触发，考虑增加间隔时间

## 🔍 故障排查

### 问题1：仍然收到11232错误

**可能原因：**
- 有多个程序实例同时运行
- 其他应用也在使用同一个飞书机器人

**解决方法：**
```bash
# 1. 检查进程
ps aux | grep python

# 2. 停止多余进程
pkill -f "python main.py"

# 3. 重新启动
nohup python main.py > logs/app.log 2>&1 &
```

### 问题2：收不到任何通知

**检查步骤：**
```bash
# 1. 确认飞书通知已启用
grep -A 3 "feishu:" config.yaml

# 2. 检查Webhook URL是否有效
curl -X POST "YOUR_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{"msg_type":"text","content":{"text":"test"}}'

# 3. 查看日志
tail -100 logs/app.log | grep -i feishu
```

### 问题3：频率控制过于严格

**调整方法：**
编辑 `src/utils/notification.py`：
```python
self.min_interval_seconds = 30  # 减小到30秒
```

然后重启服务。

## 📞 联系支持

如果以上方案都无法解决问题：
1. 检查飞书开放平台的应用配额
2. 联系飞书技术支持
3. 考虑使用企业微信或其他通知渠道作为备选
