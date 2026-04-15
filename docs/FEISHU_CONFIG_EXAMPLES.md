# 飞书通知配置示例

## 📋 完整配置示例

### 基础配置（推荐）

```yaml
# 通知配置
notification:
  # 飞书机器人通知
  feishu:
    # 是否启用飞书通知
    enabled: true
    # 飞书机器人 Webhook URL（替换为您的实际URL）
    webhook_url: "https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    # 通知类型：BUY/SELL/ADD/STOP
    notify_signals: ["BUY", "SELL", "ADD", "STOP"]
```

---

## 💡 不同场景的配置

### 场景1: 仅接收买卖信号

适合不想被加仓信号打扰的用户：

```yaml
notification:
  feishu:
    enabled: true
    webhook_url: "your_webhook_url"
    notify_signals: ["BUY", "SELL"]  # 仅买卖信号
```

**优点：**
- 减少通知频率
- 只关注关键交易决策
- 避免信息过载

---

### 场景2: 接收所有信号

适合需要全面监控的用户：

```yaml
notification:
  feishu:
    enabled: true
    webhook_url: "your_webhook_url"
    notify_signals: ["BUY", "SELL", "ADD", "STOP"]  # 所有重要信号
```

**优点：**
- 完整的交易记录
- 及时了解每次加仓
- 便于后续分析

---

### 场景3: 临时关闭通知

适合暂时不需要通知的场景：

```yaml
notification:
  feishu:
    enabled: false  # 禁用通知
    webhook_url: "your_webhook_url"  # 保留配置
    notify_signals: ["BUY", "SELL", "ADD", "STOP"]
```

**优点：**
- 无需删除配置
- 随时可以快速启用
- 保留Webhook URL

---

### 场景4: 多机器人配置（需修改代码）

如果需要同时通知多个群，当前版本需要扩展代码支持。

**未来可能的配置格式：**
```yaml
notification:
  feishu:
    - name: "主监控群"
      enabled: true
      webhook_url: "webhook_url_1"
      notify_signals: ["BUY", "SELL"]
    
    - name: "团队通知群"
      enabled: true
      webhook_url: "webhook_url_2"
      notify_signals: ["BUY", "SELL", "STOP"]
```

---

## 🔧 获取 Webhook URL 详细步骤

### 步骤1: 创建群聊（如果没有）

1. 打开飞书
2. 点击右上角 **"+"** → **"创建群聊"**
3. 添加成员（可以只加自己）
4. 设置群名称，如：**ETF交易监控**

### 步骤2: 添加机器人

1. 进入目标群聊
2. 点击右上角 **"..."** 或 **"群设置"**
3. 找到 **"群机器人"** 或 **"机器人"**
4. 点击 **"添加机器人"**

### 步骤3: 选择自定义机器人

1. 在机器人列表中，找到 **"自定义机器人"**
2. 点击 **"添加"** 或 **"前往添加"**

### 步骤4: 配置机器人

1. **设置机器人名称**：如 "ETF交易助手"
2. **（可选）上传头像**：选择一个图标
3. **（可选）设置描述**：如 "自动推送ETF交易信号"
4. 点击 **"完成"** 或 **"添加"**

### 步骤5: 复制 Webhook URL

1. 添加成功后，会显示 **Webhook 地址**
2. 点击 **"复制"** 按钮
3. 格式类似：
   ```
   https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
   ```

### 步骤6: 粘贴到配置文件

1. 打开 `config.yaml`
2. 找到 `notification.feishu.webhook_url`
3. 将复制的 URL 粘贴到引号内：
   ```yaml
   webhook_url: "https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
   ```

### 步骤7: 启用并测试

1. 设置 `enabled: true`
2. 保存配置文件
3. 运行测试脚本：
   ```bash
   python test_feishu_notification.py
   ```
4. 检查飞书群聊是否收到测试消息

---

## ⚠️ 常见问题

### Q1: Webhook URL 泄露了怎么办？

