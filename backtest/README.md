# 📈 选股策略回测工具包

本目录包含完整的量化选股+评分+回测解决方案。

## 📁 目录结构

```
backtest/
├── generate_stockpool.py        # 股票池生成器（7大条件选股）
├── score_stockpool.py           # 评分筛选工具（100分制+优选分）
├── generate_breakout.py         # 横盘突破选股（独立策略）
├── diagnose_conditions.py       # 选股条件诊断工具
├── run_backtest.py              # 回测主入口
├── backtest_engine.py           # 回测引擎
├── backtest_reporter.py         # 报告生成器
├── calc_backtest_rate.py        # 收益率计算工具
├── update_hs300_data.py         # 沪深300数据更新
├── view_stockpool.py            # 查看原始股票池
├── view_scored_results.py       # 查看评分结果
├── analyze_stockpool.py         # 选股统计分析
├── NEWCHAT_START.md             # 新对话快速启动指南
├── BACKTEST_OPTIMIZATION_PLAN.md # 优化总结文档
└── README.md                    # 本文档
```

---

## 🚀 完整工作流程

```
                   选股条件诊断 ← → 选股参数调优
                         ↓
第1步：选股 → python generate_stockpool.py --date YYYY-MM-DD
                         ↓
第2步：评分 → python score_stockpool.py --date YYYY-MM-DD
                         ↓
第3步：回测 → python run_backtest.py --start-date ... --end-date ...
                         ↓
第4步：信号 → python trade_decision/market_signal.py --date YYYY-MM-DD
```

---

## 📋 三步核心流程

### 第1步：选股

```bash
python backtest/generate_stockpool.py --start-date 2026-01-01 --end-date 2026-06-01
```

**7大选股条件**：

| # | 条件 | 内容 |
|:-:|:----|:------|
| ① | 成交量放量 | 至少2天≥85%，全部≥65%，第3天不是最小 |
| ② | 价格稳步上涨 | 至少2天>基准日，回调≤5%，第3天不是最低，冲高回落<8% |
| ③ | 站上MA20 | 收盘 > 20日均线 |
| ④ | 涨幅区间 | 放量期涨幅 [0%, 20%] |
| ⑤ | 量比区间 | 放量期3天≥1.0x，基准日≥0.9x |
| ⑥ | 相对强度 | 跑赢沪深300≥-2% |
| ⑦ | 波动率过滤 | 日收益率标准差<6% |

### 第2步：评分

```bash
python backtest/score_stockpool.py --date 2026-04-13
python backtest/score_stockpool.py --start-date 2026-01-01 --end-date 2026-06-01
```

**评分系统**：

| 维度 | 权重 | 说明 |
|:----:|:----:|:------|
| 量能因子 | 20分 | 成交量递增、量比、换手率 |
| 趋势因子 | 35分 | 均线多头排列、均线斜率 |
| 动量因子 | 20分 | 5日/10日涨幅、相对强度 |
| 形态因子 | 15分 | MACD、布林带 |
| 风险因子 | 10分 | RSI、波动率 |

**优选分（0~10分）**：评分相同时，按量能和幅度二次排序

### 第3步：回测

```bash
# 持有2天（推荐）
python backtest/run_backtest.py --start-date 2026-01-06 --end-date 2026-06-03

# 开启DEBUG模式查看资金明细
python backtest/run_backtest.py --start-date 2026-01-06 --end-date 2026-06-03 --debug
```

---

## 📊 回测成绩（2026年1月~5月，持有2天）

| 指标 | 策略 | 沪深300 |
|:----|:----:|:-------:|
| 总收益率 | **+68.96%** | +4.32% |
| 年化收益率 | +278% | +11.33% |
| 胜率 | 52.1% | — |
| 盈亏比 | 1.5 : 1 | — |
| 夏普比率 | 2.95 | — |
| 最大回撤 | -8.1% | — |
| 交易笔数 | 447笔 | — |

---

## 🛠️ 辅助工具

### 横盘突破选股

```bash
python backtest/generate_breakout.py --date 2026-04-13
python backtest/generate_breakout.py --diagnose 301319 --date 2026-04-13
```

### 选股条件诊断

```bash
python backtest/diagnose_conditions.py --date 2026-04-13 --sample 500
python backtest/diagnose_conditions.py --date 2026-04-13 --show-detail
```

### 大盘环境信号

```bash
python trade_decision/market_signal.py
python trade_decision/market_signal.py --date 2026-04-13
```

### 查看选股结果

```bash
python backtest/view_stockpool.py --date 2026-04-13
python backtest/view_scored_results.py --date 2026-04-13 --top 10
```

### 沪深300数据更新

```bash
python backtest/update_hs300_data.py
```

---

## ⚙️ 关键配置参数（config.yaml）

```yaml
backtest:
  hold_days: 2                    # 持仓天数
  volume_period: 3                # 放量周期
  min_score: 65                   # 最低评分
  max_score: 75                   # 最高评分
  max_stocks_per_cycle: 10        # 每周期最多10只
  max_stocks_per_industry: 3      # 每行业最多3只
  min_volume_ratio: 1.0
  max_volume_ratio: 5.0
  max_volatility_pct: 6.0
  min_relative_strength: -2.0
  ...

trade_decision:
  ma_short: 20
  ma_long: 60
  min_market_volume: 25000

breakout:
  consolidation_days: 60
  consolidation_range: 15.0
  vol_ratio_threshold: 1.5
```

---

## 📝 文档导航

| 文档 | 内容 |
|:----|:------|
| [NEWCHAT_START.md](NEWCHAT_START.md) | 新对话快速启动指南 |
| [BACKTEST_OPTIMIZATION_PLAN.md](BACKTEST_OPTIMIZATION_PLAN.md) | 完整优化总结 |

---

## ❓ 快速问题

**Q: 先选股还是先评分？**  
A: 先选股（generate_stockpool.py），再评分（score_stockpool.py），最后回测（run_backtest.py）

**Q: 评分不通过怎么办？**  
A: 用 `diagnose_conditions.py` 排查具体哪个条件淘汰

**Q: 回测亏损怎么办？**  
A: 先检查 `trade_decision/market_signal.py` 大盘信号，再调整选股参数

**Q: 每天操作流程？**  
A: `update_hs300_data.py` → `market_signal.py` → 根据信号决定是否选股+评分

---

**版本**: v2.0  
**最后更新**: 2026-06-12
