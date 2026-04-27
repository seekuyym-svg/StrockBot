# 股票资讯监控功能使用说明

## 功能概述

本系统新增了股票资讯监控功能，可以定时从东方财富网获取指定股票的**个股资讯**和**财务报告公告**，并通过飞书机器人推送给用户。

## 配置说明

### 1. 配置文件位置

在 `config.yaml` 中配置 `stock_news_monitor` 节点：

```yaml
# 股票资讯监控配置
stock_news_monitor:
  # 是否启用资讯监控
  enabled: true
  
  # 股票池配置（代码格式：sh.600000 或 sz.000001）
  stock_pool:
    - code: "sh.600519"
      name: "贵州茅台"
    - code: "sz.000858"
      name: "五粮液"
    - code: "sh.600036"
      name: "招商银行"
  
  # 资讯来源配置
  news_sources:
    # 个股资讯（来自东方财富搜索）
    individual_news:
      enabled: true
      url_template: "https://so.eastmoney.com/news/s?keyword={symbol}"
    # 财务报告公告
    financial_reports:
      enabled: true
      url_template: "https://data.eastmoney.com/notices/stock/{symbol}.html"
  
  # 定时任务配置（Cron表达式格式）
  schedule:
    # 每天执行时间（24小时制）
    hour: 21
    minute: 0
    second: 0
```

### 2. 配置项说明

#### stock_pool（股票池）
- **code**: 股票代码，格式为 `市场前缀.代码`
  - 上海证券交易所：`sh.XXXXXX`（如 `sh.600519`）
  - 深圳证券交易所：`sz.XXXXXX`（如 `sz.000858`）
- **name**: 股票名称（用于显示）

#### news_sources（资讯来源）
- **individual_news**: 个股资讯
  - 来源：东方财富网搜索页面
  - URL模板：`https://so.eastmoney.com/news/s?keyword={symbol}`
- **financial_reports**: 财务报告公告
  - 来源：东方财富网公告页面
  - URL模板：`https://data.eastmoney.com/notices/stock/{symbol}.html`

#### schedule（定时任务）
- **hour**: 执行小时（0-23）
- **minute**: 执行分钟（0-59）
- **second**: 执行秒数（0-59）
- 默认：每天 21:00:00 执行

## 使用方式

### 1. 启动系统

正常启动主程序即可：

```bash
python main.py
```

系统会自动：
- 加载股票池配置
- 启动资讯监控调度器
- 每天在指定时间自动获取资讯并推送

### 2. 测试功能

#### 测试爬虫功能

```bash
python tests/test_news_monitor.py --mode crawler
```

这会测试单只股票（贵州茅台）的资讯抓取功能。

#### 测试完整流程

```bash
python tests/test_news_monitor.py --mode full
```

这会按照配置的股票池，获取所有股票的资讯并发送飞书通知。

### 3. 手动触发一次

可以在代码中调用：

```python
from src.utils.news_scheduler import test_news_monitor

test_news_monitor()
```

## 飞书通知格式

推送的消息包含以下内容：

```
📊 股票资讯日报
时间: 2024-01-15 21:00:00

━━━━━━━━━━━━━━━
🏢 贵州茅台 (sh.600519) - 共 5 条资讯
━━━━━━━━━━━━━━━

📰 个股资讯 (3条):
1. **贵州茅台发布2023年业绩预告**
   🕒 2024-01-15 18:30
   🔗 [查看详情](https://...)

2. **茅台经销商大会召开**
   🕒 2024-01-15 15:20
   🔗 [查看详情](https://...)

📑 财务报告 (2条):
1. **贵州茅台2023年年度报告**
   🕒 2024-01-15 00:00
   🔗 [查看详情](https://...)

━━━━━━━━━━━━━━━
📈 汇总: 共监控 3 只股票，获取 12 条资讯
```

每条资讯都包含：
- ✅ 标题
- ✅ 发布时间
- ✅ 可点击的链接地址

## 注意事项

### 1. 网络请求限制
- 每只股票抓取后会等待1秒，避免被网站封禁
- 如果股票池较大，整体执行时间会较长

### 2. 网页结构变化
- 爬虫基于当前东方财富网的HTML结构设计
- 如果网站结构调整，可能需要更新解析逻辑
- 建议在 `tests/test_news_monitor.py` 中定期测试

### 3. 飞书通知频率
- 即使某天没有新资讯，也会发送通知（显示0条）
- 可以通过修改代码逻辑来跳过无资讯的情况

### 4. 时区设置
- 定时任务使用 `Asia/Shanghai` 时区
- 确保服务器时区设置正确

## 故障排查

### 问题1：无法获取资讯

**可能原因：**
- 网络连接问题
- 东方财富网反爬虫限制
- HTML结构变化

**解决方法：**
```bash
# 运行测试脚本查看详细错误
python tests/test_news_monitor.py --mode crawler
```

### 问题2：飞书通知发送失败

**可能原因：**
- Webhook URL 配置错误
- 网络连接问题
- 飞书API限流

**解决方法：**
1. 检查 `config.yaml` 中的 `notification.feishu.webhook_url`
2. 确认飞书机器人已启用
3. 查看日志中的具体错误信息

### 问题3：定时任务未执行

**可能原因：**
- 配置中 `enabled: false`
- 股票池为空
- 调度器启动失败

**解决方法：**
1. 检查 `stock_news_monitor.enabled` 是否为 `true`
2. 确认 `stock_pool` 不为空
3. 查看启动日志是否有错误

## 扩展建议

### 1. 增加更多资讯来源
可以扩展 `news_sources` 配置，添加其他财经网站的资讯。

### 2. 关键词过滤
在爬虫中添加关键词过滤，只推送包含特定关键词的资讯。

### 3. 去重机制
记录已推送的资讯URL，避免重复推送。

### 4. 情感分析
对资讯内容进行情感分析，标记利好/利空消息。

## 技术架构

```
main.py
  ├── 启动资讯监控调度器 (news_scheduler.py)
  │     ├── 定时触发 (APScheduler CronTrigger)
  │     └── 执行监控任务
  │           ├── 调用爬虫 (news_crawler.py)
  │           │     ├── 获取个股资讯
  │           │     └── 获取财务报告
  │           └── 发送通知 (notification.py)
  │                 └── 飞书机器人推送
```

## 相关文件

- **配置文件**: `config.yaml` - `stock_news_monitor` 节点
- **配置模型**: `src/utils/config.py` - `StockNewsMonitorConfig` 类
- **爬虫模块**: `src/utils/news_crawler.py` - `EastMoneyCrawler` 类
- **调度器**: `src/utils/news_scheduler.py` - `NewsMonitorScheduler` 类
- **通知模块**: `src/utils/notification.py` - `send_news_notification()` 函数
- **测试脚本**: `tests/test_news_monitor.py`

## 更新日志

### v1.0.0 (2024-01-15)
- ✅ 实现东方财富网爬虫
- ✅ 支持个股资讯和财务报告抓取
- ✅ 集成飞书通知
- ✅ 添加定时任务调度
- ✅ 提供测试脚本
