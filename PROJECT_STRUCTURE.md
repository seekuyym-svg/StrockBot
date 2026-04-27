# StockBot 项目结构说明

本文档详细说明 StockBot 项目的目录结构、文件组织方式和各模块的职责。

---

## 📁 项目根目录结构

```
StockBot/
├── config.yaml                      # 主配置文件（YAML格式）
├── main.py                          # 应用程序主入口
│
├── tool_bullbear_a.py              # ⭐ A股多空信号分析工具
├── tool_bullbear_hk.py             # 港股多空信号分析工具
├── tool_bullbear_us.py             # 美股多空信号分析工具
├── tool_calc_relation.py           # 股票相关性分析工具
│
├── test_integration_trend.py       # 集成测试脚本（资讯监控+多空信号）
├── test_tencent_stock_metrics.py   # 腾讯财经API测试脚本
├── debug_tencent_fields.py         # 腾讯财经字段调试脚本
│
├── src/                            # 源代码目录
│   ├── __init__.py
│   ├── market/                     # 数据接入层
│   │   ├── __init__.py
│   │   └── data_provider.py        # 统一数据提供者（iTick/BaoStock/AKShare）
│   │
│   ├── models/                     # 数据模型层
│   │   ├── __init__.py
│   │   └── models.py               # SQLAlchemy ORM模型 + Pydantic模型
│   │
│   ├── strategy/                   # 策略核心层
│   │   ├── __init__.py
│   │   └── engine.py               # 马丁格尔策略引擎
│   │
│   └── utils/                      # 工具模块层
│       ├── __init__.py
│       ├── config.py               # 配置加载器（Pydantic校验）
│       ├── news_scheduler.py       # ⭐ 资讯监控调度器
│       ├── news_crawler.py         # ⭐ 资讯爬虫（新浪+东方财富）
│       ├── notification.py         # ⭐ 飞书通知模块
│       ├── scheduler.py            # 定时任务调度器
│       ├── signal_storage.py       # 信号持久化存储
│       └── market_analyzer.py      # 市场分析工具
│
├── tests/                          # 测试脚本目录
│   ├── test_baostock.py            # BaoStock数据源测试
│   ├── test_tushare.py             # Tushare数据源测试
│   └── ...                         # 其他测试脚本
│
├── docs/                           # 文档目录
│   ├── TENCENT_API_GUIDE.md        # 腾讯财经API使用指南
│   ├── BULL_BEAR_ANALYSIS_GUIDE.md # 多空信号分析功能说明
│   ├── FEISHU_TREND_SIGNAL_GUIDE.md# 飞书通知多空信号规范
│   ├── FILE_MOVE_RENAME_RECORD.md  # 文件移动操作记录
│   └── ...                         # 其他技术文档
│
├── signal/                         # 信号持久化目录
│   └── *.json                      # 历史交易信号文件
│
├── requirements.txt                # Python依赖清单（开发环境）
├── requirements_locked.txt         # Python依赖清单（生产环境，版本锁定）
├── environment.yml                 # Conda环境配置文件
├── .python-version                 # Python版本指定文件（3.12.3）
│
├── README.md                       # 项目主文档
├── PROJECT_STRUCTURE.md            # 本文件 - 项目结构说明
├── QUICKSTART.md                   # 快速开始指南
├── LICENSE                         # MIT许可证
│
└── .git/                           # Git版本控制目录
```

---

## 🎯 核心模块详解

### 1. 工具脚本层（项目根目录）

#### `tool_*.py` 系列工具

**职责**：独立的数据分析和计算工具，可直接运行。

| 文件名 | 功能描述 | 主要类/函数 | 运行方式 |
|--------|---------|------------|---------|
| `tool_bullbear_a.py` | A股多空信号分析 | `TrendAnalyzer` | `python tool_bullbear_a.py` |
| `tool_bullbear_hk.py` | 港股多空信号分析 | - | `python tool_bullbear_hk.py` |
| `tool_bullbear_us.py` | 美股多空信号分析 | - | `python tool_bullbear_us.py` |
| `tool_calc_relation.py` | 股票相关性分析 | - | `python tool_calc_relation.py` |

**特点**：
- ✅ 位于项目根目录，便于直接运行
- ✅ 采用统一的 `tool_` 前缀命名规范
- ✅ 独立于业务逻辑，可单独测试和使用
- ✅ 从 `src.utils.config` 读取配置

