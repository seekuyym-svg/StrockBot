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
- `pandas` / `numpy` - 数据处理与数值计算
- `pyyaml` / `pydantic` - YAML配置解析与数据验证
- `apscheduler` - 定时任务调度
- `loguru` - 结构化日志记录
- `mootdx` - 通达信数据读取
- `akshare` - 金融数据接口
- `fastapi` / `uvicorn` - Web API服务

### 第二步：配置系统

编辑 `config.yaml` 文件，配置以下关键信息：

#### 1. 飞书通知配置

```yaml
notification:
  feishu:
    enabled: true  # 启用飞书通知
    webhook_url: "https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_WEBHOOK_URL"
```

**获取Webhook URL**：
1. 在飞书中创建群机器人
2. 复制机器人的 Webhook 地址
3. 替换配置文件中的 `YOUR_WEBHOOK_URL`

#### 2. ETF T+0 交易配置

```yaml
symbols:
  - code: "sh.513120"
    name: "港股创新药ETF"
    enabled: true
    add_drop_threshold: 3.5    # 加仓跌幅阈值（%）
    take_profit_threshold: 4.0 # 止盈涨幅阈值（%）
    max_add_positions: 4       # 最大加仓次数
    initial_position_pct: 6    # 初始建仓比例（%）
  
  - code: "sh.513050"
    name: "中概互联网ETF"
    enabled: true
    add_drop_threshold: 2.5
    take_profit_threshold: 3.0
    max_add_positions: 4
    initial_position_pct: 6

strategy:
  max_add_positions: 4         # 全局默认最大加仓次数
  add_position_multiplier: 2.0 # 加仓倍数
  add_drop_threshold: 3.0      # 全局默认加仓跌幅（%）
  take_profit_threshold: 2.0   # 全局默认止盈涨幅（%）
```

#### 3. 股票资讯监控配置

```yaml
stock_news_monitor:
  enabled: true  # 启用资讯监控
  
  stock_pool:
    - code: "sz.000792"
      name: "盐湖股份"
    - code: "sz.002706"
      name: "良信股份"
  
  schedule:
    hour: 21
    minute: 0
    second: 0
```

#### 4. 买入委托定时任务配置

```yaml
buy_order_scheduler:
  enabled: true      # 启用买入委托定时任务
  hour: 9            # 执行时间：9点
  minute: 26         # 执行时间：26分
  min_score: 1.0     # 最低综合评分要求
```

#### 5. 通达信数据目录配置（选股功能需要）

```yaml
TDX_DIR: "D:\\Install\\zd_zxzq_gm"  # 通达信安装目录
```

### 第三步：运行系统

#### 方式1：启动完整监控系统（推荐）⭐

```bash
python main.py
```

这将同时启动：
- ✅ **T+0 ETF信号检查调度器** - 交易时间内动态监控买卖信号
- ✅ **股票资讯监控调度器** - 每天21:00推送资讯
- ✅ **买入委托计算调度器** - 周一至周五09:26自动计算买入委托
- ✅ **FastAPI API服务** - 提供RESTful API接口

**优势**：统一管理、资源共享、一键启停

#### 方式2：单独运行特定功能

**A. 执行持续放量选股**
```bash
python local/select_stocks_volume.py
```
- 扫描全市场A股
- 筛选连续5天放量的股票
- 自动过滤ST、退市、停牌股票
- 计算综合评分并保存到 `data/stockpool_YYYYMMDD.txt`

**B. 手动执行买入委托计算**
```bash
python tool_calc_buynum_simple.py
```
- 读取前一天的选股结果
- 过滤评分 >= 1.0的股票
- 计算买入股数（100的倍数）
- 生成委托明细到 `data/trade_YYYYMMDD.txt`

**C. 单独运行A股多空信号分析**
```bash
python tool_bullbear_a.py
```
- 对指定股票进行技术分析
- 输出综合评分和多空判断

**D. 独立运行买入委托调度器**
```bash
python src/utils/buy_order_scheduler.py
```
- 仅启动买入委托定时任务
- 适用于调试和测试

### 第四步：查看结果

