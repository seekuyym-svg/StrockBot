# 飞书通知多空信号功能说明

## 📖 功能概述

在原有的股票资讯飞书通知中，新增了**多空信号**显示功能。该功能基于技术分析（均线排列、MACD、RSI、布林带等指标）综合判断个股当前是处于多头还是空头状态，并在通知中直观展示。

## 🎯 显示位置

多空信号显示在**行情指标**下方，格式如下：

```
📈 行情指标: 日-1.61% | 周+1.28% | 月+12.27% | 市值2004.96亿
🟢 多空信号: 多头排列（4.0分），37.89元
```

## 📊 显示格式

### 基本格式
```
{emoji} 多空信号: {趋势描述}（{评分}分），{收盘价}元
```

### 示例

#### 1. 多头排列（强烈看涨）
```
🟢 多空信号: 多头排列（4.0分），37.89元
```

#### 2. 偏多震荡（谨慎看涨）
```
🟡 多空信号: 偏多震荡（0.5分），11.21元
```

#### 3. 中性观望
```
⚪ 多空信号: 中性观望（0.0分），16.88元
```

#### 4. 偏空震荡（谨慎看跌）
```
🟠 多空信号: 偏空震荡（-1.5分），25.30元
```

#### 5. 空头排列（强烈看跌）
```
🔴 多空信号: 空头排列（-4.5分），42.15元
```

## 🔍 趋势类型与Emoji映射

| 趋势标签 | Emoji | 趋势描述 | 评分范围 | 含义 |
|---------|-------|---------|---------|------|
| `BULLISH` | 🟢 | 多头排列 | ≥ 2.0 | 强烈看涨 |
| `SLIGHTLY_BULLISH` | 🟡 | 偏多震荡 | 0 ~ 2.0 | 谨慎看涨 |
| `NEUTRAL` | ⚪ | 中性观望 | = 0 | 观望 |
| `SLIGHTLY_BEARISH` | 🟠 | 偏空震荡 | -2.0 ~ 0 | 谨慎看跌 |
| `BEARISH` | 🔴 | 空头排列 | ≤ -2.0 | 强烈看跌 |

## 💡 评分系统

评分基于以下技术指标加权计算：

| 指标 | 条件 | 分值 |
|------|------|------|
| 均线排列 | 多头 | +3 |
| 均线排列 | 空头 | -3 |
| MACD | 金叉且在零轴上 | +1 |
| MACD | 死叉且在零轴下 | -1 |
| RSI | > 60 (强势) | +1 |
| RSI | < 40 (弱势) | -1 |
| 布林带 | 突破上轨 | +1 |
| 布林带 | 跌破下轨 | -1 |
| 成交量 | 价涨量增 (>1.2倍) | +0.5 |
| 成交量 | 价跌量增 (>1.2倍) | -0.5 |

**评分范围**: -6.0 ~ +6.0

## 🔧 技术实现

### 1. 数据流程

```
新闻调度器 (_fetch_and_send_news)
    ↓
获取行情指标 (_fetch_stock_metrics)
    ↓
调用趋势分析器 (TrendAnalyzer.analyze_stock)
    ↓
将分析结果添加到通知数据 (trend_analysis)
    ↓
构建飞书消息 (_build_news_message)
    ↓
发送通知 (send_news_notification)
```

### 2. 核心代码

#### news_scheduler.py
```python
# 导入趋势分析器
from src.utils.bull_bear_a import TrendAnalyzer
trend_analyzer = TrendAnalyzer()

# 获取趋势分析结果
trend_analysis = trend_analyzer.analyze_stock(symbol, name)

# 添加到通知数据
stock_news = {
    'code': symbol,
    'name': name,
    'metrics': stock_metrics,
    'trend_analysis': trend_analysis  # 新增字段
}
```

