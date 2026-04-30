# 📈 选股策略回测工具包

本目录包含对 `select_daysvol.py` 持续放量选股策略的完整回测解决方案。

## 📁 目录结构

```
backtest/
├── __init__.py                      # Python包初始化文件
│
├── 🔧 核心代码
│   ├── generate_stockpool.py        # 🆕 股票池生成器（第1步）
│   ├── backtest_engine.py           # 回测引擎（第2步）
│   ├── backtest_reporter.py         # 报告生成器
│   ├── run_backtest.py              # 主入口脚本
│   └── test_two_step.py             # 🆕 两步回测测试脚本
│
├── 🧪 测试脚本
│   ├── test_backtest.py             # 基础功能测试
│   └── test_two_step.py             # 两步回测测试
│
├── ⚙️ 配置文件
│   └── backtest_config_example.yaml # 配置示例
│
└── 📖 文档
    ├── README.md                    # 目录说明
    ├── TWO_STEP_BACKTEST.md         # 🆕 两步回测详细指南
    ├── QUICKSTART_BACKTEST.md       # 3分钟快速上手
    ├── BACKTEST_README.md           # 完整使用说明
    ├── BACKTEST_DESIGN.md           # 方案设计
    ├── BACKTEST_SUMMARY.md          # 开发总结
    ├── WHITELIST_OPTIMIZATION.md    # 白名单优化说明
    └── MIGRATION_SUMMARY.md         # 迁移总结
```

## 🚀 快速开始

### 前置准备
```bash
# 确保已生成白名单（回测工具会自动查找最新文件）
python local/manage_stock_list.py --update
```

**智能加载机制**：
- ✅ 优先使用 `data/whitelist_当天日期.txt`
- ✅ 如果当天文件不存在，自动使用最新的白名单文件
- ✅ 只有在上述都失败时，才需要通过 `--whitelist` 参数手动指定

---

### 方式一：两步回测（推荐，高效）

#### 第1步：生成股票池
```bash
python backtest/generate_stockpool.py --start-date 2024-01-01 --end-date 2026-01-01
```

**选股策略**：
- ✅ 每隔3个交易日选股一次（因为持有3个交易日）
- ✅ 避免重复选股和资金分散
- ✅ 例如：周一选股 -> 周二买入 -> 周四卖出 -> 周四再次选股

#### 第2步：执行回测（初始资金100万）
```bash
python backtest/run_backtest.py --use-stockpool
```

**优势**：
- ⚡ 速度快：股票池只需生成一次
- 🔧 灵活：可独立调整回测参数
- 📊 可追溯：可查看每日选股结果

---

### 方式二：一步回测（简单）

直接运行回测，实时选股：
```bash
python backtest/run_backtest.py --start-date 2024-01-01 --end-date 2026-01-01
```

**优势**：
- ✅ 一条命令完成
- ✅ 适合快速测试

### 3. 执行回测
```
# 基本用法
python backtest/run_backtest.py

# 自定义参数
python backtest/run_backtest.py --start-date 2024-01-01 --end-date 2026-01-01
```

## 🧠 回测逻辑说明

本回测工具严格模拟真实交易流程，具体逻辑如下：

**核心规则**：
- ✅ **只在选股日买入**：仅在股票池文件存在的日期（即选股日）触发买入信号
- ✅ **次日开盘买入**：在选股日后的第一个交易日以开盘价买入
- ✅ **持有3个交易日**：买入后持有3个交易日，在第4个交易日收盘时卖出
- ✅ **循环操作**：卖出后的下一个选股日读取新股票池并执行新一轮买入

**时间线示例**：
```
周一（选股日）: 读取股票池 -> 周二开盘买入 -> 周四收盘卖出
周二: 持有中（不操作）
周三: 持有中（不操作）
周四: 收盘卖出
周五（非选股日）: 空仓等待（不操作）
下周一（选股日）: 读取新股票池 -> 下周二开盘买入 -> ...
```

## 📚 文档导航

| 文档 | 用途 | 适合人群 |
|------|------|----------|
| [QUICKSTART_BACKTEST.md](QUICKSTART_BACKTEST.md) | ⚡ 3分钟快速上手 | 新手用户 |
| [BACKTEST_README.md](BACKTEST_README.md) | 📖 完整使用说明 | 所有用户 |
| [BACKTEST_DESIGN.md](BACKTEST_DESIGN.md) | 🎨 方案设计详情 | 开发者/研究者 |
| [BACKTEST_SUMMARY.md](BACKTEST_SUMMARY.md) | 📝 开发总结 | 技术review |

## 🔧 核心模块说明

### backtest_engine.py
回测引擎核心，包含：
- `BacktestEngine` 类：完整的回测逻辑
- `TradeRecord` 类：交易记录数据结构
- 主要功能：加载数据、模拟交易、计算指标

### backtest_reporter.py
报告生成器，包含：
- `BacktestReporter` 类：生成报告和可视化
- 统计指标计算
- 图表生成（累计收益曲线、月度收益柱状图）

### run_backtest.py
主入口脚本，提供：
- 命令行接口（CLI）
- 参数解析
- 完整的回测流程控制

### test_backtest.py
快速测试脚本，用于：
- 验证基本功能
- 检查数据源连接
- 确认配置正确性

## 💡 使用提示

1. **首次使用**：先运行 `test_backtest.py` 验证环境
2. **小范围测试**：先用较短周期（如1个月）测试
3. **查看结果**：回测完成后在 `data/` 目录查看图表和CSV
4. **调整参数**：尝试不同的 `--volume-period` 和 `--hold-days`

## 📊 输出文件

回测完成后会在 `data/` 目录生成：
- `backtest_cumulative_returns_*.png` - 累计收益曲线
- `backtest_monthly_returns_*.png` - 月度收益柱状图
- `backtest_trades_*.csv` - 交易明细
- `backtest.log` - 运行日志

## ❓ 常见问题

**Q: 提示"白名单为空"或"未找到任何白名单文件"？**  
A: 先运行 `python local/manage_stock_list.py --update` 生成白名单

**Q: 如何指定特定日期的白名单？**  
A: 通常不需要指定，会自动使用最新文件。只有在需要特定日期时才使用：
```bash
python backtest/run_backtest.py --whitelist data/whitelist_20260424.txt
```

**Q: 回测速度太慢？**  
A: 缩短回测周期或减少白名单股票数量

**Q: 图表中文乱码？**  
A: 确保系统安装了中文字体（Windows自带SimHei）

更多问题请查看 [BACKTEST_README.md](BACKTEST_README.md)

---

**版本**: v1.0  
**创建时间**: 2026-04-25  
**维护者**: StockBot Team
