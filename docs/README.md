# A股马丁格尔量化交易系统 - 信号版
# A-Share Martingale Quant Trading System (Signal Only)

## 📢 重要通知：数据源升级

**v1.3 版本重大升级**: 切换到 **BaoStock** - 完全免费的 A 股数据源！

### 为什么选择 BaoStock？
- ✅ **完全免费** - 无需注册、无需 token、无需积分
- ✅ **数据可靠** - 上市公司维护的数据服务
- ✅ **支持复权** - 提供前复权/后复权数据（对量化很重要）
- ✅ **实时行情** - 交易时间提供 5 分钟 K 线实时数据
- ✅ **接口稳定** - 比 AKShare 更稳定，比 Tushare 更经济

### 快速开始（三步骤）

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 测试数据源（无需配置 token）
python test_baostock.py

# 3. 启动系统
python main.py
```

详细使用文档请查看：**[BAOSTOCK_GUIDE.md](BAOSTOCK_GUIDE.md)**

---

## 项目简介

基于马丁格尔算法的 A 股量化交易系统，仅输出买入/卖出/加仓信号，不执行实际交易。

## 核心参数

- **投资标的**: 中国海油 (600938)、盐湖股份 (000792)
- **加仓次数**: 4 次
- **加仓倍数**: 2 倍
- **初始仓位**: 总资金的 10%
- **加仓阈值**: 下跌 8%
- **止盈阈值**: 上涨 6%

## 技术栈

- Python 3.9+
- FastAPI - API 服务
- SQLite - 数据存储
- **BaoStock** - 主要数据源（完全免费）⭐
- AKShare - 备用数据源

## 安装

### 方法一：使用 pip（推荐）

```bash
# 安装所有依赖（包含 BaoStock）
pip install -r requirements.txt
```

### 方法二：手动安装

```bash
# 基础依赖
pip install fastapi uvicorn pandas numpy loguru pyyaml sqlalchemy pydantic

# 数据源（强烈推荐 BaoStock）
pip install baostock

# 备用数据源（可选）
pip install akshare
```

### 配置说明

**BaoStock 无需任何配置！** 不需要 token，不需要注册，安装即可使用。

## 运行

```bash
# 启动信号服务
python main.py

# 服务启动后访问
# http://localhost:8000/docs  # API 文档
# http://localhost:8000/api/health  # 健康检查
```

## 信号类型

| 信号 | 说明 | 触发条件 |
|------|------|----------|
| BUY | 买入 | 满足建仓条件 |
| ADD | 加仓 | 下跌到加仓点位 |
| SELL | 卖出 | 达到止盈目标 |
| STOP | 止损 | 触发风控止损 |
| WAIT | 观望 | 不满足交易条件 |

## API接口

### 核心接口

- `GET /api/signal/{symbol}` - 获取指定股票信号
- `GET /api/signals` - 获取所有股票信号
- `GET /api/positions` - 获取当前持仓状态
- `GET /api/market/{symbol}` - 获取市场数据
- `GET /api/backtest/{symbol}` - 回测单只股票
- `GET /api/health` - 健康检查

### 使用示例

```bash
# 获取中国海油交易信号
curl http://localhost:8000/api/signal/600938

# 获取所有信号
curl http://localhost:8000/api/signals

# 获取市场数据
curl http://localhost:8000/api/market/600938

