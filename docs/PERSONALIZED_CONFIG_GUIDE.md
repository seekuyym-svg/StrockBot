# 个性化策略参数配置指南

## 📋 功能概述

从 v2.1.0 版本开始，StockBot 支持为不同的 ETF 分别配置个性化的马丁格尔策略参数。这意味着你可以根据每个 ETF 的波动特性、风险偏好等因素，设置不同的加仓跌幅阈值和止盈涨幅。

## 🎯 使用场景

### 场景 1：不同波动性的 ETF
- **高波动 ETF**（如创新药）：设置较小的加仓跌幅阈值（如 3%），更频繁地捕捉波动机会
- **低波动 ETF**（如银行ETF）：设置较大的加仓跌幅阈值（如 5%），避免过于频繁的加仓

### 场景 2：不同风险偏好的 ETF
- **高风险 ETF**：设置较高的止盈涨幅（如 3%），追求更高收益
- **低风险 ETF**：设置较低的止盈涨幅（如 1.5%），快速锁定利润

### 场景 3：不同资金分配策略
- **核心持仓**：设置较高的初始建仓比例（如 8%）
- **卫星持仓**：设置较低的初始建仓比例（如 4%）

## ⚙️ 配置方法

### 1. 基本配置结构

在 `config.yaml` 文件中，每个 symbol 可以配置以下个性化参数：

```yaml
symbols:
  - code: "sh.513120"  # 港股创新药ETF
    name: "港股创新药ETF"
    enabled: true
    # 个性化策略参数（可选）
    add_drop_threshold: 3.0      # 加仓跌幅阈值：下跌3%加仓
    take_profit_threshold: 2.0   # 止盈涨幅：盈利2%止盈
    max_add_positions: 4         # 最大加仓次数
    initial_position_pct: 6      # 初始建仓比例（占总资金百分比）
    
  - code: "sh.513050"  # 中概互联网ETF
    name: "中概互联网ETF"
    enabled: true
    # 个性化策略参数（可选）
    add_drop_threshold: 3.5      # 加仓跌幅阈值：下跌3.5%加仓
    take_profit_threshold: 2.5   # 止盈涨幅：盈利2.5%止盈
    max_add_positions: 4         # 最大加仓次数
    initial_position_pct: 6      # 初始建仓比例（占总资金百分比）
```

### 2. 可配置的个性化参数

| 参数名 | 类型 | 说明 | 示例值 |
|--------|------|------|--------|
| `add_drop_threshold` | float | 加仓跌幅阈值（%）。每次加仓需要的累计跌幅 = 该值 × (加仓次数+1) | 3.0, 3.5, 4.0 |
| `take_profit_threshold` | float | 止盈涨幅阈值（%）。基于加权平均成本的盈利比例 | 2.0, 2.5, 3.0 |
| `max_add_positions` | int | 最大加仓次数（不含初始建仓） | 3, 4, 5 |
| `initial_position_pct` | float | 初始建仓比例（%）。占初始资金的百分比 | 5, 6, 8 |

### 3. 保持全局统一的参数

以下参数在所有 ETF 间保持一致，**不支持**个性化配置：

| 参数名 | 说明 | 配置位置 |
|--------|------|----------|
| `add_position_multiplier` | 加仓倍数。每次加仓金额是上一次的倍数 | `strategy.add_position_multiplier` |
| `max_position_pct` | 单只股票最大持仓比例（%） | `strategy.max_position_pct` |

## 🔄 配置优先级规则

系统按照以下优先级确定策略参数：

1. **个性化配置优先**：如果 symbol 配置了某个参数，使用该值
2. **全局配置兜底**：如果 symbol 未配置某参数，使用 `strategy` 节点的全局默认值
3. **向后兼容**：不配置个性化参数时，系统行为与之前完全一致

### 示例 1：完全个性化配置

```yaml
symbols:
  - code: "sh.513120"
    name: "港股创新药ETF"
    enabled: true
    add_drop_threshold: 3.0
    take_profit_threshold: 2.0
    
  - code: "sh.513050"
    name: "中概互联网ETF"
    enabled: true
    add_drop_threshold: 4.0
    take_profit_threshold: 3.0

strategy:
  add_drop_threshold: 3.5  # 全局默认值（仅作为兜底）
  take_profit_threshold: 2.5
```

**结果**：
- sh.513120 使用：add_drop_threshold=3.0, take_profit_threshold=2.0
- sh.513050 使用：add_drop_threshold=4.0, take_profit_threshold=3.0

### 示例 2：部分个性化配置

```yaml
symbols:
  - code: "sh.513120"
    name: "港股创新药ETF"
    enabled: true
    add_drop_threshold: 3.0  # 只配置这一个参数
    # take_profit_threshold 未配置，将使用全局默认值
    
  - code: "sh.513050"
    name: "中概互联网ETF"
    enabled: true
    # 完全不配置个性化参数，全部使用全局默认值

strategy:
  add_drop_threshold: 3.5  # 全局默认值
  take_profit_threshold: 2.5
```

**结果**：
- sh.513120 使用：add_drop_threshold=3.0（个性化）, take_profit_threshold=2.5（全局）
- sh.513050 使用：add_drop_threshold=3.5（全局）, take_profit_threshold=2.5（全局）

### 示例 3：完全不配置个性化参数（向后兼容）

```yaml
symbols:
  - code: "sh.513120"
    name: "港股创新药ETF"
    enabled: true
    
  - code: "sh.513050"
    name: "中概互联网ETF"
    enabled: true

strategy:
  add_drop_threshold: 3.5
  take_profit_threshold: 2.5
```