**示例**：
```python
from tool_bullbear_a import TrendAnalyzer

analyzer = TrendAnalyzer()
result = analyzer.analyze_stock("sz.000792", "盐湖股份")
print(f"趋势: {result['conclusion']}")
```

---

### 2. 测试脚本层（项目根目录）

#### 测试脚本列表

| 文件名 | 功能描述 | 用途 |
|--------|---------|------|
| `test_integration_trend.py` | 完整资讯监控流程测试 | 验证资讯获取+多空分析+飞书通知全流程 |
| `test_tencent_stock_metrics.py` | 腾讯财经行情指标测试 | 验证实时行情、涨跌幅、市值获取 |
| `debug_tencent_fields.py` | 腾讯财经字段调试 | 查看API返回的所有字段结构 |

**运行方式**：
```bash
python test_integration_trend.py
```

---

### 3. 源代码层（`src/` 目录）

#### 3.1 数据接入层（`src/market/`）

**职责**：统一封装各数据源的访问接口。

**核心文件**：
- `data_provider.py` - 数据提供者类

**支持的数据源**：
- **iTick API**: 实时行情数据
- **BaoStock**: 历史K线数据
- **AKShare**: 备用数据源

**使用示例**：
```python
from src.market.data_provider import DataProvider

provider = DataProvider()
data = provider.get_realtime_quote("sh.513120")
```

---

#### 3.2 数据模型层（`src/models/`）

**职责**：定义数据结构，提供ORM映射和数据验证。

**核心文件**：
- `models.py` - SQLAlchemy模型 + Pydantic模型

**包含内容**：
- **数据库表模型**：交易信号、持仓记录等
- **Pydantic验证模型**：配置校验、API请求/响应模型

**使用示例**：
```python
from src.models.models import TradeSignal

signal = TradeSignal(
    symbol="sh.513120",
    action="BUY",
    price=1.234,
    timestamp=datetime.now()
)
```

---

#### 3.3 策略核心层（`src/strategy/`）

**职责**：实现马丁格尔量化交易策略。

**核心文件**：
- `engine.py` - 策略引擎

**核心功能**：
- 马丁格尔算法实现
- 交易信号生成（买入/卖出/加仓/止盈/止损）
- 仓位管理
- 风险控制

**使用示例**：
```python
from src.strategy.engine import StrategyEngine

engine = StrategyEngine()
signal = engine.generate_signal(market_data, position)
```

---

#### 3.4 工具模块层（`src/utils/`）⭐

**职责**：提供通用工具类和辅助功能。

##### 核心模块详解

###### 1. `config.py` - 配置管理器

**功能**：
- 读取和解析 `config.yaml`
- 使用 Pydantic 进行配置校验
- 提供类型安全的配置访问

**主要类**：
- `Config` - 主配置类
- `get_config()` - 全局配置获取函数

**使用示例**：
```python
from src.utils.config import get_config

config = get_config()
symbols = config.symbols  # 获取股票列表
webhook = config.notification.feishu.webhook_url
```

---

###### 2. `news_scheduler.py` - 资讯监控调度器 ⭐

**功能**：
- 定时执行资讯监控任务
- 协调行情获取、多空分析、资讯抓取
- 构建通知数据并发送飞书消息

**主要类**：
- `NewsMonitorScheduler` - 资讯监控调度器

**核心方法**：
- `_fetch_and_send_news()` - 获取资讯并发送通知
- `_fetch_stock_metrics()` - 获取行情指标
- `start()` - 启动调度器

**工作流程**：
```
定时触发
  ↓
遍历股票池
  ↓
获取行情指标（腾讯财经）
  ↓
进行多空信号分析（TrendAnalyzer）
  ↓
抓取个股资讯（新浪财经）
  ↓
抓取公告（东方财富网）
  ↓
构建通知数据
  ↓
发送飞书通知
```

**使用示例**：
```python
from src.utils.news_scheduler import NewsMonitorScheduler

scheduler = NewsMonitorScheduler()
scheduler.start()  # 启动定时任务
```

---

###### 3. `news_crawler.py` - 资讯爬虫 ⭐