#### 1. 选股结果文件
位置：`data/stockpool_YYYYMMDD.txt`
```text
# 选股结果 - 2026-04-23
# 格式: 股票代码,综合评分
000526,3.5
002830,2.0
```

#### 2. 交易委托文件
位置：`data/trade_YYYYMMDD.txt`
```text
4
股票代码,开盘价,股数,金额
000526,31.77,200,6354.00
002830,15.50,500,7750.00
```

#### 3. 飞书通知示例

**买入委托通知**：
```
📊 今日买入委托明细
时间: 2026-04-23 09:26:30
数量: 4 只股票

━━━━━━━━━━━━━━━

1. 学大教育 (000526)
   开盘价: ¥31.77
   股数: 200 股
   金额: ¥6,354.00

2. 名雕股份 (002830)
   开盘价: ¥15.50
   股数: 500 股
   金额: ¥7,750.00

━━━━━━━━━━━━━━━
```

**ETF交易信号通知**：
```
🟢 【重要信号】港股创新药ETF (sh.513120)
信号: BUY
涨跌幅: -0.31%
目标股数: 14,000
原因: 初始建仓，购买14000股，成本1.280元/股
```

---

## 🏗️ 系统架构

### 整体架构图

```
┌─────────────────────────────────────────────────────┐
│                   main.py (主入口)                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ T+0调度器 │  │资讯调度器 │  │买入委托调度器     │  │
│  └────┬─────┘  └────┬─────┘  └────────┬─────────┘  │
└───────┼──────────────┼────────────────┼─────────────┘
        │              │                │
        ▼              ▼                ▼
┌──────────────┐ ┌──────────┐ ┌──────────────────┐
│策略引擎       │ │资讯爬虫   │ │买入计算模块       │
│(马丁格尔)    │ │(新浪/东财)│ │(tool_calc_*)     │
└──────┬───────┘ └──────────┘ └────────┬─────────┘
       │                                │
       ▼                                ▼
┌──────────────────────────────────────────────────┐
│              数据层 (Data Layer)                   │
│  ┌──────────────┐    ┌──────────────────────┐   │
│  │腾讯财经API    │    │通达信本地数据         │   │
│  │(实时行情)     │    │(选股/K线)             │   │
│  └──────────────┘    └──────────────────────┘   │
└──────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────┐
│           通知层 (Notification Layer)              │
│         飞书机器人 (Webhook)                       │
└──────────────────────────────────────────────────┘
```

### 核心模块说明

| 模块 | 路径 | 功能 |
|------|------|------|
| **主程序** | `main.py` | 统一入口，启动所有调度器和API服务 |
| **T+0策略引擎** | `src/strategy/engine.py` | 马丁格尔策略实现，T+0交易逻辑 |
| **数据提供者** | `src/market/data_provider.py` | 腾讯财经API封装，行情数据获取 |
| **资讯爬虫** | `src/utils/news_crawler.py` | 新浪财经、东方财富资讯抓取 |
| **新闻调度器** | `src/utils/news_scheduler.py` | 资讯监控定时任务 |
| **买入调度器** | `src/utils/buy_order_scheduler.py` | 买入委托定时计算与通知 |
| **信号存储** | `src/utils/signal_storage.py` | 历史信号JSON文件持久化 |
| **配置管理** | `src/utils/config.py` | YAML配置加载与Pydantic验证 |
| **选股工具** | `local/select_stocks_volume.py` | 持续放量选股策略 |
| **买入计算** | `tool_calc_buynum_simple.py` | 根据选股结果计算买入委托 |
| **多空分析** | `tool_bullbear_a.py` | A股综合评分与趋势判断 |

### 数据流转

```mermaid
graph LR
    A[选股脚本] -->|生成| B[stockpool文件]
    B -->|读取| C[买入计算]
    C -->|生成| D[trade文件]
    D -->|推送| E[飞书通知]
    
    F[腾讯API] -->|行情| G[T+0策略]
    G -->|信号| E
    
    H[新浪/东财] -->|资讯| I[资讯爬虫]
    I -->|推送| E
```

---

## ⚙️ 配置指南

### 完整配置示例