#### notification.py
```python
# 提取趋势分析数据
trend_analysis = stock_info.get('trend_analysis', {})
if trend_analysis:
    trend_type = trend_analysis.get('trend', 'NEUTRAL')
    score = trend_analysis.get('score', 0)
    close_price = trend_analysis.get('close', 0)
    
    # 根据趋势类型选择emoji
    if trend_type in ['BULLISH', 'SLIGHTLY_BULLISH']:
        trend_emoji = "🟢"
    elif trend_type in ['BEARISH', 'SLIGHTLY_BEARISH']:
        trend_emoji = "🔴"
    else:
        trend_emoji = "⚪"
    
    # 格式化多空信号行
    content += f"**{trend_emoji} 多空信号**: {trend_desc}（{score:.1f}分），{close_price:.2f}元\n"
```

## 📝 配置说明

无需额外配置，功能自动集成到现有的股票资讯监控系统中。

### 前提条件
1. **股票资讯监控已启用**: `config.yaml` 中 `stock_news_monitor.enabled = true`
2. **飞书通知已启用**: `config.yaml` 中 `notification.feishu.enabled = true`
3. **股票池已配置**: `config.yaml` 中 `stock_news_monitor.stock_pool` 包含要监控股票

## 🧪 测试方法

### 方式一：运行测试脚本
```bash
python test_feishu_trend_signal.py
```

### 方式二：触发完整的资讯监控
```bash
# 手动触发一次资讯监控
python -m src.utils.news_scheduler
```

### 方式三：等待定时任务执行
系统会在每天配置的定时任务时间（默认12:52）自动执行并发送通知。

## 📋 完整通知示例

```
📊 股票资讯日报
时间: 2026-04-19 14:17:43

━━━━━━━━━━━━━━━
🏢 一、盐湖股份 (sz.000792)
📈 行情指标: 日-1.61% | 周+1.28% | 月+12.27% | 市值2004.96亿
🟢 多空信号: 多头排列（4.0分），37.89元
━━━━━━━━━━━━━━━

📰 个股资讯 (1条):
1. 盐湖股份发布2026年一季度业绩预告 | 2026-04-19 14:17:43 🔥NEW
   🔗 [查看详情](https://example.com/news1)

📑 公告: 暂无

━━━━━━━━━━━━━━━
🏢 二、良信股份 (sz.002706)
📈 行情指标: 日+10.01% | 周+12.21% | 月+0.36% | 市值102.5亿
🟡 多空信号: 偏多震荡（0.5分），11.21元
━━━━━━━━━━━━━━━

📰 个股资讯: 暂无

📑 公告: 暂无

━━━━━━━━━━━━━━━
📈 汇总: 共监控 4 只股票，获取 1 条资讯
```

## ⚠️ 注意事项

### 1. 性能影响
- 每只股票的趋势分析需要获取300天历史K线数据
- 建议在资讯监控执行时增加适当的延迟（已设置为1秒/股）
- 4只股票的完整分析约需10-15秒

### 2. 数据完整性
- 如果趋势分析失败（网络异常、数据不足等），`trend_analysis` 字段为 `None`
- 通知构建时会跳过缺失的趋势分析，不影响其他内容显示

### 3. 评分解读
- **高分（≥ 4.0）**: 多个指标一致看多，可信度高
- **中等分（1.0 ~ 3.0）**: 部分指标看多，需谨慎
- **低分（-1.0 ~ 1.0）**: 指标分歧较大，建议观望
- **负分（≤ -2.0）**: 多个指标一致看空，风险较高

### 4. 与其他指标配合
- **结合涨跌幅**: 多头排列 + 正涨幅 = 强势上涨
- **结合成交量**: 多头排列 + 价涨量增 = 健康上涨
- **结合RSI**: 多头排列 + RSI超买 = 警惕回调

## 🔗 相关文档

- [多头/空头排列判断功能说明](BULL_BEAR_ANALYSIS_GUIDE.md)
- [腾讯财经API使用指南](TENCENT_API_GUIDE.md)
- [股票资讯监控规范](README.md#股票资讯监控)

---

**最后更新**: 2026-04-19  
**版本**: v1.0