**功能**：
- 从新浪财经抓取个股最新资讯
- 从东方财富网获取财务报告公告
- HTML解析和数据提取

**主要类**：
- `NewsCrawler` - 资讯爬虫类

**核心方法**：
- `fetch_individual_news(symbol, name)` - 获取个股资讯（最新3条）
- `fetch_financial_reports(symbol, name)` - 获取公告（最新1条）
- `_fetch_from_sina()` - 新浪财经抓取
- `_parse_financial_reports_api()` - 东方财富网API解析

**数据源**：
- **新浪财经**: `https://finance.sina.com.cn/realstock/company/{symbol}/nc.shtml`
- **东方财富网**: `http://np-anotice-stock.eastmoney.com/api/security/ann`

**使用示例**：
```python
from src.utils.news_crawler import NewsCrawler

crawler = NewsCrawler()
news = crawler.fetch_individual_news("sz.000792", "盐湖股份")
for item in news[:3]:
    print(f"{item['title']} | {item['time']}")
```

---

###### 4. `notification.py` - 飞书通知模块 ⭐

**功能**：
- 发送飞书机器人消息
- 支持交互式卡片格式
- 彩色格式化涨跌幅
- Emoji标识趋势状态

**主要类**：
- `FeishuNotifier` - 飞书通知器

**核心方法**：
- `send_news_notification(news_data)` - 发送资讯通知
- `_build_news_message()` - 构建消息内容
- `send_signal_notification(signal)` - 发送交易信号通知

**通知内容结构**：
```
🏢 一、盐湖股份 (sz.000792)
📈 行情指标: 日-1.61% | 周+1.28% | 月+12.27% | 市值2004.96亿
🟢 多空信号: 多头排列（4.0分），37.89元
━━━━━━━━━━━━━━━

📰 个股资讯 (3条):
1. xxx | 2026-04-19 🔥NEW
   🔗 [查看详情](链接)

📑 公告 (1条):
1. xxx | 2026-04-18
   🔗 [查看详情](链接)
```

**使用示例**：
```python
from src.utils.notification import send_news_notification

news_data = {
    'stock_pool': [...],
    'fetch_time': '2026-04-19 14:54:00',
    'total_count': 16
}
send_news_notification(news_data)
```

---

###### 5. `scheduler.py` - 定时任务调度器

**功能**：
- 基于 APScheduler 的定时任务管理
- 智能区分交易时间和非交易时间
- 动态调整检查间隔

**主要类**：
- `TradingScheduler` - 交易调度器

**核心功能**：
- 交易时间：每1分钟检查一次
- 非交易时间：每10分钟检查一次
- 自动识别交易日和交易时段

**使用示例**：
```python
from src.utils.scheduler import TradingScheduler

scheduler = TradingScheduler()
scheduler.add_job(check_trading_signal, 'interval', minutes=1)
scheduler.start()
```

---

###### 6. `signal_storage.py` - 信号持久化存储

**功能**：
- 将交易信号保存到JSON文件
- 按日期分类存储
- 支持历史信号查询

**主要类**：
- `SignalStorage` - 信号存储器

**存储路径**：
```
signal/
├── 2026-04-19/
│   ├── sh.513120_093000.json
│   └── sh.513050_093000.json
└── 2026-04-18/
    └── ...
```

**使用示例**：
```python
from src.utils.signal_storage import SignalStorage

storage = SignalStorage()
storage.save_signal(signal)
signals = storage.load_signals_by_date("2026-04-19")
```

---

###### 7. `market_analyzer.py` - 市场分析工具

**功能**：
- RSI与BOLL结合的市场状态分析
- 自动识别超买/超卖/震荡状态
- 提供市场情绪判断

**主要类**：
- `MarketAnalyzer` - 市场分析器

**使用示例**：
```python
from src.utils.market_analyzer import MarketAnalyzer

analyzer = MarketAnalyzer()
state = analyzer.analyze_market_state(rsi, boll_position)
print(f"市场状态: {state}")
```

---

### 4. 文档层（`docs/` 目录）

#### 技术文档列表