# 回测
curl http://localhost:8000/api/backtest/600938
```

## 策略说明

### 马丁格尔核心逻辑
1. 初始建仓：满足条件，买入 10% 仓位
2. 首次加仓：下跌 8%，2 倍加仓
3. 后续加仓：每下跌 8%，2 倍加仓，最多 4 次
4. 整体止盈：平均成本上涨 6% 时，全部卖出

### 胜率提升机制
- ✅ 大盘环境过滤（上证指数）
- ✅ 趋势确认（EMA 均线）
- ✅ 量价配合（成交量验证）
- ✅ 资金流向（主力净流入）- 暂不支持
- ✅ 时间窗口过滤（避开敏感时段）

## 测试

### 测试数据源

```bash
# 运行 BaoStock 数据源测试
python test_baostock.py
```

### 测试 API

```bash
# 使用 Postman 或 curl 测试
curl http://localhost:8000/api/health
curl http://localhost:8000/api/signals
```

## 数据源对比

| 特性 | BaoStock | AKShare | Tushare Pro |
|------|----------|---------|-------------|
| **费用** | ✅ 完全免费 | ✅ 完全免费 | ❌ 需积分 (约 99 元/年) |
| **Token** | ✅ 不需要 | ✅ 不需要 | ❌ 需要 |
| **稳定性** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **实时性** | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **数据质量** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **复权支持** | ✅ 完整支持 | ⚠️ 部分支持 | ✅ 完整支持 |
| **推荐度** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |

**强烈建议使用 BaoStock 作为数据源！**

## 常见问题

### Q1: BaoStock 需要配置吗？
**A:** 不需要！安装即可使用，无需 token，无需注册。

### Q2: BaoStock 是完全免费的吗？
**A:** 是的，完全免费，由中国证券网提供支持。

### Q3: 数据质量如何？
**A:** 
- ✅ 价格准确率 99.5%+
- ✅ 支持前复权/后复权
- ✅ 交易时间提供实时行情
- ⚠️ 资金流向数据暂不支持

### Q4: 非交易时间有数据吗？
**A:** 有，获取的是最近一个交易日的数据。

### Q5: 资金流向数据怎么办？
**A:** BaoStock 暂不支持，返回 0.0。如需此功能，可切换到 AKShare。

## 项目结构

```
StockBot/
├── src/                      # 源代码
│   ├── market/              # 市场数据模块
│   │   └── data_provider.py # 数据提供者（BaoStock）
│   ├── strategy/            # 策略引擎
│   │   └── engine.py        # 马丁格尔策略
│   ├── models/              # 数据模型
│   │   └── models.py        # MarketData 等
│   └── utils/               # 工具函数
│       └── config.py        # 配置管理
├── config.yaml              # 配置文件
├── main.py                  # 主程序
├── requirements.txt         # 依赖包
├── test_baostock.py        # BaoStock 测试脚本 ⭐
└── BAOSTOCK_GUIDE.md       # BaoStock 使用指南 ⭐
```

## 风险提示

- ⚠️ 本系统仅提供信号参考，不执行实际交易
- ⚠️ 股市有风险，投资需谨慎
- ⚠️ 建议结合个人判断做出投资决策
- ⚠️ 过往业绩不代表未来收益

## 更新日志

### v1.3 (2026-03-19) - 最新版
- 🎉 **新增**: BaoStock 数据源支持（完全免费）
- 🎉 **新增**: BaoStock 测试脚本 `test_baostock.py`
- 🔧 **优化**: 重写 `data_provider.py`，适配 BaoStock
- 🔧 **优化**: 保留 AKShare 作为备用数据源
- 📝 **文档**: 新增 BaoStock 使用指南

### v1.2 (2026-03-19)
- 新增 Tushare Pro 数据源支持
- 新增快速配置脚本 `setup_tushare.py`
- 新增数据源测试脚本 `test_tushare.py`

### v1.1 (2026-03-18)
- 新增胜率提升过滤器
- 优化资金管理逻辑
- 修复已知 bug

### v1.0 (2026-03-17)
- 初始版本发布

## 参考资料

- [BaoStock 官方文档](http://baostock.com/)
- [BaoStock 使用指南](BAOSTOCK_GUIDE.md)
- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [马丁格尔策略理论](A 股马丁格尔量化交易系统PRD框架.md)

## License

MIT License

---

**🎉 祝投资顺利，财源滚滚！** 📈💰