**A:** 
1. 立即在飞书中删除该机器人
2. 重新添加一个新的机器人
3. 更新配置文件中的 Webhook URL
4. 重启系统

### Q2: 可以同时添加到多个群吗？

**A:** 
是的！一个机器人可以添加到多个群聊，所有群都会收到相同的消息。

### Q3: 如何停止接收通知？

**A:** 
有三种方法：
1. **推荐**：在 config.yaml 中设置 `enabled: false`
2. 从群聊中移除机器人
3. 删除或注释掉 notification 配置

### Q4: 收不到通知但日志显示发送成功？

**A:** 
可能原因：
1. 飞书客户端未登录
2. 群聊被静音
3. 网络延迟
4. 飞书服务器问题

**解决方法：**
- 检查飞书是否正常登录
- 取消群聊静音
- 稍后重试
- 查看飞书官方状态页

### Q5: 通知有延迟怎么办？

**A:** 
延迟通常在1-3秒内是正常的。如果延迟过长：
1. 检查网络连接
2. 尝试更换网络环境
3. 联系飞书技术支持

### Q6: 可以自定义消息格式吗？

**A:** 
当前版本使用固定的交互式卡片格式。如需自定义，可以修改 `src/utils/notification.py` 中的 `_build_message` 方法。

---

## 🎨 消息样式说明

### 颜色映射

| 信号类型 | 颜色 | Emoji | 用途 |
|---------|------|-------|------|
| BUY | 绿色 🟢 | 🟢 | 买入信号 |
| ADD | 蓝色 🔵 | 🔵 | 加仓信号 |
| SELL | 红色 🔴 | 🔴 | 卖出信号 |
| STOP | 橙色 ⚠️ | ⚠️ | 止损信号 |

### 消息结构

```
┌─────────────────────────────┐
│  [标题栏 - 带颜色和Emoji]     │
├─────────────────────────────┤
│                             │
│  [主要内容区域]               │
│  - 标的信息                  │
│  - 价格信息                  │
│  - 交易详情                  │
│  - 原因说明                  │
│                             │
├─────────────────────────────┤
│  [分隔线]                    │
├─────────────────────────────┤
│  [底部备注 - 系统信息+时间]   │
└─────────────────────────────┘
```

---

## 📊 通知频率估算

假设交易日为周一至周五，每天9:00-15:00，每5分钟检查一次：

| 信号类型 | 日均次数 | 周均次数 | 月均次数 |
|---------|---------|---------|---------|
| WAIT | 100-200次 | 500-1000次 | 2000-4000次 |
| BUY | 0-2次 | 0-10次 | 0-40次 |
| ADD | 0-5次 | 0-25次 | 0-100次 |
| SELL | 0-2次 | 0-10次 | 0-40次 |
| STOP | 极少 | 极少 | 极少 |

**注意：**
- WAIT 信号默认不通知，避免刷屏
- 实际频率取决于市场波动和策略参数
- 建议在配置中只选择需要的信号类型

---

## 🔒 安全建议

### 1. 保护 Webhook URL

- ✅ 不要公开分享
- ✅ 不要提交到公开代码仓库
- ✅ 定期更换（飞书支持重新生成）
- ❌ 不要截图发到社交媒体

### 2. 权限管理

- 仅在必要的群聊中添加机器人
- 定期检查群成员列表
- 发现异常立即禁用

### 3. 监控异常

- 留意是否有未知消息
- 定期检查通知历史
- 发现异常立即更换 Webhook

---

## 📝 相关文件

- **配置示例**: 本文档
- **配置文件**: `config.yaml`
- **配置模型**: `src/utils/config.py`
- **通知模块**: `src/utils/notification.py`
- **测试脚本**: `test_feishu_notification.py`
- **使用指南**: `FEISHU_NOTIFICATION_GUIDE.md`

---

**配置版本**: v1.0.0  
**更新日期**: 2026-04-13  
**作者**: AI Assistant
