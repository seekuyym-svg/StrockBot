# 飞书通知RSI同步功能说明

## 📋 更新概述

已将RSI指标信息同步到飞书通知中，确保飞书消息与控制台输出保持一致。

## ✅ 完成的修改

### 1. 数据模型扩展
- **文件**: `src/models/models.py`
- **修改**: 在 `Signal` 模型中添加 `rsi: Optional[float] = None` 字段

### 2. 策略引擎更新
- **文件**: `src/strategy/engine.py`
- **修改**: 在所有信号生成方法中传递RSI值
  - `_create_buy_signal()` - 买入信号
  - `_create_add_signal()` - 加仓信号
  - `_create_sell_signal()` - 卖出信号
  - `_create_stop_signal()` - 止损信号
  - `_generate_signal()` - 所有WAIT信号
  - `analyze()` - 过滤器失败的信号

### 3. 控制台输出优化
- **文件**: `src/utils/scheduler.py`
- **修改**: 
  - `_log_important_signal()` - 重要信号输出中添加RSI显示
  - `_log_wait_signal()` - 等待信号输出中添加RSI显示

### 4. 飞书通知同步 ⭐ 新增
- **文件**: `src/utils/notification.py`
- **修改**: 在 `_build_message()` 方法中添加RSI指标输出和判断
- **位置**: BOLL信息之后、原因之前
- **格式**: `**📈 RSI: {rsi_value:.2f} ({emoji} {zone})**`

### 5. 测试脚本
- **文件**: `test_feishu_rsi.py`
- **功能**: 验证飞书通知中RSI信息的正确显示
- **测试场景**:
  - RSI超买区 (>70)
  - RSI中性区 (30-70)
  - RSI超卖区 (<30)
  - 无RSI数据

## 📊 飞书通知效果

### 买入信号示例
```
🟢 买入信号

标的: 港股创新药ETF广发 (sh.513120)
信号类型: BUY
当前价格: ¥1.281
涨跌幅: +0.71%
目标份额: 14,000 份
平均成本: ¥1.281
BOLL上轨-5.56% | 中轨+4.22% ← 此轨最近 | 下轨+13.99%
📈 RSI: 74.32 (🔴 超买区 ⚠️)

原因: 初始建仓：买入14000份，成本1.281元/份
```

### 加仓信号示例
```
🔵 加仓信号

标的: 港股创新药ETF广发 (sh.513120)
信号类型: ADD
当前价格: ¥1.250
涨跌幅: -2.42%
目标份额: 10,000 份
平均成本: ¥1.265
BOLL上轨-7.85% | 中轨+2.15% ← 此轨最近 | 下轨+12.15%
📈 RSI: 25.80 (🟢 超卖区 ✅)

原因: 加仓10000份，成本1.250元/份，累计1次加仓
```

## 🔍 RSI判断标准

| RSI值范围 | 区域 | 标识 | 含义 |
|-----------|------|------|------|
| RSI > 70 | 超买区 | 🔴 ⚠️ | 市场可能过热，存在回调风险 |
| 30 ≤ RSI ≤ 70 | 中性区 | 🟡 | 市场处于正常波动范围 |
| RSI < 30 | 超卖区 | 🟢 ✅ | 市场可能超跌，存在反弹机会 |

## 🧪 测试验证

### 1. 测试飞书通知RSI显示
```bash
python test_feishu_rsi.py
```

### 2. 测试真实飞书通知
```python
from src.utils.notification import get_feishu_notifier

notifier = get_feishu_notifier()
notifier.test_notification()
```

### 3. 运行主程序验证
```bash
python main.py
```

启动后，系统会：
- 在控制台输出中包含RSI信息
- 通过飞书机器人推送包含RSI的通知（如果已配置）

## 📝 注意事项

1. **RSI值为None时**: 飞书通知中不显示RSI信息
2. **精度**: RSI值保留两位小数
3. **实时性**: RSI基于最新的市场数据计算
4. **通知类型**: 默认仅对 BUY/SELL/ADD/STOP 信号发送飞书通知
5. **配置要求**: 需在 `config.yaml` 中正确配置飞书Webhook URL

## 🔄 与其他功能的一致性

现在系统的三个输出渠道都已同步RSI信息：
1. ✅ **控制台日志** (`scheduler.py`)
2. ✅ **飞书通知** (`notification.py`) ⭐ 本次更新
3. ✅ **信号数据持久化** (JSON文件自动包含rsi字段)

确保用户在不同渠道获取的信息完全一致。

## 💡 使用建议

1. **结合BOLL和RSI**: 
   - RSI超买 + 价格接近BOLL上轨 → 强烈回调信号
   - RSI超卖 + 价格接近BOLL下轨 → 强烈反弹信号

2. **飞书通知优势**:
   - 实时接收交易信号
   - 随时随地查看RSI状态
   - 快速判断市场情绪

3. **风险控制**:
   - RSI超买时谨慎追高
   - RSI超卖时关注反弹机会
   - 始终结合多个指标综合判断
