# 个股多头/空头排列判断功能说明

## 📖 功能概述

本模块用于判断配置的股票池中每只股票当前是处于**多头排列**还是**空头排列**状态，并提供综合评分和详细的技术指标分析。

## 🎯 核心功能

### 1. 均线排列判断
- **多头排列**: MA5 > MA10 > MA20（短期均线在长期均线上方）
- **空头排列**: MA5 < MA10 < MA20（短期均线在长期均线下方）
- **中性震荡**: 均线相互缠绕，无明显趋势

### 2. 辅助技术指标
- **MACD**: 判断金叉/死叉及零轴位置
- **RSI**: 判断超买/超卖状态
- **布林带**: 判断价格相对位置
- **成交量**: 验证价量关系

### 3. 综合评分系统
根据多个指标进行加权评分：
- 均线排列: ±3分
- MACD信号: ±1分
- RSI强弱: ±1分
- 布林带突破: ±1分
- 成交量验证: ±0.5分

**评分解读**:
- `≥ 2`: 🟢 多头排列 (强烈看涨)
- `0 ~ 2`: 🟡 偏多震荡 (谨慎看涨)
- `= 0`: ⚪ 无明显趋势 (观望)
- `-2 ~ 0`: 🟠 偏空震荡 (谨慎看跌)
- `≤ -2`: 🔴 空头排列 (强烈看跌)

## 🚀 使用方法

### 方式一：命令行运行

```bash
# 分析配置的股票池中的所有股票
python -m src.utils.bull_bear_a
```

### 方式二：代码调用

```python
from src.utils.bull_bear_a import TrendAnalyzer

# 创建分析器
analyzer = TrendAnalyzer()

# 分析单只股票
result = analyzer.analyze_stock("sz.002706", "良信股份")
print(f"趋势: {result['trend']}")
print(f"评分: {result['score']}")
print(f"结论: {result['conclusion']}")

# 批量分析股票池
results = analyzer.analyze_stock_pool()
for r in results:
    print(f"{r['name']}: {r['conclusion']}")
```

## 📊 输出示例

```
============================================================
📊 分析 华海药业 (sh.600521)
============================================================
最新日期: 2026-04-17
最新收盘价: 16.88
均线状态: 均线多头排列 (MA5>MA10>MA20)
MA5: 16.32 | MA10: 16.14 | MA20: 15.87 | MA60: 16.00
MACD: DIF=0.166 | DEA=0.068 | 柱线=0.197
RSI(14): 61.8
布林带: 上轨=17.11 | 中轨=15.87 | 下轨=14.62
成交量: 57951400 (20日均量: 27988425, 比例: 2.07)
综合评分: 5.5 (偏多)
关键信号: 均线多头排列; MACD金叉且位于零轴上; RSI强势 (61.8); 价涨量增

📊 最终判断: 🟢 多头排列 (强烈看涨)
```

## 🔧 技术实现

### 数据源
- **统一使用腾讯财经API**
- 历史K线: `http://web.ifzq.gtimg.cn/appstock/app/fqkline/get`
- 前复权数据，确保准确性

### 判断规则

#### 1. 均线排列判定
```python
# 多头排列
if MA5 > MA10 > MA20 and MA5/MA20 > 1.01:
    trend = 'bullish'

# 空头排列
if MA5 < MA10 < MA20 and MA20/MA5 > 1.01:
    trend = 'bearish'
```

#### 2. MACD辅助判断
```python
# 金叉且在零轴上
if DIF > DEA and DIF > 0:
    score += 1

# 死叉且在零轴下
if DIF < DEA and DIF < 0:
    score -= 1
```

#### 3. RSI强弱判断
```python
# RSI强势
if RSI > 60:
    score += 1

# RSI弱势
if RSI < 40:
    score -= 1
```

#### 4. 布林带位置
```python
# 突破上轨
if close > upper_band:
    score += 1

# 跌破下轨
if close < lower_band:
    score -= 1
```

#### 5. 成交量验证
```python
vol_ratio = volume / vol_ma20

# 价涨量增
if vol_ratio > 1.2 and close > prev_close:
    score += 0.5

# 价跌量增
if vol_ratio > 1.2 and close < prev_close:
    score -= 0.5
```

## 📋 配置说明

股票池从 `config.yaml` 的 `stock_news_monitor.stock_pool` 中读取：

```yaml
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
```

## ⚠️ 注意事项

### 1. 数据要求
- 至少需要60个交易日的历史数据
- 使用前复权数据（qfq）确保准确性
- 自动跳过分红日等异常数据

### 2. 请求频率
- 每只股票分析间隔1秒
- 避免频繁请求被限流

### 3. 边界处理
- 均线粘合时（差距<1%）判定为中性
- 数据不足时返回None并记录警告
- 网络异常时重试机制

### 4. 编码处理
- 腾讯财经API返回GBK编码
- Windows终端注意Unicode输出问题

## 📈 实际应用案例

### 案例1: 盐湖股份 (sz.000792)
- **评分**: 4.0
- **判断**: 🟢 多头排列 (强烈看涨)
- **关键信号**: 
  - 均线多头排列
  - MACD金叉且位于零轴上

### 案例2: 良信股份 (sz.002706)
- **评分**: 0.5
- **判断**: 🟡 偏多震荡 (谨慎看涨)
- **关键信号**: 
  - 均线相互缠绕
  - 价涨量增

### 案例3: 华海药业 (sh.600521)
- **评分**: 5.5
- **判断**: 🟢 多头排列 (强烈看涨)
- **关键信号**: 
  - 均线多头排列
  - MACD金叉且位于零轴上
  - RSI强势 (61.8)
  - 价涨量增

### 案例4: 银轮股份 (sz.002126)
- **评分**: 5.0
- **判断**: 🟢 多头排列 (强烈看涨)
- **关键信号**: 
  - 均线多头排列
  - MACD金叉且位于零轴上
  - RSI强势 (76.6)

## 🔗 相关文件

- 实现文件: `src/utils/bull_bear_a.py`
- 配置文件: `config.yaml`
- 数据源: `src/market/data_provider.py` (腾讯财经API)

## 📝 更新日志

### 2026-04-19
- ✅ 重写模块，使用腾讯财经API替代AKShare
- ✅ 修复字符串格式化bug
- ✅ 集成到配置系统，自动读取股票池
- ✅ 封装为TrendAnalyzer类，支持模块化调用
- ✅ 添加详细的汇总报告功能
- ✅ 完善异常处理和日志记录

---

**最后更新**: 2026-04-19  
**维护人员**: AI Assistant
