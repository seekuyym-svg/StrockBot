# 止盈止损收益计算错误修复

## ❌ 问题描述

**用户反馈：**
> "触发止盈之后，为什么总收益计算出来是0元或者负数，这明显不对"

**现象：**
- 明明价格已经上涨，触发了止盈
- 但显示的"总收益"却是0元或负数
- 与实际盈利情况不符

## 🔍 问题分析

### 根本原因：使用了错误的成本基准

在 [MartingaleEngine](file://e:\LearnPY\Projects\StockBot\src\strategy\engine.py) 的收益计算中，错误地使用了 `init_price`（初始建仓价格）而非 `avg_cost`（平均成本）。

### 错误代码位置

#### 1. 止盈信号（_create_sell_signal）

**文件**: [src/strategy/engine.py](file://e:\LearnPY\Projects\StockBot\src\strategy\engine.py#L466-L516)

**错误代码（修复前）：**
```python
def _create_sell_signal(self, position: Position, market_data: MarketData, reason: str) -> Signal:
    """创建卖出信号"""
    price = market_data.current_price
    
    # ❌ 错误：使用 init_price 计算收益
    profit = position.position_value - (position.total_shares * position.init_price)
    profit_pct = (profit / (position.total_shares * position.init_price)) * 100
```

#### 2. 止损信号（_create_stop_signal）

**文件**: [src/strategy/engine.py](file://e:\LearnPY\Projects\StockBot\src\strategy\engine.py#L518-L568)

**错误代码（修复前）：**
```python
def _create_stop_signal(self, position: Position, market_data: MarketData, reason: str) -> Signal:
    """创建止损信号"""
    price = market_data.current_price
    
    # ❌ 错误：使用 init_price 计算损失
    loss = (position.total_shares * position.init_price) - position.position_value
    loss_pct = (loss / (position.total_shares * position.init_price)) * 100
```

### 为什么会出错？

**马丁格尔策略的特点：**
1. **初始建仓**: 以价格 P₀ 买入 S₀ 份
2. **多次加仓**: 在更低的价格 P₁, P₂, P₃... 继续买入
3. **平均成本降低**: 经过加仓后，`avg_cost < init_price`

**示例场景：**

假设某ETF交易过程：

| 操作 | 价格 | 份额 | 金额 | 累计份额 | 平均成本 |
|------|------|------|------|---------|---------|
| 初始建仓 | ¥1.300 | 10,000 | ¥13,000 | 10,000 | ¥1.300 |
| 第1次加仓 | ¥1.250 | 20,000 | ¥25,000 | 30,000 | ¥1.267 |
| 第2次加仓 | ¥1.200 | 40,000 | ¥48,000 | 70,000 | ¥1.229 |
| **止盈卖出** | **¥1.250** | **70,000** | **¥87,500** | - | - |

**正确的收益计算：**
```
总成本 = 70,000 × ¥1.229 = ¥86,030
市值 = 70,000 × ¥1.250 = ¥87,500
收益 = ¥87,500 - ¥86,030 = +¥1,470 ✅ 盈利
收益率 = 1,470 / 86,030 = +1.71%
```

**错误的收益计算（使用init_price）：**
```
总成本 = 70,000 × ¥1.300 = ¥91,000  ❌ 错误！
市值 = 70,000 × ¥1.250 = ¥87,500
收益 = ¥87,500 - ¥91,000 = -¥3,500 ❌ 显示亏损！
收益率 = -3,500 / 91,000 = -3.85% ❌ 完全错误！
```

**结果：**
- 实际盈利 ¥1,470
- 系统显示亏损 ¥3,500
- **差异高达 ¥4,970！**

### Position 模型字段说明

根据 [Position](file://e:\LearnPY\Projects\StockBot\src\models\models.py#L56-L67) 模型定义：

```python
class Position(BaseModel):
    """持仓信息"""
    symbol: str
    name: str
    status: PositionStatus
    init_price: float           # 初始建仓价格（第一次买入的价格）
    avg_cost: float             # 平均成本（加权平均后的成本）✅ 应该用这个
    total_shares: int           # 总股数
    position_value: float       # 持仓市值
    add_count: int              # 加仓次数
    open_date: datetime         # 建仓日期
    last_update: datetime       # 最后更新
```

**关键字段区别：**
- `init_price`: 只在初始建仓时设置，之后不再改变
- `avg_cost`: 每次加仓后都会重新计算（加权平均）

## ✅ 解决方案

### 修复原则

**正确的收益计算公式：**
```
收益 = 当前市值 - 总成本
     = position_value - (total_shares × avg_cost)

收益率 = 收益 / 总成本 × 100%
       = profit / (total_shares × avg_cost) × 100%
```

### 修复1: 止盈信号

**文件**: [src/strategy/engine.py](file://e:\LearnPY\Projects\StockBot\src\strategy\engine.py#L466-L516)

**修复后代码：**
```python
def _create_sell_signal(self, position: Position, market_data: MarketData, reason: str) -> Signal:
    """创建卖出信号"""
    price = market_data.current_price
    
    # ✅ 正确：使用 avg_cost 计算收益
    total_cost = position.total_shares * position.avg_cost
    profit = position.position_value - total_cost
    profit_pct = (profit / total_cost) * 100 if total_cost > 0 else 0
    
    # 重置持仓状态
    position.status = PositionStatus.CLOSED
    position.init_price = 0
    position.avg_cost = 0
    position.total_shares = 0
    position.position_value = 0
    position.add_count = 0
    position.last_update = datetime.now()
    
    # ... BOLL计算等后续代码 ...
    
    return Signal(
        symbol=position.symbol,
        name=market_data.name,
        signal_type=SignalType.SELL,
        price=price,
        change_pct=market_data.change_pct,
        reason=f"{reason}，总收益{profit:.2f}元 ({profit_pct:+.2f}%)",
        # ... 其他参数 ...
    )
```

### 修复2: 止损信号

**文件**: [src/strategy/engine.py](file://e:\LearnPY\Projects\StockBot\src\strategy\engine.py#L518-L568)

**修复后代码：**
```python
def _create_stop_signal(self, position: Position, market_data: MarketData, reason: str) -> Signal:
    """创建止损信号"""
    price = market_data.current_price
    
    # ✅ 正确：使用 avg_cost 计算损失
    total_cost = position.total_shares * position.avg_cost
    loss = total_cost - position.position_value
    loss_pct = (loss / total_cost) * 100 if total_cost > 0 else 0
    
    # 重置持仓状态
    position.status = PositionStatus.CLOSED
    position.init_price = 0
    position.avg_cost = 0
    position.total_shares = 0
    position.position_value = 0
    position.add_count = 0
    position.last_update = datetime.now()
    
    # ... BOLL计算等后续代码 ...
    
    return Signal(
        symbol=position.symbol,
        name=market_data.name,
        signal_type=SignalType.STOP,
        price=price,
        change_pct=market_data.change_pct,
        reason=f"{reason}，总损失{loss:.2f}元 ({loss_pct:+.2f}%)",
        # ... 其他参数 ...
    )
```

### 关键改进点

1. **使用 avg_cost 而非 init_price**:
   ```python
   # ❌ 错误
   profit = position.position_value - (position.total_shares * position.init_price)
   
   # ✅ 正确
   total_cost = position.total_shares * position.avg_cost
   profit = position.position_value - total_cost
   ```

2. **添加除零保护**:
   ```python
   profit_pct = (profit / total_cost) * 100 if total_cost > 0 else 0
   ```

3. **先计算再重置**:
   - 在重置持仓状态**之前**计算收益
   - 确保使用的是重置前的数据

## 📊 修复效果对比

### 示例场景

**交易过程：**
- 初始建仓: ¥1.300 × 10,000份
- 第1次加仓: ¥1.250 × 20,000份
- 第2次加仓: ¥1.200 × 40,000份
- 止盈卖出: ¥1.250 × 70,000份

**修复前（错误）：**
```
总收益: -3500.00元 (-3.85%)  ❌ 显示亏损
```

**修复后（正确）：**
```
总收益: +1470.00元 (+1.71%)  ✅ 显示盈利
```

### 不同场景测试

| 场景 | 初始价 | 平均成本 | 卖出价 | 修复前显示 | 修复后显示 |
|------|--------|---------|--------|-----------|-----------|
| 未加仓直接止盈 | ¥1.300 | ¥1.300 | ¥1.350 | +¥500 ✅ | +¥500 ✅ |
| 加仓后止盈 | ¥1.300 | ¥1.229 | ¥1.250 | -¥3,500 ❌ | +¥1,470 ✅ |
| 加仓后止损 | ¥1.300 | ¥1.229 | ¥1.150 | -¥10,500 ⚠️ | -¥5,530 ✅ |

**说明：**
- 未加仓时，`init_price == avg_cost`，两种算法结果相同
- 加仓后，`avg_cost < init_price`，使用 init_price 会严重低估收益

## 💡 最佳实践

### 1. 马丁格尔策略收益计算规范

**核心原则：**
- ✅ 始终使用 `avg_cost`（平均成本）作为收益计算基准
- ❌ 不要使用 `init_price`（初始价格），它只代表第一次建仓价格

**适用场景：**
- 止盈信号
- 止损信号
- 任何需要计算盈亏的场景

### 2. 代码审查检查点

在涉及收益计算的代码中，检查：
- [ ] 是否使用了正确的成本基准（avg_cost）
- [ ] 是否在重置持仓前完成计算
- [ ] 是否有除零保护
- [ ] 正负号是否符合业务逻辑

### 3. 单元测试建议

```python
def test_profit_calculation_with_additions():
    """测试加仓后的收益计算"""
    # 模拟多次加仓
    position = Position(
        symbol="sh.513120",
        name="港股创新药ETF",
        status=PositionStatus.FULL,
        init_price=1.300,      # 初始建仓价
        avg_cost=1.229,        # 加仓后的平均成本
        total_shares=70000,
        position_value=87500,  # 70000 × 1.250
        add_count=2
    )
    
    # 计算收益
    total_cost = position.total_shares * position.avg_cost
    profit = position.position_value - total_cost
    profit_pct = (profit / total_cost) * 100
    
    # 验证结果
    assert abs(profit - 1470.0) < 0.01  # 应该盈利约1470元
    assert abs(profit_pct - 1.71) < 0.01  # 收益率约1.71%
```

## ⚠️ 注意事项

### 1. 历史数据影响

修复只影响**未来的**止盈/止损信号，已持久化的历史信号不会改变。

### 2. 日志与通知

修复后，飞书通知和控制台日志中的收益数字会变为正确值：

**修复前：**
```
🔴 卖出信号
标的: 港股创新药ETF广发 (sh.513120)
原因: 达到止盈目标，总收益-3500.00元 (-3.85%)  ❌
```

**修复后：**
```
🔴 卖出信号
标的: 港股创新药ETF广发 (sh.513120)
原因: 达到止盈目标，总收益+1470.00元 (+1.71%)  ✅
```

### 3. 数据库存储

如果系统将收益保存到数据库，确保：
- 使用修复后的计算逻辑
- 历史数据的收益字段可能需要重新计算或标记为"旧算法"

## 🎯 相关代码位置

### 需要检查的其他地方

虽然本次修复了主要的两个方法，但建议检查整个代码库中是否还有其他地方使用了错误的公式：

```bash
# 搜索所有使用 init_price 计算收益的地方
grep -r "init_price.*position_value\|position_value.*init_price" src/
```

### 相关文件

- **策略引擎**: [src/strategy/engine.py](file://e:\LearnPY\Projects\StockBot\src\strategy\engine.py)
- **数据模型**: [src/models/models.py](file://e:\LearnPY\Projects\StockBot\src\models\models.py)
- **调度器**: [src/utils/scheduler.py](file://e:\LearnPY\Projects\StockBot\src\utils\scheduler.py)（输出信号）
- **飞书通知**: [src/utils/notification.py](file://e:\LearnPY\Projects\StockBot\src\utils\notification.py)（显示收益）

## 🎉 总结

**问题根源:**
- 错误地使用 `init_price`（初始建仓价格）作为收益计算基准
- 在马丁格尔策略中，经过多次加仓后，`init_price` 远高于实际的平均成本
- 导致盈利被低估，甚至显示为亏损

**解决方案:**
- 改用 `avg_cost`（加权平均成本）作为计算基准
- 同时修复了止盈和止损两个方法
- 添加除零保护，提高代码健壮性

**修复结果:**
- ✅ 止盈收益计算正确
- ✅ 止损损失计算正确
- ✅ 符合马丁格尔策略的实际盈亏情况
- ✅ 飞书通知和控制台日志显示准确

---

**修复版本**: v2.2.6  
**修复日期**: 2026-04-15  
**问题类型**: 收益计算逻辑错误
