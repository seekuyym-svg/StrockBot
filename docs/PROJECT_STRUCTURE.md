# 项目结构说明

```
StockBot/
│
├── 📄 README.md                      # 完整项目文档
├── 📄 QUICKSTART.md                  # 快速启动指南
├── 📄 REFACTORING_SUMMARY.md        # 重构总结文档
├── 📄 PROJECT_STRUCTURE.md          # 本文件 - 项目结构说明
│
├── ⚙️  config.yaml                   # 系统配置文件
├── 📋 requirements.txt               # Python依赖列表
│
├── 🚀 main.py                        # 主程序入口（FastAPI服务）
├── 🧪 test_etf_system.py            # 系统测试脚本
├── ▶️  start.py                      # 快速启动脚本
│
└── 📁 src/                           # 源代码目录
    │
    ├── 📁 market/                    # 市场数据模块
    │   ├── __init__.py
    │   └── data_provider.py         # 东方财富网数据提供者 ⭐核心
    │
    ├── 📁 models/                    # 数据模型模块
    │   ├── __init__.py
    │   └── models.py                # Pydantic和SQLAlchemy模型定义
    │
    ├── 📁 strategy/                  # 策略引擎模块
    │   ├── __init__.py
    │   └── engine.py                # 马丁格尔策略引擎 ⭐核心
    │
    └── 📁 utils/                     # 工具模块
        ├── __init__.py
        └── config.py                # 配置管理工具
```

## 📂 核心文件详解

### 1. config.yaml - 系统配置

**作用**: 集中管理所有系统配置参数

**主要配置项**:
```yaml
symbols:                    # 交易标的列表
  - code: "sh.513120"      # ETF代码
    name: "港股创新药ETF"   # ETF名称
    enabled: true           # 是否启用

initial_capital: 500000    # 初始资金

strategy:                   # 马丁格尔策略参数
  initial_position_pct: 10  # 初始建仓比例(%)
  max_add_positions: 4      # 最大加仓次数
  add_position_multiplier: 2 # 加仓倍数
  add_drop_threshold: 5     # 加仓跌幅阈值(%)
  take_profit_threshold: 3  # 止盈涨幅(%)

filters:                    # 过滤器配置
  market_filter:           # 大盘环境过滤
  trend_filter:            # 趋势过滤
  volume_filter:           # 成交量过滤
  time_filter:             # 时间窗口过滤

api:                        # API服务配置
  host: "0.0.0.0"
  port: 8080

database:                   # 数据库配置
  type: "sqlite"
  path: "data/trading.db"
```

### 2. src/market/data_provider.py - 数据提供者 ⭐

**作用**: 从东方财富网获取实时行情和历史K线数据

**核心类**: `EastMoneyDataProvider`

**主要方法**:
- `get_realtime_data(symbol)`: 获取实时行情
- `_get_historical_klines(symbol, days)`: 获取历史K线
- `_calculate_indicators(df)`: 计算技术指标
- `get_sh_index()`: 获取上证指数

**数据流程**:
```
东方财富API → 解析JSON → 计算指标 → 返回MarketData对象
```

**关键字段映射**:
```python
f43 → current_price (最新价)
f46 → open_price (今开)
f44 → high_price (最高)
f45 → low_price (最低)
f47 → volume (成交量)
f48 → amount (成交额)
f170 → change_pct (涨跌幅)
```

### 3. src/strategy/engine.py - 策略引擎 ⭐

**作用**: 实现马丁格尔策略逻辑，生成交易信号

**核心类**: `MartingaleEngine`

**主要方法**:
- `analyze(symbol)`: 分析单个ETF并生成信号
- `get_all_signals()`: 获取所有ETF的信号
- `_apply_filters(market_data)`: 应用过滤器
- `_generate_signal(position, market_data)`: 生成交易信号
- `_check_buy_conditions()`: 检查买入条件
- `_create_buy_signal()`: 创建买入信号
- `_create_add_signal()`: 创建加仓信号
- `_create_sell_signal()`: 创建卖出/止损信号

**信号类型**:
- `BUY`: 初始建仓
- `ADD`: 加仓
- `SELL`: 止盈卖出
- `STOP`: 止损卖出
- `WAIT`: 观望

**策略状态机**:
```
NONE (无持仓)
  ↓ BUY
INIT (初始建仓)
  ↓ ADD (下跌)
ADDING (加仓中)
  ↓ ADD (继续下跌)
FULL (满仓)
  ↓ SELL (上涨) 或 STOP (大跌)
CLOSED (已平仓)
  ↓ BUY (重新建仓)
NONE
```

### 4. src/models/models.py - 数据模型

**作用**: 定义数据结构（Pydantic）和数据库模型（SQLAlchemy）

**核心模型**:

**Pydantic模型** (用于API):
- `Signal`: 交易信号
- `Position`: 持仓信息
- `MarketData`: 市场数据
- `OrderRecord`: 订单记录

**SQLAlchemy模型** (用于数据库):
- `DBPosition`: 持仓数据库表
- `DBSignal`: 信号记录表
- `DBOrder`: 订单记录表

**枚举类型**:
- `SignalType`: BUY, ADD, SELL, STOP, WAIT
- `PositionStatus`: NONE, INIT, ADDING, FULL, CLOSED

### 5. src/utils/config.py - 配置管理

**作用**: 加载和解析config.yaml配置文件

**主要功能**:
- 使用PyYAML读取YAML文件
- 使用Pydantic进行配置校验
- 提供全局配置访问接口