| 文件名 | 内容描述 |
|--------|---------|
| `TENCENT_API_GUIDE.md` | 腾讯财经API接口说明、字段解析、使用示例 |
| `BULL_BEAR_ANALYSIS_GUIDE.md` | 多空信号分析系统详解、评分规则、趋势分类 |
| `FEISHU_TREND_SIGNAL_GUIDE.md` | 飞书通知多空信号显示规范、Emoji映射、格式说明 |
| `FILE_MOVE_RENAME_RECORD.md` | 文件移动与重命名操作记录、导入路径变更说明 |
| `IMPLEMENTATION_SUMMARY_TREND_SIGNAL.md` | 飞书通知多空信号功能实施总结 |
| `BUGFIX_TREND_SIGNAL.md` | 问题修复记录、排查过程、解决方案 |

**访问方式**：
```bash
# 在GitHub或本地Markdown阅读器中查看
cat docs/TENCENT_API_GUIDE.md
```

---

### 5. 信号持久化层（`signal/` 目录）

**结构**：
```
signal/
├── 2026-04-19/
│   ├── sh.513120_093000.json
│   ├── sh.513120_093500.json
│   └── sh.513050_093000.json
├── 2026-04-18/
│   └── ...
└── ...
```

**文件命名规则**：
```
{股票代码}_{HHMMSS}.json
```

**文件内容示例**：
```json
{
  "symbol": "sh.513120",
  "action": "BUY",
  "price": 1.234,
  "shares": 1000,
  "reason": "RSI超卖 + BOLL下轨支撑",
  "timestamp": "2026-04-19 09:30:00",
  "market_state": "OVERSOLD"
}
```

---

### 6. 测试层（`tests/` 目录）

#### 测试脚本列表

| 文件名 | 测试内容 |
|--------|---------|
| `test_baostock.py` | BaoStock数据源连通性和数据质量 |
| `test_tushare.py` | Tushare数据源连通性 |
| `test_akshare.py` | AKShare数据源测试 |
| `test_strategy.py` | 策略引擎单元测试 |
| `test_config.py` | 配置加载测试 |

**运行方式**：
```bash
python tests/test_baostock.py
```

---

## 🔧 配置文件说明

### `config.yaml` - 主配置文件

**结构**：
```yaml
# ==================== 基础配置 ====================
symbols:
  - code: "sh.513120"
    name: "港股创新药ETF"
    enabled: true
    
  - code: "sh.513050"
    name: "中概互联网ETF"
    enabled: true

initial_capital: 500000

# ==================== 策略配置 ====================
strategy:
  initial_position_pct: 6
  max_add_positions: 4
  add_position_multiplier: 2
  add_drop_threshold: 3.0
  take_profit_threshold: 2.0
  max_position_pct: 80

# ==================== 定时任务配置 ====================
scheduler:
  trading_check_interval: 1
  non_trading_check_interval: 10
  run_immediately_on_start: true
  enabled: true
  
  trading_hours:
    trading_days: [1, 2, 3, 4, 5]
    sessions:
      - start_time: "09:30"
        end_time: "11:30"
      - start_time: "13:00"
        end_time: "15:00"

# ==================== 股票资讯监控配置 ====================
stock_news_monitor:
  enabled: true
  
  stock_pool:
    - code: "sz.000792"
      name: "盐湖股份"
      index: "一"
    - code: "sz.002706"
      name: "良信股份"
      index: "二"
    - code: "sh.600521"
      name: "华海药业"
      index: "三"
    - code: "sz.002126"
      name: "银轮股份"
      index: "四"
  
  news_sources:
    individual_news:
      enabled: true
    financial_reports:
      enabled: true
  
  schedule:
    hour: 14
    minute: 54
    second: 0

# ==================== 飞书通知配置 ====================
notification:
  feishu:
    enabled: true
    webhook_url: "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
    notify_signals:
      - BUY
      - SELL
      - ADD
      - STOP

# ==================== 数据库配置 ====================
database:
  url: "sqlite:///./stockbot.db"
  echo: false

# ==================== 日志配置 ====================
logging:
  level: "INFO"
  format: "{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
```

---

## 📦 依赖管理

### `requirements.txt` - 开发环境依赖

```txt
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
sqlalchemy>=2.0.0
pandas>=2.0.0
numpy>=1.24.0
requests>=2.31.0
baostock>=0.8.8
akshare>=1.12.0
pyyaml>=6.0
loguru>=0.7.0
pydantic>=2.0.0
apscheduler>=3.10.0
aiohttp>=3.9.0
beautifulsoup4>=4.12.0
```

