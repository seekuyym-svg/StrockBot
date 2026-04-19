# StockBot - 智能股票监控与量化交易系统

<div align="center">

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)
![Version](https://img.shields.io/badge/Version-3.0.0-orange.svg)

**A股实时监控 | 多空信号分析 | 资讯自动推送 | 飞书智能通知**

[快速开始](#-快速开始) • [核心功能](#-核心功能) • [配置指南](#-配置指南) • [使用示例](#-使用示例) • [常见问题](#-常见问题)

</div>

---

## 📖 项目简介

StockBot 是一个功能强大的**A股智能监控系统**，集成了实时行情获取、技术分析、资讯抓取和智能通知等功能。系统基于腾讯财经API获取稳定可靠的行情数据，结合多维度技术指标进行趋势判断，并通过飞书实时推送重要信息。

### ✨ 核心特性

#### 🎯 智能监控与分析
- 📈 **实时行情监控** - 基于腾讯财经API，获取日/周/月涨跌幅及市值
- 🔄 **多空信号分析** - 均线排列 + MACD + RSI + 布林带综合评分系统
- 📊 **技术指标计算** - MA5/10/20/60、MACD、RSI、BOLL等专业指标
- 🧠 **智能研判** - RSI与BOLL结合的市场状态自动识别

#### 📰 资讯自动化
- 🕷️ **资讯自动抓取** - 从新浪财经获取个股最新资讯（最新3条）
- 📑 **公告监控** - 从东方财富网获取财务报告公告（最新1条）
- ⏰ **定时任务调度** - APScheduler自动执行，默认每天晚上执行
- 🔥 **NEW标签标记** - 当日资讯自动标注，重要信息不错过

#### 💬 智能通知系统
- 📱 **飞书实时推送** - 行情指标、多空信号、资讯公告一体化通知
- 🎨 **彩色格式化** - 涨红跌绿，视觉直观
- 🤖 **Emoji标识** - 🟢多头 🟡偏多 ⚪中性 🟠偏空 🔴空头
- ⚙️ **灵活配置** - 可自定义通知内容和频率

#### 🛠️ 技术架构
- 🌐 **统一数据源** - 腾讯财经API（稳定可靠，前复权数据）
- 📦 **模块化设计** - 工具脚本独立存放，业务逻辑清晰分离
- 🔧 **配置化管理** - YAML配置文件，Pydantic模型验证
- 📝 **完整日志** - Loguru结构化日志，便于问题排查

### 🎯 适用场景

- ✅ **个人投资者** - 监控股票池，及时获取行情和资讯
- ✅ **量化交易者** - 技术分析辅助决策，多空信号参考
- ✅ **资讯追踪者** - 自动抓取个股新闻和公告
- ✅ **投资组合管理** - 多只股票同时监控，一目了然

---

## 🚀 快速开始

### 第一步：环境准备

```bash
# 克隆项目
git clone https://github.com/yourusername/StockBot.git
cd StockBot

# 安装依赖
pip install -r requirements.txt
```

**主要依赖**：
- `requests` - HTTP请求库
- `pandas` - 数据处理
- `numpy` - 数值计算
- `pyyaml` - YAML配置解析
- `pydantic` - 数据验证
- `apscheduler` - 定时任务调度
- `loguru` - 日志记录

### 第二步：配置系统

编辑 `config.yaml` 文件：

```yaml
# ==================== 股票资讯监控配置 ====================
stock_news_monitor:
  enabled: true  # 启用资讯监控
  
  # 股票池配置
  stock_pool:
    - code: "sz.000792"
      name: "盐湖股份"
      index: "一"  # 中文序号，用于飞书通知显示
    - code: "sz.002706"
      name: "良信股份"
      index: "二"
    - code: "sh.600521"
      name: "华海药业"
      index: "三"
    - code: "sz.002126"
      name: "银轮股份"
      index: "四"
  
  # 资讯来源配置
  news_sources:
    individual_news:
      enabled: true  # 启用个股资讯
    financial_reports:
      enabled: true  # 启用公告
  
  # 定时任务配置
  schedule:
    hour: 21
    minute: 0
    second: 0

# ==================== 飞书通知配置 ====================
notification:
  feishu:
    enabled: true  # 启用飞书通知
    webhook_url: "https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_WEBHOOK_URL"
    notify_signals:  # 通知的信号类型（保留字段，兼容旧版）
      - BUY
      - SELL
      - ADD
      - STOP
```

**关键配置说明**：
- `stock_pool`: 配置要监控的股票列表，支持A股（sh/sz前缀）
- `index`: 中文序号，用于飞书通知中显示（如"一、二、三"）
- `webhook_url`: 替换为您的飞书机器人Webhook地址

### 第三步：运行系统

#### 方式1：启动完整监控系统（推荐）

```bash
python main.py
```

这将启动：
- ✅ 定时资讯监控任务
- ✅ 飞书通知服务
- ✅ 后台自动执行

#### 方式2：手动触发一次资讯监控

```bash
python test_integration_trend.py
```

立即执行一次完整的资讯获取和分析流程。

#### 方式3：单独运行多空信号分析

```bash
python tool_bullbear_a.py
```

仅对配置的股票池进行技术分析，输出详细的多空判断结果。

---

## 📊 核心功能详解

### 1. 多空信号分析系统

#### 功能说明
基于多维度技术指标综合判断个股当前是处于多头还是空头状态。

#### 技术指标
- **均线排列**: MA5 > MA10 > MA20（多头）或 MA5 < MA10 < MA20（空头）
- **MACD**: DIF与DEA的金叉/死叉，零轴位置判断
- **RSI**: 超买区(>70)、中性区(30-70)、超卖区(<30)
- **布林带**: 价格相对上轨/中轨/下轨的位置
- **成交量**: 价涨量增/价跌量增验证

#### 评分系统
| 指标 | 条件 | 分值 |
|------|------|------|
| 均线排列 | 多头 | +3 |
| 均线排列 | 空头 | -3 |
| MACD | 金叉且零轴上 | +1 |
| MACD | 死叉且零轴下 | -1 |
| RSI | > 60 (强势) | +1 |
| RSI | < 40 (弱势) | -1 |
| 布林带 | 突破上轨 | +1 |
| 布林带 | 跌破下轨 | -1 |
| 成交量 | 价涨量增 (>1.2倍) | +0.5 |
| 成交量 | 价跌量增 (>1.2倍) | -0.5 |

**评分范围**: -6.0 ~ +6.0

#### 趋势分类
| Emoji | 趋势标签 | 评分范围 | 含义 |
|-------|---------|---------|------|
| 🟢 | BULLISH | ≥ 2.0 | 多头排列（强烈看涨） |
| 🟡 | SLIGHTLY_BULLISH | 0 ~ 2.0 | 偏多震荡（谨慎看涨） |
| ⚪ | NEUTRAL | = 0 | 中性观望 |
| 🟠 | SLIGHTLY_BEARISH | -2.0 ~ 0 | 偏空震荡（谨慎看跌） |
| 🔴 | BEARISH | ≤ -2.0 | 空头排列（强烈看跌） |

#### 使用示例

```python
from tool_bullbear_a import TrendAnalyzer

analyzer = TrendAnalyzer()
result = analyzer.analyze_stock("sz.000792", "盐湖股份")

print(f"趋势: {result['conclusion']}")
print(f"评分: {result['score']}")
print(f"收盘价: {result['close']}")
```

**输出示例**：
```
📊 最终判断: 🟢 多头排列 (强烈看涨)
综合评分: 4.0 (偏多)
关键信号: 均线多头排列; MACD金叉且位于零轴上
```

---

### 2. 飞书通知系统

#### 通知内容结构

每只股票的通知包含以下信息：

```
━━━━━━━━━━━━━━━
🏢 一、盐湖股份 (sz.000792)
📈 行情指标: 日-1.61% | 周+1.28% | 月+12.27% | 市值2004.96亿
🟢 多空信号: 多头排列（4.0分），37.89元
━━━━━━━━━━━━━━━

📰 个股资讯 (3条):
1. 盐湖股份发布2026年一季度业绩预告 | 2026-04-19 🔥NEW
   🔗 [查看详情](链接)

📑 公告 (1条):
1. 关于召开2025年度股东大会的通知 | 2026-04-18
   🔗 [查看详情](链接)
```

#### 特色功能

1. **彩色涨跌幅**: 涨红 `<font color='red'>+1.28%</font>` / 跌绿 `<font color='green'>-1.61%</font>`
2. **NEW标签**: 当日资讯自动标注 `🔥NEW`
3. **多空信号**: 直观展示技术面判断结果
4. **中文序号**: 便于快速定位股票

#### 配置方法

在 `config.yaml` 中配置飞书Webhook：

```yaml
notification:
  feishu:
    enabled: true
    webhook_url: "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
```

**获取Webhook URL步骤**：
1. 在飞书群聊中添加"自定义机器人"
2. 复制机器人的Webhook地址
3. 粘贴到配置文件中

---

### 3. 资讯监控系统

#### 数据来源

| 数据类型 | 数据源 | 更新频率 | 数量限制 |
|---------|--------|---------|---------|
| 行情指标 | 腾讯财经API | 实时 | - |
| 个股资讯 | 新浪财经 | 每次执行 | 最新3条 |
| 财务报告 | 东方财富网 | 每次执行 | 最新1条 |

#### 定时任务

默认配置：每天 **21:00** 执行一次

可在 `config.yaml` 中修改：

```yaml
stock_news_monitor:
  schedule:
    hour: 21
    minute: 0
    second: 0
```

#### 控制台输出示例

```
============================================================
🔄 【股票资讯监控】开始执行...
============================================================
执行时间: 2026-04-19 14:54:00
现在开始获取个股资讯和公告

📊 处理股票: 一、盐湖股份 (sz.000792)
   📊 正在从腾讯财经获取 盐湖股份(000792) 的实时行情...
   ✅ 腾讯实时行情: 日-1.61% | 市值2004.96亿
   ✅ 腾讯K线: 周+1.28% | 月+12.27%
   ✅ 行情指标: 日-1.61% | 周+1.28% | 月+12.27% | 市值2004.96亿
   📈 正在进行多空信号分析...
   📊 最终判断: 🟢 多头排列 (强烈看涨)
   📰 获取个股资讯...
   ✅ 获取到 3 条个股资讯
   📑 获取公告...
   ✅ 获取到 1 条公告

✅ 资讯获取完成，共 16 条
📱 飞书通知发送成功
✅ 本轮资讯监控完成
```

---

## 📁 项目结构

```
StockBot/
├── config.yaml                      # 主配置文件
├── main.py                          # 主程序入口
│
├── tool_bullbear_a.py              # A股多空信号分析工具 ⭐
├── tool_bullbear_hk.py             # 港股多空信号分析工具
├── tool_bullbear_us.py             # 美股多空信号分析工具
├── tool_calc_relation.py           # 相关性分析工具
│
├── src/
│   ├── utils/
│   │   ├── config.py               # 配置加载模块（Pydantic）
│   │   ├── news_scheduler.py       # 资讯监控调度器
│   │   ├── news_crawler.py         # 资讯爬虫（新浪+东方财富）
│   │   ├── notification.py         # 飞书通知模块
│   │   └── ...
│   └── ...
│
├── tests/                          # 测试脚本目录
│   ├── test_integration_trend.py  # 集成测试
│   └── ...
│
├── docs/                           # 文档目录
├── signal/                         # 信号持久化目录
└── README.md                       # 本文件
```

**工具文件说明**：
- `tool_*.py` 文件位于项目根目录，可直接运行
- 采用统一的命名规范，便于识别和管理
- 独立的工具脚本，不依赖复杂的包结构

---

## 🎯 使用示例

### 示例1：分析单只股票

```python
from tool_bullbear_a import TrendAnalyzer

analyzer = TrendAnalyzer()
result = analyzer.analyze_stock("sh.600519", "贵州茅台")

if result:
    print(f"股票: {result['name']}")
    print(f"日期: {result['date']}")
    print(f"收盘价: {result['close']:.2f}")
    print(f"趋势: {result['conclusion']}")
    print(f"评分: {result['score']:.1f}")
    print(f"关键信号: {'; '.join(result['reasons'])}")
```

### 示例2：批量分析股票池

```python
from tool_bullbear_a import TrendAnalyzer

analyzer = TrendAnalyzer()
results = analyzer.analyze_stock_pool()

# 统计结果
bullish = sum(1 for r in results if r['trend'] in ['BULLISH', 'SLIGHTLY_BULLISH'])
bearish = sum(1 for r in results if r['trend'] in ['BEARISH', 'SLIGHTLY_BEARISH'])

print(f"多头: {bullish}只, 空头: {bearish}只")
```

### 示例3：手动触发资讯监控

```bash
# 立即执行一次资讯监控并发送飞书通知
python test_integration_trend.py
```

### 示例4：查看历史信号

```bash
# 查看signal目录下的历史信号文件
ls signal/

# 查看某天的信号
cat signal/2026-04-19/xxx.json
```

---

## ⚙️ 高级配置

### 1. 调整定时任务时间

编辑 `config.yaml`：

```yaml
stock_news_monitor:
  schedule:
    hour: 9      # 上午9点
    minute: 30   # 30分
    second: 0
```

### 2. 禁用某些资讯来源

```yaml
stock_news_monitor:
  news_sources:
    individual_news:
      enabled: false  # 禁用个股资讯
    financial_reports:
      enabled: true   # 保留公告
```

### 3. 调整股票池

```yaml
stock_news_monitor:
  stock_pool:
    - code: "sh.600000"
      name: "浦发银行"
      index: "一"
    - code: "sz.000001"
      name: "平安银行"
      index: "二"
    # 添加更多股票...
```

### 4. 关闭飞书通知

```yaml
notification:
  feishu:
    enabled: false  # 临时关闭通知
```

---

## 🔍 技术细节

### 数据源说明

#### 腾讯财经API（主力数据源）

**实时行情接口**：
```
http://qt.gtimg.cn/q={market}{code}
```

**返回字段**：
- `parts[3]`: 当前价
- `parts[4]`: 昨收价
- `parts[32]`: 涨跌幅（%）
- `parts[45]`: 流通市值（亿）

**历史K线接口**：
```
http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={market}{code},day,,,{days},qfq
```

**特点**：
- ✅ 稳定可靠，响应速度快
- ✅ 支持前复权数据（qfq参数）
- ✅ 无需认证，无调用限制
- ✅ 编码格式：GBK

#### 新浪财经（个股资讯）

**URL模板**：
```
https://finance.sina.com.cn/realstock/company/{symbol}/nc.shtml
```

**解析方式**：
- 使用BeautifulSoup解析HTML
- 提取"公司资讯"模块
- 编码格式：GBK

#### 东方财富网（公告）

**API接口**：
```
http://np-anotice-stock.eastmoney.com/api/security/ann
```

**特点**：
- JSON格式返回，易于解析
- 包含详细的公告信息
- 支持分页查询

---

### 技术指标计算

#### 移动平均线（MA）

```python
df['MA5'] = df['close'].rolling(window=5).mean()
df['MA10'] = df['close'].rolling(window=10).mean()
df['MA20'] = df['close'].rolling(window=20).mean()
df['MA60'] = df['close'].rolling(window=60).mean()
```

#### MACD

```python
ema_fast = df['close'].ewm(span=12, adjust=False).mean()
ema_slow = df['close'].ewm(span=26, adjust=False).mean()
dif = ema_fast - ema_slow
dea = dif.ewm(span=9, adjust=False).mean()
macd_bar = (dif - dea) * 2
```

#### RSI

```python
delta = df['close'].diff()
gain = delta.where(delta > 0, 0).rolling(window=14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
rs = gain / loss
rsi = 100 - (100 / (1 + rs))
```

#### 布林带（BOLL）

```python
ma = df['close'].rolling(window=20).mean()
std = df['close'].rolling(window=20).std()
upper = ma + 2 * std
lower = ma - 2 * std
```

---

## ❓ 常见问题

### Q1: 为什么飞书没有收到通知？

**检查清单**：
1. ✅ 确认 `config.yaml` 中 `notification.feishu.enabled = true`
2. ✅ 确认 Webhook URL 正确无误
3. ✅ 确认股票资讯监控已启用 `stock_news_monitor.enabled = true`
4. ✅ 查看控制台日志是否有错误信息
5. ✅ 测试网络连接是否正常

**测试方法**：
```bash
python test_integration_trend.py
```

### Q2: 如何修改监控的股票列表？

编辑 `config.yaml` 中的 `stock_news_monitor.stock_pool` 部分：

```yaml
stock_news_monitor:
  stock_pool:
    - code: "sh.600000"
      name: "浦发银行"
      index: "一"
    # 添加或删除股票...
```

**注意**：
- 代码格式必须为 `市场.代码`（如 `sh.600000` 或 `sz.000001`）
- `index` 字段为可选，用于飞书通知显示中文序号

### Q3: 多空信号评分偏低怎么办？

评分是基于多个技术指标的综合结果，建议：
1. 查看详细的关键信号列表
2. 结合基本面分析
3. 关注长期趋势，不要过度依赖短期波动
4. 评分仅供参考，不作为唯一决策依据

### Q4: 资讯抓取失败如何处理？

**可能原因**：
- 网络连接问题
- 网站反爬虫机制
- HTML结构变化

**解决方案**：
1. 检查网络连接
2. 增加请求间隔时间
3. 查看日志中的具体错误信息
4. 如持续失败，考虑更换数据源

### Q5: 如何调整定时任务的执行时间？

编辑 `config.yaml`：

```yaml
stock_news_monitor:
  schedule:
    hour: 15    # 改为下午3点
    minute: 0
    second: 0
```

重启程序后生效。

### Q6: 可以直接运行 tool_bullbear_a.py 吗？

可以！工具文件位于项目根目录，可以直接运行：

```bash
python tool_bullbear_a.py
```

无需使用 `-m` 参数。

---

## 📚 相关文档

- [腾讯财经API使用指南](TENCENT_API_GUIDE.md) - 详细的数据源说明
- [多空信号分析功能说明](BULL_BEAR_ANALYSIS_GUIDE.md) - 技术分析详解
- [飞书通知多空信号规范](FEISHU_TREND_SIGNAL_GUIDE.md) - 通知格式说明
- [文件移动操作记录](FILE_MOVE_RENAME_RECORD.md) - 项目结构调整说明

---

## 🛠️ 开发指南

### 添加新的工具脚本

1. 在项目根目录创建 `tool_xxx.py`
2. 实现核心功能
3. 添加 `if __name__ == "__main__":` 入口
4. 在README中补充说明

### 修改配置结构

1. 编辑 `config.yaml` 添加新配置项
2. 在 `src/utils/config.py` 中更新Pydantic模型
3. 确保向后兼容

### 扩展通知渠道

目前仅支持飞书，如需添加其他渠道：
1. 在 `src/utils/notification.py` 中实现新的Notifier类
2. 在配置文件中添加对应配置
3. 在 `news_scheduler.py` 中调用新的通知器

---

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

---

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

---

## 📮 联系方式

如有问题或建议，请通过以下方式联系：

- 📧 Email: seekuyym@gmail.com
- 💬 Issues: [GitHub Issues](https://github.com/yourusername/StockBot/issues)

---

<div align="center">

**⭐ 如果这个项目对您有帮助，请给个Star！**

Made with ❤️ by StockBot Team

</div>
