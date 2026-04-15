# StockBot - A股马丁格尔量化交易系统
# A-Share Martingale Quantitative Trading System

<div align="center">

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)
![Version](https://img.shields.io/badge/Version-2.0.0-orange.svg)

**智能ETF交易信号系统 | 实时行情监控 | 飞书通知推送 | RSI技术分析**

[快速开始](#-快速开始) • [核心功能](#-核心功能) • [配置指南](#-配置指南) • [API文档](#-api文档) • [故障排查](#-故障排查)

</div>

---

## 📖 项目简介

StockBot 是一个基于**马丁格尔策略**的A股ETF量化交易系统，专注于**港股创新药ETF (sh.513120)** 和 **中概互联网ETF (sh.513050)** 的自动化交易信号生成。

### ✨ 核心特性

- 🔄 **自动定时检查** - 每5分钟自动获取交易信号（可配置）
- 📊 **多指标分析** - BOLL布林带 + RSI相对强弱指数双重判断
- 💬 **飞书实时通知** - 重要信号即时推送到飞书群聊
- 💾 **信号持久化** - 自动保存历史信号到JSON文件
- 🎯 **智能过滤** - 大盘环境、趋势确认、量价配合多重验证
- ⏰ **交易时间控制** - 仅在A股交易时段执行检查
- 🌐 **RESTful API** - 提供完整的HTTP接口服务

### 🎯 适用场景

- ✅ ETF定投自动化监控
- ✅ 量化策略回测与实盘
- ✅ 交易信号实时提醒
- ✅ 投资组合管理辅助

---

## 🚀 快速开始

### 第一步：安装依赖

```bash
# 克隆项目
git clone https://github.com/yourusername/StockBot.git
cd StockBot

# 安装依赖
pip install -r requirements.txt
```

### 第二步：配置系统

编辑 `config.yaml` 文件（可选配置）：

```yaml
# 基础配置 - 支持个性化策略参数
symbols:
  - code: "sh.513120"  # 港股创新药ETF
    name: "港股创新药ETF"
    enabled: true
    # 个性化策略参数（可选，不设置则使用全局默认值）
    add_drop_threshold: 3.0  # 加仓跌幅阈值：下跌3%加仓
    take_profit_threshold: 2.0  # 止盈涨幅：盈利2%止盈
    
  - code: "sh.513050"  # 中概互联网ETF
    name: "中概互联网ETF"
    enabled: true
    add_drop_threshold: 3.5  # 加仓跌幅阈值：下跌3.5%加仓
    take_profit_threshold: 2.5  # 止盈涨幅：盈利2.5%止盈

initial_capital: 500000  # 初始资金

# 全局默认策略配置（当symbol未配置个性化参数时使用）
strategy:
  initial_position_pct: 6  # 初始建仓比例（占总资金百分比）
  max_add_positions: 4     # 最大加仓次数
  add_position_multiplier: 2  # 加仓倍数
  add_drop_threshold: 3.0  # 全局默认加仓跌幅阈值
  take_profit_threshold: 2.0  # 全局默认止盈涨幅
  max_position_pct: 80     # 单只股票最大持仓比例

# 定时任务配置
scheduler:
  # 智能检查间隔（推荐）
  trading_check_interval: 1           # 交易时间检查间隔（分钟）
  non_trading_check_interval: 10      # 非交易时间检查间隔（分钟）
  
  run_immediately_on_start: true    # 启动时立即执行
  enabled: true                     # 启用定时任务
  
  # 交易时间配置
  trading_hours:
    trading_days: [1, 2, 3, 4, 5]  # 周一到周五
    sessions:
      - start_time: "09:30"         # 上午时段
        end_time: "11:30"
      - start_time: "13:00"         # 下午时段
        end_time: "15:00"

# 飞书通知配置（可选）
notification:
  feishu:
    enabled: false                    # 默认禁用，需要时改为true
    webhook_url: "YOUR_WEBHOOK_URL"   # 飞书机器人Webhook
    notify_signals: ["BUY", "SELL", "ADD", "STOP"]
```

**💡 提示**：从 v2.1.0 开始，支持为不同 ETF 分别配置个性化的策略参数。详见 [个性化配置指南](docs/PERSONALIZED_CONFIG_GUIDE.md)。

### 第三步：启动系统

```bash
python main.py
```

启动后会看到：

```
============================================================
ETF链接基金T+0马丁格尔量化交易系统启动
============================================================
✅ 定时任务调度器启动成功
🚀 立即执行首次信号检查...
✅ 定时任务已启动，每5分钟自动检查信号
```

---

## 🎯 核心功能

### 1️⃣ 自动定时信号检查

系统会按照配置的间隔（默认5分钟）自动检查交易信号：

**控制台输出示例：**

```
============================================================
🟢 【重要信号】2026-04-14 17:49:20
============================================================
标的: 港股创新药ETF广发 (sh.513120)
信号: BUY
价格: ¥1.281
涨跌幅: +0.71%
目标份额: 14,000
平均成本: ¥1.281
📊 BOLL上轨-5.56% | 中轨+4.22% ← 此轨最近 | 下轨+13.99%
📈 RSI: 74.32 (🔴 超买区 ⚠️)
原因: 初始建仓：买入14000份，成本1.281元/份
============================================================
```

**信号类型说明：**

| 图标 | 信号 | 处理方式 | 说明 |
|------|------|----------|------|
| 🟢 | BUY | 打印+持久化+飞书通知 | 初始建仓信号 |
| 🔵 | ADD | 打印+持久化+飞书通知 | 分批加仓信号 |
| 🔴 | SELL | 打印+持久化+飞书通知 | 止盈卖出信号 |
| ⚠️ | STOP | 打印+持久化+飞书通知 | 止损信号 |
| ⏸️ | WAIT | 仅打印 | 观望等待信号 |

### 2️⃣ RSI技术指标分析

系统实时计算并显示RSI（相对强弱指数），帮助判断市场状态：

**RSI区域判断：**

| RSI值 | 区域 | 标识 | 含义 |
|-------|------|------|------|
| > 70 | 超买区 | 🔴 ⚠️ | 市场可能过热，注意回调风险 |
| 30-70 | 中性区 | 🟡 | 市场正常波动范围 |
| < 30 | 超卖区 | 🟢 ✅ | 市场可能超跌，关注反弹机会 |

**使用建议：**
- RSI超买 + 价格接近BOLL上轨 → 强烈回调信号
- RSI超卖 + 价格接近BOLL下轨 → 强烈反弹机会
- RSI中性 + 价格在BOLL中轨附近 → 震荡行情

### 3️⃣ 智能市场研判 ⭐ 新功能

系统基于**RSI指标**和**BOLL布林带**进行综合分析，自动给出市场研判：

**研判规则：**

| 条件 | 研判结果 | 含义 |
|------|----------|------|
| RSI > 70 + 距BOLL上轨 ≤ 5% | 💡 回调 | 市场过热，存在回调风险 ⚠️ |
| RSI < 30 + 距BOLL下轨 ≤ 5% | 💡 反弹 | 市场超跌，存在反弹机会 ✅ |
| 30 ≤ RSI ≤ 70 + 距BOLL中轨 ≤ 5% | 💡 震荡 | 市场平衡，区间整理阶段 🔄 |
| 其他情况 | 💡 暂无 | 状态不明确，继续观望 ⏸️ |

**控制台输出示例：**

```
============================================================
🟢 【重要信号】2026-04-14 21:05:00
============================================================
标的: 港股创新药ETF广发 (sh.513120)
信号: BUY
价格: ¥1.281
涨跌幅: +0.71%
目标份额: 14,000
平均成本: ¥1.281
📊 BOLL: 上轨-5.56% | 中轨+4.22% ← 此轨最近 | 下轨+13.99%
📈 RSI: 74.32 (🔴 超买区 ⚠️)
💡 研判: 回调 - RSI超买且价格接近BOLL上轨，市场可能过热，存在回调风险 ⚠️
原因: 初始建仓：买入14000份，成本1.281元/份
============================================================
```

**飞书通知同步：**

研判结果会同步推送到飞书，帮助您快速判断市场状态并调整交易策略。

详细文档：[市场研判功能说明](docs/MARKET_ANALYSIS_GUIDE.md)

### 4️⃣ 飞书实时通知

当触发重要信号时，系统会自动推送到飞书群聊：

**配置步骤：**

1. **获取飞书Webhook URL**
   - 打开飞书群聊 → 群机器人 → 添加机器人 → 自定义机器人
   - 复制生成的Webhook URL

2. **修改配置文件**
   ```yaml
   notification:
     feishu:
       enabled: true
       webhook_url: "https://open.feishu.cn/open-apis/bot/v2/hook/xxxxx"
       notify_signals: ["BUY", "SELL", "ADD", "STOP"]
   ```

3. **重启系统**
   ```bash
   python main.py
   ```

**通知效果：**

飞书消息卡片会显示完整的交易信息，包括标的、价格、涨跌幅、BOLL指标、RSI指标等。

### 5️⃣ 信号持久化存储

所有重要信号（BUY/ADD/SELL/STOP）会自动保存到JSON文件：

**文件结构：**
```
signal/
├── 2026-04-14/
│   ├── sh_513120_174920.json
│   ├── sh_513050_175000.json
│   └── ...
└── 2026-04-13/
    └── ...
```

**查询历史信号：**
```bash
# 通过API查询
curl http://localhost:8080/api/signals/today
curl "http://localhost:8080/api/signals/history?days=7"

# 直接查看文件
cat signal/2026-04-14/sh_513120_174920.json
```

### 6️⃣ RESTful API服务

系统提供完整的HTTP API接口：

**核心接口：**

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/signal/{symbol}` | GET | 获取指定标的信号 |
| `/api/signals` | GET | 获取所有标的信号 |
| `/api/signals/today` | GET | 获取今日信号 |
| `/api/signals/history` | GET | 获取历史信号 |
| `/api/market/{symbol}` | GET | 获取市场数据 |
| `/api/positions` | GET | 获取持仓状态 |

**访问API文档：**
```
http://localhost:8080/docs
```

---

## ⚙️ 配置指南

### 完整配置示例

```
# ==================== 基础配置 ====================
symbols: ["sh.513120", "sh.513050"]
initial_capital: 500000
max_add_times: 5
add_multiplier: 2
add_threshold_pct: -8.0
take_profit_pct: 6.0

# ==================== 定时任务配置 ====================
scheduler:
  # 智能检查间隔（推荐）
  trading_check_interval: 1           # 交易时间检查间隔（分钟）
  non_trading_check_interval: 10      # 非交易时间检查间隔（分钟）
  
  # 兼容旧配置（已废弃）
  signal_check_interval: 5            # 固定检查间隔
  
  run_immediately_on_start: true    # 启动时立即执行
  enabled: true                     # 启用定时任务
  
  # 交易时间配置
  trading_hours:
    trading_days: [1, 2, 3, 4, 5]  # 周一到周五
    sessions:
      - start_time: "09:30"         # 上午时段
        end_time: "11:30"
      - start_time: "13:00"         # 下午时段
        end_time: "15:00"

# ==================== 飞书通知配置 ====================
notification:
  feishu:
    enabled: false                  # 是否启用
    webhook_url: ""                 # Webhook URL
    notify_signals:                 # 通知的信号类型
      - "BUY"
      - "SELL"
      - "ADD"
      - "STOP"

# ==================== 数据库配置 ====================
database:
  url: "sqlite:///./stockbot.db"
  echo: false

# ==================== 日志配置 ====================
logging:
  level: "INFO"
  log_dir: "./logs"
  retention_days: 30
```

### 常见配置场景

#### 场景1：智能间隔（推荐）⭐

```
scheduler:
  trading_check_interval: 1           # 交易时间1分钟检查
  non_trading_check_interval: 10      # 非交易时间10分钟检查
  trading_hours:
    trading_days: [1, 2, 3, 4, 5]
    sessions:
      - start_time: "09:30"
        end_time: "11:30"
      - start_time: "13:00"
        end_time: "15:00"
```

**优势:**
- ✅ 交易时间高频检查，及时捕捉信号
- ✅ 非交易时间低频检查，节省资源
- ✅ 自动切换，无需手动干预

#### 场景2：仅交易时间运行

```
scheduler:
  signal_check_interval: 5
  trading_hours:
    trading_days: [1, 2, 3, 4, 5]
    sessions:
      - start_time: "09:30"
        end_time: "11:30"
      - start_time: "13:00"
        end_time: "15:00"
```

#### 场景3：启用飞书通知

```
notification:
  feishu:
    enabled: true
    webhook_url: "https://open.feishu.cn/open-apis/bot/v2/hook/xxxxx"
    notify_signals: ["BUY", "SELL"]  # 仅通知买卖
```

#### 场景4：调整检查频率

```
scheduler:
  signal_check_interval: 3  # 改为3分钟检查一次
```

#### 场景5：临时禁用定时任务

```
scheduler:
  enabled: false  # 禁用定时任务，仅保留API服务
```

---

## 📊 策略说明

### 马丁格尔核心逻辑

1. **初始建仓**：满足条件时买入10%仓位
2. **分批加仓**：每下跌8%，2倍加仓，最多5次
3. **整体止盈**：平均成本上涨6%时全部卖出
4. **严格止损**：累计亏损超过阈值时止损

### 胜率提升机制

- ✅ **大盘环境过滤** - 上证指数趋势判断
- ✅ **趋势确认** - EMA均线系统验证
- ✅ **量价配合** - 成交量变化率验证
- ✅ **BOLL轨道** - 布林带三轨位置判断
- ✅ **RSI指标** - 相对强弱指数辅助决策
- ✅ **智能研判** - RSI+BOLL综合分析，自动给出操作建议 ⭐
- ✅ **时间窗口** - 避开开盘/收盘敏感时段

### 风险控制

- ⚠️ 最大加仓次数限制（默认5次）
- ⚠️ 单笔交易金额限制
- ⚠️ 总仓位比例控制
- ⚠️ 止损机制保护本金

---

## 🛠️ 开发指南

### 项目结构

```
StockBot/
├── src/                          # 源代码
│   ├── market/                   # 市场数据模块
│   │   └── data_provider.py      # 数据提供者
│   ├── strategy/                 # 策略引擎
│   │   └── engine.py             # 马丁格尔策略
│   ├── models/                   # 数据模型
│   │   └── models.py             # Pydantic模型
│   └── utils/                    # 工具函数
│       ├── config.py             # 配置管理
│       ├── scheduler.py          # 定时任务调度
│       └── notification.py       # 飞书通知
├── docs/                         # 文档目录
│   ├── RSI_FEATURE.md            # RSI功能说明
│   ├── FEISHU_NOTIFICATION_GUIDE.md  # 飞书通知指南
│   ├── SCHEDULER_GUIDE.md        # 定时任务指南
│   └── ...                       # 其他文档
├── signal/                       # 信号存储目录
├── logs/                         # 日志目录
├── config.yaml                   # 配置文件
├── main.py                       # 主程序入口
├── requirements.txt              # 依赖包列表
└── README.md                     # 项目说明
```

### 技术栈

- **Web框架**: FastAPI >= 0.104.0
- **ASGI服务器**: Uvicorn >= 0.24.0
- **数据处理**: Pandas >= 2.0.0, Numpy >= 1.24.0
- **数据库**: SQLAlchemy >= 2.0.0
- **定时任务**: APScheduler >= 3.10.0
- **日志**: Loguru >= 0.7.0
- **配置**: PyYAML >= 6.0, Pydantic >= 2.0.0
- **HTTP请求**: requests, aiohttp

### 本地开发

```bash
# 1. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate     # Windows

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行测试
python test_rsi_output.py
python check_feishu_config.py

# 4. 启动开发服务器
uvicorn main:app --reload --host 0.0.0.0 --port 8080
```

---

## ❓ 常见问题

### Q1: 如何修改检查间隔？

**A:** 在 `config.yaml` 中修改：
```yaml
scheduler:
  signal_check_interval: 3  # 改为3分钟
```

### Q2: 飞书通知收不到怎么办？

**A:** 检查以下几点：
1. 确认 `enabled: true`
2. 确认 `webhook_url` 正确
3. 运行测试：`python check_feishu_config.py test`
4. 查看日志是否有错误信息

### Q3: 如何查看历史信号？

**A:** 
```bash
# 方法1: 通过API
curl http://localhost:8080/api/signals/history?days=7

# 方法2: 直接查看文件
ls signal/2026-04-14/
cat signal/2026-04-14/sh_513120_*.json
```

### Q4: 非交易时间会检查信号吗？

**A:** 不会。系统会根据 `trading_hours` 配置，仅在交易时间内执行信号检查。非交易时间仅输出上证指数点数。

### Q5: 如何清理旧数据？

**A:** 可以手动删除 `signal/` 目录下的旧文件夹，或编写脚本自动清理：
```python
from pathlib import Path
import shutil
from datetime import datetime, timedelta

def cleanup_old_signals(keep_days=30):
    base_dir = Path("signal")
    cutoff_date = datetime.now() - timedelta(days=keep_days)
    
    for date_dir in base_dir.iterdir():
        if date_dir.is_dir():
            try:
                dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d")
                if dir_date < cutoff_date:
                    shutil.rmtree(date_dir)
                    print(f"已删除: {date_dir}")
            except ValueError:
                pass
```

### Q6: RSI值为None怎么办？

**A:** RSI为None表示数据源未提供该数据，此时不显示RSI信息。这不影响其他功能的正常使用。

---

## 📚 详细文档

更多详细信息请查看 `docs/` 目录下的文档：

- **[动态检查间隔指南](docs/DYNAMIC_INTERVAL_GUIDE.md)** - 交易时间和非交易时间智能切换 ⭐ 新增
- **[市场研判功能说明](docs/MARKET_ANALYSIS_GUIDE.md)** - RSI+BOLL综合研判详解
- **[RSI功能说明](docs/RSI_FEATURE.md)** - RSI指标详解和使用指南
- **[飞书通知指南](docs/FEISHU_NOTIFICATION_GUIDE.md)** - 飞书通知配置和使用
- **[定时任务指南](docs/SCHEDULER_GUIDE.md)** - 定时任务配置和管理
- **[飞书限流解决方案](docs/FEISHU_RATE_LIMIT_SOLUTION.md)** - 解决飞书API限流问题
- **[信号存储指南](docs/SIGNAL_STORAGE_GUIDE.md)** - 信号持久化存储说明
- **[故障排查手册](docs/TROUBLESHOOTING.md)** - 常见问题和解决方案

---

## ⚠️ 风险提示

- ⚠️ **本系统仅提供信号参考，不构成投资建议**
- ⚠️ **股市有风险，投资需谨慎**
- ⚠️ **建议结合个人判断做出投资决策**
- ⚠️ **过往业绩不代表未来收益**
- ⚠️ **马丁格尔策略在单边下跌行情中存在较大风险**
- ⚠️ **请在充分理解策略逻辑后再使用本系统**

---

## 📝 更新日志

### v2.2.0 (2026-04-15) - 最新版 🎉

**新增功能：**
- ✨ **动态检查间隔** - 交易时间和非交易时间使用不同的检查频率
- ✨ **智能资源调度** - 交易时间1分钟检查，非交易时间10分钟检查
- ✨ **自动切换机制** - 根据配置的交易时间自动调整检查间隔

**优化改进：**
- 🔧 重构调度器启动逻辑，支持动态间隔判断
- 🔧 保留旧配置参数用于向后兼容
- 🔧 完善启动日志，清晰显示当前使用的间隔
- 📝 新增[动态检查间隔指南](docs/DYNAMIC_INTERVAL_GUIDE.md)

**性能提升:**
- 📊 API调用量减少约60%（从576次/天降至216次/天）
- 💾 系统资源消耗显著降低
- ⚡ 交易时间响应更及时

### v2.1.0 (2026-04-14) - 最新版 🎉

**新增功能：**
- ✨ **智能市场研判** - RSI+BOLL综合分析，自动给出操作建议（回调/反弹/震荡/暂无）
- ✨ **研判结果同步** - 控制台输出和飞书通知均包含研判信息
- ✨ **灵活参数配置** - 可调整RSI阈值和BOLL接近阈值

**优化改进：**
- 🔧 创建独立的市场研判模块 `src/utils/market_analyzer.py`
- 🔧 完善研判规则的边界处理
- 🔧 增加详细的测试用例覆盖所有场景
- 📝 新增[市场研判功能说明](docs/MARKET_ANALYSIS_GUIDE.md)

### v2.0.0 (2026-04-14) - 最新版 🎉

**新增功能：**
- ✨ **RSI技术指标** - 实时计算并显示RSI指标，支持超买/中性/超卖判断
- ✨ **飞书通知同步** - 飞书消息与控制台输出完全同步，包含RSI信息
- ✨ **频率限制控制** - 智能频率控制机制，避免飞书API限流
- ✨ **信号类型优化** - 飞书通知中信号类型显示为简洁格式（如"BUY"而非"SignalType.BUY"）

**优化改进：**
- 🔧 完善BOLL布林带三轨价差计算规范
- 🔧 优化飞书通知错误处理和日志记录
- 🔧 增加配置检查工具 `check_feishu_config.py`
- 📝 更新完整的项目文档

### v1.3.0 (2026-04-13)

- ✨ 飞书机器人通知功能
- ✨ 定时信号检查任务
- ✨ 信号持久化存储
- 🔧 交易时间智能控制

### v1.2.0 (2026-03-19)

- ✨ BaoStock数据源支持
- 🔧 多数据源fallback机制

### v1.0.0 (2026-03-17)

- 🎉 初始版本发布

---

## 🤝 贡献指南

欢迎提交Issue和Pull Request！

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

---

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

---

## 📞 联系方式

- 📧 Email: your.email@example.com
- 💬 微信群: 扫码加入交流群
- 🐛 Issues: [GitHub Issues](https://github.com/yourusername/StockBot/issues)

---

<div align="center">

**⭐ 如果这个项目对您有帮助，请给个Star！**

Made with ❤️ by StockBot Team

</div>




















