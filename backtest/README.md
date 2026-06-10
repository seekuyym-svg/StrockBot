# 📈 选股策略回测工具包

本目录包含对 `select_daysvol.py` 持续放量选股策略的完整回测解决方案。

## 📁 目录结构

```
backtest/
├── __init__.py                      # Python包初始化文件
│
├── 🔧 核心代码
│   ├── generate_stockpool.py        # 🆕 股票池生成器（第1步）
│   ├── score_stockpool.py           # 🆕 股票池评分工具
│   ├── calc_backtest_rate.py        # 🆕 回测收益率计算工具
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

---

## 🆕 最新优化（2026-05-03）

### 1. **股票池评分系统**
**文件**: [`score_stockpool.py`](score_stockpool.py)

**功能**：为股票池中的每只股票计算综合评分

**使用方式**：
```bash
# 单日期评分（默认不生成备份）
python backtest/score_stockpool.py --date 2024-01-15

# 批量评分（指定日期范围）
python backtest/score_stockpool.py --start-date 2024-01-01 --end-date 2024-01-10

# 需要生成备份文件时
python backtest/score_stockpool.py --date 2024-01-15 --backup
```

**输出格式**：
```
股票代码,评分
603768,2.5
000858,-0.3
```

**关键特性**：
- ✅ 支持单日和批量评分
- ✅ 默认不生成备份文件，节省磁盘空间
- ✅ 通过 `--backup` 参数显式启用备份

---

### 2. **回测收益率计算工具**
**文件**: [`calc_backtest_rate.py`](calc_backtest_rate.py)

**功能**：基于评分过滤后的股票池，计算单日或区间收益率

**评分过滤机制**：
- ✅ 从 [config.yaml](../config.yaml) 读取 `backtest_minscore` 配置
- ✅ 自动过滤掉无评分数据的股票
- ✅ 自动过滤掉评分低于阈值的股票
- ✅ 输出详细的过滤统计信息

**使用方式**：
```bash
# 计算单日收益率
python backtest/calc_backtest_rate.py --date 2026-04-20 --pooldate 20260420

# 计算区间收益率
python backtest/calc_backtest_rate.py --start 2026-04-20 --end 2026-04-22 --pooldate 20260420

# 同时计算单日和区间收益
python backtest/calc_backtest_rate.py --date 2026-04-20 --start 2026-04-20 --end 2026-04-22 --pooldate 20260420

# 自定义初始资金
python backtest/calc_backtest_rate.py --date 2026-04-20 --pooldate 20260420 --capital 200000
```

**输出报告**：
- 📊 个股详情（开盘价、收盘价、买入股数、收益率、盈亏）
- 💰 汇总报告（总投入、总市值、综合收益率、总盈亏）
- 💹 资金使用率诊断（闲置资金分析、优化建议）
- 📋 详细数据表（按收益率排序）

**关键特性**：
- ✅ 严格遵守A股100股整数倍限制
- ✅ 智能资金使用率分析（<80%警告、80-95%提示、>95%良好）
- ✅ 自动保存报告到 `data/report_*.txt`

---

### 3. **指数数据增量更新（通用）**
**文件**: [`update_index_data.py`](update_index_data.py) / [`update_indices.py`](update_indices.py)

**优化内容**：支持任意东方财富指数增量更新，可批量一键更新所有参考指数

**使用方式**：
```bash
# 一键更新所有参考指数（推荐，从config.yaml自动读取指数列表）
python backtest/update_indices.py

# 更新指定指数
python backtest/update_index_data.py --name kc_index --secid 1.000680
python backtest/update_index_data.py --name hs300_eastmoney --secid 1.000300

# 全量重新获取
python backtest/update_index_data.py --name kc_index --secid 1.000680 --start 2020-01-01
```

**关键特性**：
- ✅ 增量更新：自动检测本地最新日期，只下载缺失数据
- ✅ 批量更新：一条命令更新所有配置的指数
- ✅ 通用设计：支持任意东方财富指数（通过 --secid 指定）
- ✅ 数据格式统一：所有指数CSV格式一致（date,open,close,high,low,volume）

---

### 4. **白名单智能加载**
**文件**: [`local/utils.py`](../local/utils.py) - `load_whitelist()`

**优化内容**：支持自动回退到最近的白名单文件

**加载策略**：
1. ✅ 优先使用 `data/whitelist_当天日期.txt`
2. ✅ 如果不存在，自动查找并使用最新的白名单文件
3. ✅ 完全没有则返回空集合并提示用户生成

**适用场景**：
- 📅 周末/节假日运行：自动使用最近交易日的白名单
- 🔄 跨天运行：凌晨运行时自动使用前一天的白名单
- ⚠️ 数据缺失：某天忘记生成白名单，自动回退到最近可用数据

**输出示例**：
```
[WARNING] 指定日期白名单不存在: whitelist_20260503.txt
[INFO] 正在查找最近的白名单文件...
[OK] 使用最近白名单: 20260430
[LOAD] 加载白名单 (20260430): 4500 只股票
[PATH] 文件路径: E:\LearnPY\Projects\StockBot\data\whitelist_20260430.txt
```

---

### 5. **修复沪深300数据路径问题**
**文件**: 
- [`backtest_engine.py`](backtest_engine.py)
- [`update_hs300_data.py`](update_hs300_data.py)

**问题**：原代码使用相对路径 `Path("data/hs300_eastmoney.csv")`，导致从当前工作目录查找文件

**修复**：改为使用项目根目录的绝对路径
```python
project_root = Path(__file__).parent.parent
csv_file = project_root / "data" / "hs300_eastmoney.csv"
```

**优势**：无论从哪个目录运行脚本，都能正确定位到数据文件

---

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