```yaml
# ==================== 基础配置 ====================
initial_capital: 300000  # 初始资金（元）

# ==================== ETF配置 ====================
symbols:
  - code: "sh.513120"
    name: "港股创新药ETF"
    enabled: true
    # 个性化策略参数
    add_drop_threshold: 3.5
    take_profit_threshold: 4.0
    max_add_positions: 4
    initial_position_pct: 6

# ==================== 全局策略配置 ====================
strategy:
  max_add_positions: 4
  add_position_multiplier: 2.0
  add_drop_threshold: 3.0
  take_profit_threshold: 2.0

# ==================== 风险控制 ====================
risk_control:
  max_position_pct: 80  # 最大仓位比例（%）
  stop_loss_pct: 10     # 止损比例（%）

# ==================== 数据源配置 ====================
data_source:
  tencent_api: true     # 使用腾讯财经API
  fallback_to_sina: true # 失败时降级到新浪

# ==================== API服务配置 ====================
api:
  host: "0.0.0.0"
  port: 8000
  debug: false

# ==================== 定时任务配置 ====================
scheduler:
  enabled: true
  trading_check_interval: 1.1      # 交易时间检查间隔（分钟）
  non_trading_check_interval: 10.0 # 非交易时间检查间隔（分钟）
  run_immediately_on_start: true   # 启动时立即执行

# ==================== 股票资讯监控 ====================
stock_news_monitor:
  enabled: true
  stock_pool:
    - code: "sz.000792"
      name: "盐湖股份"
  schedule:
    hour: 21
    minute: 0
    second: 0

# ==================== 买入委托调度器 ====================
buy_order_scheduler:
  enabled: true
  hour: 9
  minute: 26
  min_score: 1.0

# ==================== 飞书通知配置 ====================
notification:
  feishu:
    enabled: true
    webhook_url: "https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_WEBHOOK_URL"

# ==================== 数据库配置 ====================
database:
  enabled: false  # 暂未启用
  url: "sqlite:///stockbot.db"

# ==================== 通达信数据目录 ====================
TDX_DIR: "D:\\Install\\zd_zxzq_gm"
```

### 配置项详细说明

#### ETF个性化配置优先级

1. **个性化配置优先**：如果symbol配置了某参数，使用该值
2. **全局配置兜底**：如果symbol未配置，使用 `strategy` 节点的全局默认值
3. **向后兼容**：不配置个性化参数时，系统行为与之前完全一致

可配置的个性化参数：
- `add_drop_threshold` - 加仓跌幅阈值（%）
- `take_profit_threshold` - 止盈涨幅阈值（%）
- `max_add_positions` - 最大加仓次数
- `initial_position_pct` - 初始建仓比例（%）

保持全局统一的参数：
- `add_position_multiplier` - 加仓倍数
- `max_position_pct` - 最大仓位比例

---

## 📊 核心功能详解

### 1. 持续放量选股

**功能说明**：基于通达信本地数据，筛选连续N天成交量递增的强势股票。

**运行方式**：
```bash
python local/select_stocks_volume.py
```

