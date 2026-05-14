# 🚀 新对话快速启动指南

**适用场景**：开启新对话后，快速继续回测策略优化工作

**最后更新**：2026-05-04 00:05

---

## 📋 当前状态（2026-05-04最新修复）

### ✅ **已完成的工作**

#### 1. 回测引擎非交易日过滤修复 ⭐⭐⭐⭐⭐ 【NEW】
- **文件**：[backtest_engine.py](file://e:\LearnPY\Projects\StockBot\backtest\backtest_engine.py)
- **问题**：回测引擎的 `get_trading_days()` 方法仅过滤周末，未处理法定节假日，导致回测时出现日期跳跃
- **解决方案**：复用 [generate_stockpool.py](file://e:\LearnPY\Projects\StockBot\backtest\generate_stockpool.py) 中的 akshare 交易日历获取逻辑
- **效果**：回测时自动识别并过滤所有非交易日（周末+节假日），确保交易周期计算准确
- **降级机制**：API失败时自动降级为仅过滤周末
- **测试验证**：2026年4月正确识别21个交易日（跳过清明假期4月4-6日）

#### 2. 股票池生成器非交易日过滤 ⭐⭐⭐⭐⭐
- **文件**：[generate_stockpool.py](file://e:\LearnPY\Projects\StockBot\backtest\generate_stockpool.py)
- **问题**：原逻辑仅过滤周末，未处理法定节假日
- **解决方案**：使用 akshare 获取准确的A股交易日历
- **效果**：自动识别并过滤所有非交易日（周末+节假日）
- **降级机制**：API失败时自动降级为仅过滤周末

#### 3. 粗筛参数配置化与优化 ⭐⭐⭐⭐⭐
- **文件**：[config.yaml](file://e:\LearnPY\Projects\StockBot\config.yaml)、[generate_stockpool.py](file://e:\LearnPY\Projects\StockBot\backtest\generate_stockpool.py)
- **新增配置项**：
  ```yaml
  backtest:
    # 涨跌幅过滤区间（%）
    min_price_change_pct: -5.0    # 收紧：从-10%改为-5%
    max_price_change_pct: 25.0    # 收紧：从+30%改为+25%
    
    # 成交量放大倍数范围
    min_volume_ratio: 1.3         # 提高：从1.1x改为1.3x
    max_volume_ratio: 8.0         # 保持不变
  ```
- **代码改进**：从配置文件读取参数，替代硬编码
- **实测效果**：选股数量从平均119只减少到91只（**-23%**）

#### 4. 新版100分评分系统 ⭐⭐⭐⭐⭐
- **文件**：[local/utils.py](file://e:\LearnPY\Projects\StockBot\local\utils.py)
- **新增函数**：[calculate_trend_score_v2()](file://e:\LearnPY\Projects\StockBot\local\utils.py#L729-L928) - 满分100分的综合评分系统
- **评分维度**：
  | 维度 | 权重 | 说明 |
  |------|------|------|
  | **量能因子** | 30分 | 成交量递增、量比、换手率 |
  | **趋势因子** | 25分 | 均线排列、均线斜率 |
  | **动量因子** | 20分 | 5日/10日涨幅、相对强度 |
  | **形态因子** | 15分 | MACD、布林带位置 |
  | **风险因子** | 10分 | RSI、波动率控制 |
- **评级标准**：
  - 80-100分：⭐⭐⭐⭐⭐ 优秀
  - 60-79分：⭐⭐⭐⭐ 良好
  - 40-59分：⭐⭐⭐ 中等
  - 20-39分：⭐⭐ 较差
  - 0-19分：⭐ 很差

#### 5. 回测引擎集成新评分系统 ⭐⭐⭐⭐⭐
- **文件**：[score_stockpool.py](file://e:\LearnPY\Projects\StockBot\backtest\score_stockpool.py)
- **关键修改**：第208行已调用新版评分系统
  ```python
  from local.utils import calculate_trend_score_v2
  score = calculate_trend_score_v2(market, code, days=300)
  ```
- **配置读取**：从 [config.yaml](file://e:\LearnPY\Projects\StockBot\config.yaml) 读取 `min_score: 60`

#### 6. 实测验证（2026-04-13）⭐⭐⭐⭐⭐
- **筛选流程**：
  ```
  白名单 (5014只) 
      ↓ 粗筛（放量+趋势+涨幅+量比）
  候选池 (46只)
      ↓ 精筛（100分评分系统）
  评分>=60 (18只)
      ↓ Top N排序
  最终选股 (10只)
  ```
- **Top 10股票详情**：
  | 排名 | 代码 | 名称 | 行业 | 评分 | 评级 |
  |------|------|------|------|------|------|
  | 1 | 600379 | 宝光股份 | 电网设备 | 78.0 | ⭐⭐⭐⭐ 良好 |
  | 2 | 000036 | 华联控股 | 房地产开发 | 77.0 | ⭐⭐⭐⭐ 良好 |
  | 3 | 688155 | 先惠技术 | 电池 | 74.0 | ⭐⭐⭐⭐ 良好 |
  | 4 | 603773 | 沃格光电 | 光学光电子 | 72.0 | ⭐⭐⭐⭐ 良好 |
  | 5 | 603800 | 洪田股份 | 专用设备 | 72.0 | ⭐⭐⭐⭐ 良好 |
  | 6 | 002497 | 雅化集团 | 化学制品 | 71.0 | ⭐⭐⭐⭐ 良好 |
  | 7 | 002192 | 融捷股份 | 能源金属 | 70.0 | ⭐⭐⭐⭐ 良好 |
  | 8 | 301526 | 国际复材 | 玻璃玻纤 | 70.0 | ⭐⭐⭐⭐ 良好 |
  | 9 | 603045 | 福达合金 | 金属新材料 | 70.0 | ⭐⭐⭐⭐ 良好 |
  | 10 | 688719 | 爱科赛博 | 其他电源设备Ⅱ | 69.0 | ⭐⭐⭐⭐ 良好 |
- **统计摘要**：
  - 最高评分：**78.0分**（宝光股份）
  - 最低评分：**69.0分**（爱科赛博）
  - 平均评分：**72.3分**
  - 评级分布：**全部为"⭐⭐⭐⭐ 良好"**

---

## 🎯 **核心设计原则**

### "宽粗筛，严评分"策略
- **第一阶段（粗筛）**：放宽条件，选出100-200只候选股票
  - 放量天数：3天（从5天降低，提升灵敏度）
  - 涨跌幅区间：[-5%, +25%]（收紧，过滤极端值）
  - 量比范围：[1.3x, 8.0x]（提高下限，过滤温和放量）
- **第二阶段（精筛）**：严格评分，筛选出Top 10高分股票
  - 评分阈值：60分（满分100分）
  - 选股数量：最多10只，最少3只
  - 按评分降序排序

---

## 🛠️ **实用工具清单**

### 1. 查看原始股票池（粗筛结果）
```bash
python backtest/view_stockpool.py --date 2026-04-13 --top 20
```
**功能**：显示未经评分的候选股票列表

### 2. 查看评分后的股票池（精筛结果）⭐推荐
```bash
python backtest/view_scored_results.py --date 2026-04-13
python backtest/view_scored_results.py --date 2026-04-13 --top 5
```
**功能**：显示评分后的Top N股票，包含代码、名称、行业、评分、评级

### 3. 统计分析选股数量
```bash
python backtest/analyze_stockpool.py --start-date 2026-04-13 --end-date 2026-04-24
```
**功能**：统计指定日期范围内的选股数量、平均值、最大最小值

### 4. 测试单只股票的评分
```bash
python backtest/test_new_score.py --code 000036
python backtest/test_new_score.py --code 600707 --market sh
```
**功能**：对比新旧评分系统，显示详细评分结果

---

## 📂 **重要文件清单**

### 核心代码文件
- `backtest/generate_stockpool.py` - 股票池生成（✅ 已优化：缓存+配置化+非交易日过滤）
- `backtest/score_stockpool.py` - 评分筛选（✅ 已集成100分评分系统）
- `local/utils.py` - 技术指标计算（✅ 新增 calculate_trend_score_v2）
- `backtest/backtest_engine.py` - 回测引擎
- `backtest/run_backtest.py` - 回测入口

### 配置文件
- `config.yaml` - 全局配置（✅ 已更新粗筛参数和评分阈值）

### 数据文件
- `data/stockpool_*.txt` - 每日股票池（含评分数据）
- `data/backtest_trades_*.csv` - 交易明细
- `data/backtest_cumulative_returns_*.png` - 收益曲线图
- `data/backtest_monthly_returns_*.png` - 月度收益图

### 工具文件
- `backtest/view_stockpool.py` - 查看原始股票池
- `backtest/view_scored_results.py` - 查看评分结果 ⭐新增
- `backtest/analyze_stockpool.py` - 统计分析 ⭐新增
- `backtest/test_new_score.py` - 测试评分系统 ⭐新增

### 文档文件
- `backtest/NEW_CHAT_QUICKSTART.md` - 本文档
- `backtest/PHASE1_IMPLEMENTATION_STATUS.md` - 第一阶段实施状态
- `backtest/PHASE1_OPTIMIZATION_SUMMARY.md` - 详细总结

---

## 🧪 **快速验证命令**

### 场景1：生成新的股票池
```bash
# 单日测试
python backtest/generate_stockpool.py --date 2026-04-13

# 多日测试（10个交易日）
python backtest/generate_stockpool.py --start-date 2026-04-13 --end-date 2026-04-24
```

### 场景2：对股票池进行评分
```bash
# 单日评分
python backtest/score_stockpool.py --date 2026-04-13

# 批量评分
python backtest/score_stockpool.py --start-date 2026-04-13 --end-date 2026-04-24
```

### 场景3：查看评分结果
```bash
# 查看全部
python backtest/view_scored_results.py --date 2026-04-13

# 查看前N只
python backtest/view_scored_results.py --date 2026-04-13 --top 5
```

### 场景4：运行完整回测
```bash
# 生成股票池
python backtest/generate_stockpool.py --start-date 2026-04-01 --end-date 2026-04-30

# 评分筛选
python backtest/score_stockpool.py --start-date 2026-04-01 --end-date 2026-04-30

# 执行回测
python backtest/run_backtest.py --start-date 2026-04-01 --end-date 2026-04-30
```

---

## 📊 **配置参数说明**

### config.yaml - backtest 节点

```yaml
backtest:
  # === 基础配置 ===
  hold_days: 3                    # 持仓天数（交易日）
  volume_period: 3                # 连续放量天数
  initial_capital: 1000000        # 初始资金（元）
  
  # === 第一阶段粗筛参数 ===
  min_price_change_pct: -5.0      # 最小允许涨跌幅（%）
  max_price_change_pct: 25.0      # 最大允许涨跌幅（%）
  min_volume_ratio: 1.3           # 最小量比（倍数）
  max_volume_ratio: 8.0           # 最大量比（倍数）
  
  # === 第二阶段评分参数 ===
  min_score: 60                   # 最低评分阈值（满分100分）
  max_stocks_per_cycle: 10        # 每个周期最多选10只股票
  min_stocks_per_cycle: 3         # 最少选3只（保证分散）
```

### 参数调优建议

#### 如果选股数量太多（>150只/天）
- 提高 `min_volume_ratio`：1.3 → 1.5
- 收紧涨跌幅区间：[-5%, +25%] → [-3%, +20%]
- 提高评分阈值：60 → 65

#### 如果选股数量太少（<50只/天）
- 降低 `min_volume_ratio`：1.3 → 1.2
- 放宽涨跌幅区间：[-5%, +25%] → [-8%, +30%]
- 降低评分阈值：60 → 55

#### 如果回测收益率不佳
- 增加持仓天数：3 → 5-7
- 提高评分阈值：60 → 70（只选优质股票）
- 考虑增加止损机制

---

## ❓ **常见问题**

### Q1: 新版评分系统和旧版有什么区别？
**答**：
- **旧版**：满分约6.5分，维度简单（均线3+MACD 1+RSI 1+布林带1+成交量0.5）
- **新版**：满分100分，5大维度15个子项，更科学全面
- **优势**：更直观、更易理解、更容易调整权重

### Q2: 为什么评分阈值设置为60分？
**答**：根据实测结果，60分对应"⭐⭐⭐⭐ 良好"级别，能够在选股质量和数量之间取得平衡。可以根据策略偏好调整：
- 保守策略：70分（只选优秀股票）
- 平衡策略：60分（默认，选良好及以上）
- 激进策略：40-50分（选中等的也可考虑）

### Q3: 粗筛参数如何影响选股数量？
**答**：
- **放量天数**：5天→3天，选股数量增加约30-50%
- **涨跌幅区间**：越宽松，选股越多
- **量比范围**：下限越高，选股越少（过滤温和放量）

### Q4: 内存缓存如何工作？
**答**：首次访问某只股票时从磁盘读取并缓存到 `self.data_cache`，后续同一股票的多次访问直接从内存获取，避免重复IO操作。性能提升约20-30倍，5000只股票约占用72MB内存。

### Q5: 非交易日过滤是如何实现的？
**答**：使用 akshare 库获取中国A股官方交易日历，准确识别所有非交易日（包括周末和法定节假日）。如果API失败，会自动降级为仅过滤周末的简化方案。

### Q6: 下一步应该做什么？
**答**：建议按以下顺序进行：
1. **短期验证**：运行1个月回测（2026-04-01至2026-04-30），验证新评分系统效果
2. **参数调优**：根据回测结果调整评分阈值、持仓天数等参数
3. **长期测试**：运行3-6个月回测，验证策略稳定性
4. **进一步优化**：考虑增加板块热度评分、资金流向因子等

---

## 🚀 **立即行动建议**

### 选项A：快速验证新评分系统（推荐）⭐
```bash
# 1. 生成1个月的股票池
python backtest/generate_stockpool.py --start-date 2026-04-01 --end-date 2026-04-30

# 2. 对所有股票池进行评分
python backtest/score_stockpool.py --start-date 2026-04-01 --end-date 2026-04-30

# 3. 运行回测
python backtest/run_backtest.py --start-date 2026-04-01 --end-date 2026-04-30

# 4. 查看结果
# 回测报告会保存在 data/ 目录下
```

### 选项B：先手动审查选股质量
```bash
# 查看几个典型日期的选股结果
python backtest/view_scored_results.py --date 2026-04-13
python backtest/view_scored_results.py --date 2026-04-16
python backtest/view_scored_results.py --date 2026-04-24
```

### 选项C：调整参数后再测试
```bash
# 1. 修改 config.yaml 中的参数
# 2. 重新生成股票池
python backtest/generate_stockpool.py --start-date 2026-04-01 --end-date 2026-04-30
# 3. 评分和回测...
```

---

## 📝 **待办事项清单**

### 高优先级（建议立即执行）
- [ ] 运行1个月回测，验证新评分系统效果
- [ ] 分析回测结果，评估胜率、收益率、最大回撤
- [ ] 根据结果调整评分阈值和持仓天数

### 中优先级（1-2周内）
- [ ] 增加板块热度评分
- [ ] 优化相对强度计算（对比沪深300）
- [ ] 引入OBV能量潮指标

### 低优先级（1-2月内）
- [ ] 接入财务数据（PE、PB、ROE等）
- [ ] 增加资金流向因子
- [ ] 实现动态权重调整

---

## 💡 **关键经验总结**

### 成功经验
1. **"宽粗筛，严评分"是正确的设计思路**：粗筛阶段放宽条件，精筛阶段严格评分
2. **配置化管理优于硬编码**：便于快速调优和A/B测试
3. **内存缓存显著提升性能**：从4小时降至10分钟
4. **100分评分系统更直观**：便于理解和调整

### 需要避免的陷阱
1. **评分阈值要与评分系统匹配**：旧版6.5分制不能用60分阈值
2. **粗筛参数要平衡灵敏度和准确性**：过于宽松会增加噪音，过于严格会错过机会
3. **回测周期要足够长**：至少3-6个月才能验证策略稳定性
4. **要考虑市场环境变化**：牛市、熊市、震荡市需要不同的参数

---

**准备好开始了吗？** 请告诉我你想执行哪个选项，或者有其他问题需要解答！🎯