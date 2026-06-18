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

**命令行参数**：

```bash
# 批量评分
python backtest/score_stockpool.py --start-date 2026-01-01 --end-date 2026-06-01

# 自定义评分区间
python backtest/score_stockpool.py --date 2026-06-10 --min-score 65 --max-score 70 --max-stocks 10

# 全量评分（不过滤区间）
python backtest/score_stockpool.py --date 2026-06-10 --min-score 0 --max-score 100 --max-stocks 500
```

**评分系统**：

**综合评分（100分制）**：

| 维度 | 权重 | 子项 | 说明 |
|:----:|:----:|:-----|:------|
| 量能因子 | 25分 | 成交量递增10+量比10+换手率5 | 温和放量(1~2倍)最优 |
| 趋势因子 | 25分 | 均线排列15+均线斜率10 | 短期多头，斜率0.5~2%最优 |
| 动量因子 | 20分 | 3日涨幅8+相对强度7+偏离5日线5 | 2~5%涨幅最优 |
| 形态因子 | 20分 | MACD柱体10+布林带5+K线形态5 | 柱体放大+收窄蓄力+小阳线最优 |
| 风险因子 | 10分 | RSI 5+波动率5 | 波动率2~8%最优 |

**优选分（0~25分）**：综合同分时的第二排序，评估强势延续性

| 子项 | 分值 | 说明 |
|:----:|:----:|:------|
| 趋势疲劳度 | 6分 | 阳线连涨天数，≤3天满分，>7天0分 |
| 前高压力 | 6分 | 距60日高距离，>10%满分，贴前高0分 |
| 当日强度 | 4分 | 涨1~3%+量比适中满分，大涨过热扣分 |
| 乖离率 | 4分 | 偏离20日线2~4%满分，>6%或<0%扣分 |
| 评分趋势 | 5分 | 历史综合评分逐日升高满分 |

### 第3步：收益率计算

```bash
# 计算区间收益率（回测）
python backtest/calc_backtest_rate.py --start 2026-06-08 --end 2026-06-09 --pooldate 20260605 --capital 1000000

# 收益率会自动写回股票池文件中（第4列为回测收益率%）
```

### 第4步：回测（完整流程）

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
  min_score: 65                   # 综合评分下限
  max_score: 70                   # 综合评分上限
  min_pref_score: 0               # 优选分下限（0=不淘汰）
  max_pref_score: 16              # 优选分上限（排除过热股）
  max_stocks_per_cycle: 10        # 每周期最多选股数
  max_stocks_per_industry: 4      # 每行业最多选几只
  dynamic_select_ratio: 0.4       # 动态选股比例（候选少时自动减少选股）
  max_per_score: 3                # 同分值最多保留几只
  pref_vol_ratio_threshold: 2.8   # 量比上限
  pref_vol_ratio_min: 1.2         # 量比下限
  pref_upper_shadow_threshold: 2.5  # 上影线出货信号阈值
  ...
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

**版本**: v2.1  
**最后更新**: 2026-06-14