**结果**：两个 ETF 都使用全局默认值，系统行为与 v2.0.0 完全一致。

## 💡 最佳实践建议

### 1. 根据波动性配置

```yaml
# 高波动 ETF：小步快跑
- code: "sh.513120"  # 创新药ETF，波动较大
  add_drop_threshold: 2.5  # 较小的加仓间隔
  take_profit_threshold: 1.5  # 快速止盈
  
# 低波动 ETF：稳健操作
- code: "sh.513xxx"  # 银行ETF，波动较小
  add_drop_threshold: 4.0  # 较大的加仓间隔
  take_profit_threshold: 3.0  # 追求更高收益
```

### 2. 根据风险偏好配置

```yaml
# 激进型：高频交易
- code: "sh.513120"
  add_drop_threshold: 2.0
  take_profit_threshold: 1.0
  max_add_positions: 5  # 更多加仓次数
  
# 保守型：低频交易
- code: "sh.513050"
  add_drop_threshold: 4.0
  take_profit_threshold: 3.0
  max_add_positions: 3  # 较少加仓次数
```

### 3. 根据资金规模配置

```yaml
# 大资金 ETF：重仓操作
- code: "sh.513120"
  initial_position_pct: 8  # 初始建仓 8%
  
# 小资金 ETF：轻仓试探
- code: "sh.513050"
  initial_position_pct: 4  # 初始建仓 4%
```

## 🔍 验证配置

运行测试脚本验证配置是否正确：

```bash
python test_personalized_config.py
```

输出示例：

```
============================================================
测试个性化策略参数配置
============================================================

1. 检查配置文件中的symbol配置:

   sh.513120 - 港股创新药ETF
      enabled: True
      add_drop_threshold: 3.0
      take_profit_threshold: 2.0
      max_add_positions: 4
      initial_position_pct: 6.0

   sh.513050 - 中概互联网ETF
      enabled: True
      add_drop_threshold: 3.5
      take_profit_threshold: 2.5
      max_add_positions: 4
      initial_position_pct: 6.0

2. 全局默认策略配置:
   add_drop_threshold: 3.0
   take_profit_threshold: 2.0
   max_add_positions: 4
   initial_position_pct: 6.0

3. 测试策略引擎获取个性化配置:

   sh.513120 - 港股创新药ETF:
      add_drop_threshold: 3.0
      take_profit_threshold: 2.0
      max_add_positions: 4
      initial_position_pct: 6.0
      ✓ 使用个性化配置

   sh.513050 - 中概互联网ETF:
      add_drop_threshold: 3.5
      take_profit_threshold: 2.5
      max_add_positions: 4
      initial_position_pct: 6.0
      ✓ 使用个性化配置

============================================================
✓ 所有测试通过！个性化配置功能正常工作。
============================================================
```

## ⚠️ 注意事项

1. **参数合理性**：确保个性化参数在合理范围内，避免设置过小的加仓间隔导致频繁交易
2. **资金管理**：个性化配置会影响资金分配，请确保总资金使用不超过可用资金
3. **回测验证**：建议在实盘前使用历史数据回测不同参数组合的效果
4. **逐步调整**：初次使用时建议从小幅调整开始，观察效果后再进一步优化

## 📊 配置示例参考

### 示例 1：平衡型配置

```yaml
symbols:
  - code: "sh.513120"  # 创新药ETF
    name: "港股创新药ETF"
    enabled: true
    add_drop_threshold: 3.0
    take_profit_threshold: 2.0
    max_add_positions: 4
    initial_position_pct: 6
    
  - code: "sh.513050"  # 中概互联ETF
    name: "中概互联网ETF"
    enabled: true
    add_drop_threshold: 3.5
    take_profit_threshold: 2.5
    max_add_positions: 4
    initial_position_pct: 6
```

### 示例 2：激进型配置

```yaml
symbols:
  - code: "sh.513120"
    name: "港股创新药ETF"
    enabled: true
    add_drop_threshold: 2.0  # 更频繁的加仓
    take_profit_threshold: 1.5  # 快速止盈
    max_add_positions: 5  # 更多加仓次数
    initial_position_pct: 8  # 更高的初始仓位
    
  - code: "sh.513050"
    name: "中概互联网ETF"
    enabled: true
    add_drop_threshold: 2.5
    take_profit_threshold: 2.0
    max_add_positions: 5
    initial_position_pct: 7
```

### 示例 3：保守型配置

```yaml
symbols:
  - code: "sh.513120"
    name: "港股创新药ETF"
    enabled: true
    add_drop_threshold: 4.0  # 更大的加仓间隔
    take_profit_threshold: 3.0  # 追求更高收益
    max_add_positions: 3  # 更少的加仓次数
    initial_position_pct: 5  # 更低的初始仓位
    
  - code: "sh.513050"
    name: "中概互联网ETF"
    enabled: true
    add_drop_threshold: 4.5
    take_profit_threshold: 3.5
    max_add_positions: 3
    initial_position_pct: 4
```

## 🚀 下一步

- 运行 `python main.py` 启动系统，观察不同 ETF 的信号生成情况
- 查看日志输出，确认每个 ETF 使用了正确的策略参数
- 根据实际运行情况调整参数，找到最适合你的配置组合

---

**版本信息**：v2.1.0  
**更新日期**：2026-04-15  
**作者**：StockBot Team