### `requirements_locked.txt` - 生产环境依赖（版本锁定）

精确到具体版本号，确保部署一致性。

### `environment.yml` - Conda环境配置

```yaml
name: stockbot
channels:
  - defaults
dependencies:
  - python=3.12.3
  - pip
  - pip:
    - -r requirements_locked.txt
```

### `.python-version` - Python版本指定

```
3.12.3
```

配合 `pyenv` 或 `conda` 自动切换Python版本。

---

## 🚀 运行方式总结

### 1. 启动完整系统

```bash
python main.py
```

启动内容：
- ✅ FastAPI Web服务
- ✅ 定时任务调度器
- ✅ 资讯监控任务
- ✅ 飞书通知服务

### 2. 单独运行工具脚本

```bash
# 多空信号分析
python tool_bullbear_a.py

# 资讯监控测试
python test_integration_trend.py

# 腾讯财经API测试
python test_tencent_stock_metrics.py
```

### 3. 使用 `-m` 参数运行模块

```bash
# 从项目根目录运行
python -m src.utils.bull_bear_a  # 如果文件在src/utils/下
```

**注意**：由于 `tool_bullbear_a.py` 已移动到项目根目录，现在可以直接运行，无需 `-m` 参数。

---

## 📊 模块依赖关系图

```
main.py
  ├── src/utils/config.py
  ├── src/market/data_provider.py
  ├── src/strategy/engine.py
  ├── src/utils/scheduler.py
  └── src/utils/news_scheduler.py
        ├── tool_bullbear_a.py
        ├── src/utils/news_crawler.py
        └── src/utils/notification.py
```

**依赖说明**：
- `main.py` 是应用入口，初始化所有核心组件
- `news_scheduler.py` 依赖 `tool_bullbear_a.py` 进行多空分析
- `news_crawler.py` 和 `notification.py` 被 `news_scheduler.py` 调用
- 所有模块都通过 `config.py` 读取配置

---

## 🎯 最佳实践

### 1. 添加新功能

**步骤**：
1. 确定功能类别（工具/业务/数据）
2. 选择合适的目录：
   - 独立工具 → 项目根目录 `tool_xxx.py`
   - 业务逻辑 → `src/strategy/` 或 `src/utils/`
   - 数据接入 → `src/market/`
3. 实现功能并编写测试
4. 更新相关文档

### 2. 修改配置

**步骤**：
1. 编辑 `config.yaml`
2. 如需新增配置项，同步更新 `src/utils/config.py` 中的Pydantic模型
3. 重启应用使配置生效

### 3. 编写测试

**位置**：`tests/` 目录或项目根目录（简单测试）

**命名规范**：`test_*.py`

**运行方式**：
```bash
python tests/test_xxx.py
```

### 4. 文档维护

**原则**：
- 代码变更同步更新文档
- 重要功能编写独立文档放入 `docs/`
- README保持简洁，详细内容放入专门文档

---

## 🔍 常见问题

### Q1: 为什么有些文件在根目录，有些在 src/ 下？

**A**: 
- **根目录的 `tool_*.py`**：独立工具脚本，可直接运行，不依赖复杂包结构
- **`src/` 下的模块**：业务逻辑模块，需要作为包导入使用

### Q2: 如何添加新的工具脚本？

**A**:
1. 在项目根目录创建 `tool_xxx.py`
2. 实现核心功能
3. 添加 `if __name__ == "__main__":` 入口
4. 在README中补充说明

### Q3: 信号文件存储在哪个目录？

**A**: `signal/` 目录，按日期自动创建子目录。

### Q4: 如何查看历史信号？

**A**:
```bash
# 列出某天的信号
ls signal/2026-04-19/

# 查看具体内容
cat signal/2026-04-19/sh.513120_093000.json
```

---

## 📝 版本历史

| 版本 | 日期 | 主要变更 |
|------|------|---------|
| v3.0.0 | 2026-04-19 | 新增资讯监控、多空信号分析、飞书通知功能；工具脚本移至根目录 |
| v2.0.0 | - | 马丁格尔策略系统核心功能 |
| v1.0.0 | - | 初始版本 |

---

<div align="center">

**最后更新**: 2026-04-19  
**维护人员**: StockBot Team

</div>