**使用示例**:
```python
from src.utils.config import get_config

config = get_config()
print(config.initial_capital)
print(config.strategy.add_drop_threshold)
```

### 6. main.py - 主程序入口

**作用**: 启动FastAPI Web服务

**主要功能**:
- 创建FastAPI应用实例
- 定义API路由
- 启动Uvicorn服务器

**API路由**:
- `GET /`: 根路径
- `GET /api/health`: 健康检查
- `GET /api/signals`: 获取所有信号
- `GET /api/signal/{symbol}`: 获取单个信号
- `GET /api/positions`: 获取所有持仓
- `GET /api/position/{symbol}`: 获取单个持仓
- `POST /api/position/{symbol}/reset`: 重置持仓
- `GET /api/market/{symbol}`: 获取市场数据
- `GET /api/market/index/sh`: 获取上证指数
- `GET /api/config`: 获取配置信息

### 7. test_etf_system.py - 测试脚本

**作用**: 验证系统功能是否正常

**测试内容**:
1. 数据提供者测试
   - 获取上证指数
   - 获取ETF实时行情
   - 验证技术指标计算

2. 策略引擎测试
   - 生成交易信号
   - 检查持仓状态

3. API端点提示
   - 列出可用的API接口

### 8. start.py - 快速启动脚本

**作用**: 一键启动系统

**执行流程**:
1. 检查依赖是否安装
2. 询问是否运行测试
3. 启动FastAPI服务

**使用方法**:
```bash
python start.py
```

## 🔄 数据流转图

```
用户请求
   ↓
FastAPI路由 (main.py)
   ↓
策略引擎 (engine.py)
   ↓
数据提供者 (data_provider.py)
   ↓
东方财富API
   ↓
解析数据 + 计算指标
   ↓
生成交易信号
   ↓
返回JSON响应
```

## 📊 典型调用链

### 获取交易信号

```
GET /api/signals
  ↓
get_all_signals() [engine.py]
  ↓
for each symbol:
  analyze(symbol)
    ↓
  get_market_data(symbol) [data_provider.py]
    ↓
  requests.get(eastmoney_api)
    ↓
  parse_response()
    ↓
  calculate_indicators()
    ↓
  apply_filters()
    ↓
  generate_signal()
    ↓
  return Signal object
```

### 重置持仓

```
POST /api/position/sh.513120/reset
  ↓
reset_position("sh.513120") [engine.py]
  ↓
position.status = NONE
position.add_count = 0
...
  ↓
return success
```

## 🎯 关键设计模式

### 1. 单例模式

**策略引擎**:
```python
_strategy_engine_instance = None

def get_strategy_engine():
    global _strategy_engine_instance
    if _strategy_engine_instance is None:
        _strategy_engine_instance = MartingaleEngine()
    return _strategy_engine_instance
```

**数据提供者**:
```python
_data_provider = None

def get_market_data(symbol):
    global _data_provider
    if _data_provider is None:
        _data_provider = EastMoneyDataProvider()
    return _data_provider.get_realtime_data(symbol)
```

### 2. 提供者模式

`EastMoneyDataProvider` 封装了所有数据获取逻辑，对外提供统一接口。

### 3. 策略模式

`MartingaleEngine` 实现了马丁格尔策略，可以轻松替换为其他策略。

## 🔐 安全注意事项

1. **API密钥**: 当前版本不需要API密钥
2. **输入校验**: 使用Pydantic自动校验输入
3. **错误处理**: 所有外部调用都有异常捕获
4. **重试机制**: HTTP请求失败会自动重试3次

## 🚀 扩展建议

### 添加新ETF

1. 在 `config.yaml` 中添加:
```yaml
symbols:
  - code: "sh.XXXXXX"
    name: "新ETF名称"
    enabled: true
```

2. 在 `data_provider.py` 的 `etf_codes` 字典中添加映射:
```python
self.etf_codes = {
    "sh.513120": "513120",
    "sh.513050": "513050",
    "sh.XXXXXX": "XXXXXX"  # 新增
}
```

### 添加新策略

1. 创建新的策略引擎类
2. 实现 `analyze()` 方法
3. 在 `main.py` 中切换使用的策略引擎

### 添加备用数据源

1. 创建新的数据提供者类
2. 实现相同的接口方法
3. 在主数据提供者中添加fallback逻辑

## 📝 开发规范

### 代码风格

- 使用UTF-8编码
- 遵循PEP 8规范
- 函数和类要有文档字符串
- 使用类型注解

### 日志规范

```python
logger.debug("调试信息")
logger.info("一般信息")
logger.warning("警告信息")
logger.error("错误信息")
logger.success("成功信息")
```

### 错误处理

```python
try:
    # 可能失败的代码
    result = some_operation()
except SpecificException as e:
    logger.error(f"操作失败: {e}")
    return None
```

## 🎓 学习路线

### 初级（理解系统）

1. 阅读 `config.yaml` 了解配置
2. 运行 `test_etf_system.py` 查看输出
3. 访问 `/docs` 探索API接口
4. 阅读 `README.md` 理解策略原理

### 中级（修改参数）

1. 调整 `config.yaml` 中的策略参数
2. 观察信号变化
3. 理解过滤器的作用
4. 尝试不同的参数组合

### 高级（扩展功能）

1. 添加新的ETF标的
2. 实现自定义过滤器
3. 优化策略算法
4. 添加回测功能

---

**最后更新**: 2026-04-13  
**版本**: v2.0.0