**选股流程**：
1. 获取全市场A股列表（通过akshare）
2. 过滤ST/*ST/退市股票
3. 检测停牌状态（最新成交量为0则判定停牌）
4. 检查最近5天成交量是否严格递增
5. 计算每只选中股票的综合评分
6. 保存结果到 `data/stockpool_YYYYMMDD.txt`

**输出示例**：
```
================================================================================
✅ 选股完成！
📊 扫描总数: 5000 只
🚫 过滤ST/退市股: 150 只
🚫 过滤停牌股: 25 只
🎯 选中数量: 10 只
📈 选中比例: 0.20%
================================================================================
```

**综合评分维度**：
- 均线排列（MA5/10/20/60）
- MACD金叉/死叉及位置
- RSI强弱区域
- 布林带突破情况
- 成交量变化

评分范围：-6.0（极弱）~ +6.0（极强）

### 2. ETF T+0 马丁格尔交易

**策略原理**：
- **初始建仓**：投入预设比例的資金
- **下跌加仓**：每下跌一定比例，加倍买入摊薄成本
- **上涨止盈**：当价格上涨到平均成本的止盈阈值时卖出

**配置示例**：
```yaml
symbols:
  - code: "sh.513120"
    name: "港股创新药ETF"
    add_drop_threshold: 3.5  # 每下跌3.5%加仓一次
    take_profit_threshold: 4.0 # 盈利4%时止盈
    max_add_positions: 4     # 最多加仓4次
    initial_position_pct: 6  # 初始投入6%资金
```

**加仓逻辑**：
```
初始价格: 1.280元
第1次加仓价: 1.280 * (1 - 3.5%) = 1.235元 (加仓2倍)
第2次加仓价: 1.280 * (1 - 7.0%) = 1.190元 (加仓4倍)
第3次加仓价: 1.280 * (1 - 10.5%) = 1.146元 (加仓8倍)
第4次加仓价: 1.280 * (1 - 14.0%) = 1.101元 (加仓16倍)

止盈价: 加权平均成本 * (1 + 4.0%)
```

**实时监控**：
- 交易时间：每1.1分钟检查一次
- 非交易时间：每10分钟检查一次
- 自动识别交易时段（09:15-11:30, 13:00-15:00）

### 3. 自动化买入委托

**工作流程**：
```
周一到周五 09:26
    ↓
检查 data/stockpool_YYYYMMDD.txt
    ↓
文件不存在？ → 跳过，等待下一日
    ↓
文件存在？
    ↓
执行 tool_calc_buynum_simple.py
    ↓
生成 data/trade_YYYYMMDD.txt
    ↓
读取交易报告
    ↓
发送飞书通知 ✅
```

**前置检查**：
- 自动检测前一日的选股结果文件
- 如果是周一，自动追溯到周五的文件
- 文件不存在则跳过，避免无效执行

**委托计算规则**：
- 过滤综合评分 < 1.0的股票
- 每只股票分配相等资金
- 股数必须是100的倍数（A股最小交易单位）
- 计算公式：`股数 = int((总资金 / 股票数量) / 开盘价 / 100) * 100`

**通知内容**：
- 股票名称和代码
- 开盘价格
- 买入股数
- 总金额

### 4. 股票资讯监控

**数据来源**：
- **个股资讯**：新浪财经（最新3条）
- **财务公告**：东方财富网（最新1条）

**执行时间**：每天晚上 21:00（可配置）

**通知特点**：
- 彩色格式化显示
- NEW标签标记当日资讯
- 包含资讯标题、摘要、链接
- 按股票分组展示

---

## 💡 使用技巧

### 1. 后台运行

**Windows**：
```bash
start /B python main.py
```

**Linux/Mac**：
```bash
nohup python main.py > stockbot.log 2>&1 &
```

### 2. 查看日志

日志默认输出到控制台，包含：
- 信号触发记录
- 交易执行详情
- 错误和警告信息
- 系统状态播报

### 3. 停止服务

按 `Ctrl+C` 即可优雅停止，系统会自动：
- 保存当前状态
- 停止所有调度器
- 清理资源

### 4. 自定义选股周期

修改 `local/select_stocks_volume.py` 中的参数：
```python
period = 5  # 改为3表示连续3天放量
selected_stocks = main(period)
```

### 5. 调整监控频率

在 `config.yaml` 中修改：
```yaml
scheduler:
  trading_check_interval: 0.5      # 交易时间每30秒检查一次
  non_trading_check_interval: 30.0 # 非交易时间每30分钟检查一次
```

---

## ❓ 常见问题

### Q1: 如何获取飞书Webhook URL？

**A**: 
1. 打开飞书，进入目标群聊
2. 点击右上角设置 → 群机器人 → 添加机器人
3. 选择"自定义机器人"
4. 复制生成的 Webhook 地址
5. 粘贴到 `config.yaml` 的 `webhook_url` 字段

### Q2: 选股结果文件在哪里？

**A**: 
- 位置：项目根目录下的 `data/` 文件夹
- 文件名：`stockpool_YYYYMMDD.txt`
- 例如：`data/stockpool_20260423.txt`

### Q3: 为什么没有收到飞书通知？

**A**: 检查以下几点：
1. `config.yaml` 中 `notification.feishu.enabled` 是否为 `true`
2. `webhook_url` 是否正确填写
3. 网络连接是否正常
4. 查看控制台日志是否有发送失败的错误信息

### Q4: 如何禁用某个定时任务？

**A**: 在 `config.yaml` 中设置对应的 `enabled: false`：
```yaml
# 禁用资讯监控
stock_news_monitor:
  enabled: false

# 禁用买入委托
buy_order_scheduler:
  enabled: false
```

### Q5: T+0交易支持哪些ETF？

**A**: 理论上支持所有A股ETF，只需在 `config.yaml` 的 `symbols` 中添加：
```yaml
symbols:
  - code: "sh.510300"
    name: "沪深300ETF"
    enabled: true
```

### Q6: 如何查看历史交易信号？

**A**: 历史记录保存在 `signal/` 目录下，按日期分类存储为JSON文件：
```
signal/
  ├── 2026-04-23/
  │   ├── sh.513120.json
  │   └── sh.513050.json
  └── 2026-04-22/
      └── ...
```

### Q7: 选股时如何调整放量天数？

**A**: 修改 `local/select_stocks_volume.py` 最后一行：
```python
period = 5  # 改为任意天数，如3或7
selected_stocks = main(period)
```

### Q8: 系统资源占用高怎么办？

**A**: 
1. 减少监控股票数量
2. 增加检查间隔时间
3. 关闭不需要的功能（如资讯监控）
4. 使用性能更好的服务器

---

## 🛠️ 开发指南

### 项目结构

```
StockBot/
├── main.py                      # 主程序入口
├── config.yaml                  # 配置文件
├── requirements.txt             # Python依赖
├── tool_*.py                    # 独立工具脚本
│   ├── tool_bullbear_a.py      # A股多空分析
│   ├── tool_calc_buynum.py     # 买入数量计算
│   └── tool_calc_correlation.py # 相关性分析
├── local/                       # 本地工具
│   ├── select_stocks_volume.py # 持续放量选股
│   ├── calc_bb.py              # 技术指标计算
│   └── utils.py                # 通用工具函数
├── src/                         # 核心源码
│   ├── market/                 # 市场数据层
│   │   └── data_provider.py   # 数据提供者
│   ├── strategy/               # 策略层
│   │   └── engine.py          # 策略引擎
│   └── utils/                  # 工具层
│       ├── config.py          # 配置管理
│       ├── news_crawler.py    # 资讯爬虫
│       ├── news_scheduler.py  # 资讯调度器
│       ├── buy_order_scheduler.py # 买入委托调度器
│       ├── notification.py    # 通知模块
│       ├── scheduler.py       # T+0调度器
│       └── signal_storage.py  # 信号存储
├── data/                        # 数据文件目录
│   ├── stockpool_*.txt         # 选股结果
│   └── trade_*.txt             # 交易委托
├── signal/                      # 历史信号目录
└── docs/                        # 文档
```

### 添加新的选股策略

1. 在 `local/` 目录下创建新的选股脚本
2. 实现选股逻辑，返回 `(code, name)` 列表
3. 调用 `save_selected_stocks()` 保存结果
4. 参考 `select_stocks_volume.py` 的实现

### 扩展通知渠道

1. 在 `src/utils/notification.py` 中添加新的通知类
2. 实现 `send()` 方法
3. 在 `config.yaml` 中添加对应配置
4. 在主程序中初始化并调用

### 贡献代码

欢迎提交 Issue 和 Pull Request！

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

---

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

---

## 🙏 致谢

- **腾讯财经** - 提供稳定可靠的行情数据
- **新浪财经** - 提供个股资讯
- **东方财富** - 提供财务公告
- **APScheduler** - 强大的定时任务调度
- **Loguru** - 优雅的日志记录
- **FastAPI** - 高性能Web框架

---

## 📞 联系方式

- **项目主页**: https://github.com/yourusername/StockBot
- **问题反馈**: https://github.com/yourusername/StockBot/issues
- **邮箱**: seekuyym@gmail.com

---

<div align="center">

**如果这个项目对你有帮助，请给个 ⭐ Star 支持一下！**

Made with ❤️ by StockBot Team

</div>