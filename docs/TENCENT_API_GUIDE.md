# 腾讯财经API使用指南

## 📖 概述

本项目已统一使用**腾讯财经API**作为唯一的股票行情数据源，用于获取日/周/月涨跌幅和流通市值等指标。

## 🚀 快速开始

### 1. 基本用法

```python
from src.utils.news_scheduler import NewsMonitorScheduler

# 创建调度器实例
scheduler = NewsMonitorScheduler.__new__(NewsMonitorScheduler)

# 获取股票行情指标
metrics = scheduler._fetch_stock_metrics("sz.002706", "良信股份")

# 输出结果
print(f"日涨跌幅: {metrics['daily_change_pct']:+.2f}%")
print(f"周涨跌幅: {metrics['weekly_change_pct']:+.2f}%")
print(f"月涨跌幅: {metrics['monthly_change_pct']:+.2f}%")
print(f"流通市值: {metrics['circulating_market_cap']}亿")
```

### 2. 在资讯监控中使用

资讯监控功能会自动获取每只股票的行情指标，并在飞书通知中展示：

```yaml
# config.yaml
stock_news_monitor:
  enabled: true
  stock_pool:
    - code: "sz.002706"
      name: "良信股份"
      index: "一"
    - code: "sh.600519"
      name: "贵州茅台"
      index: "二"
```

## 📊 API接口说明

### 实时行情API

**接口地址**: `http://qt.gtimg.cn/q={market}{code}`

**示例**:
```
http://qt.gtimg.cn/q=sz002706
http://qt.gtimg.cn/q=sh600519
```

**返回格式**: 
```
v_sz002706="1~良信股份~002706~11.21~10.19~10.18~..."
```

**关键字段**:
- `[3]`: 当前价格
- `[32]`: 日涨跌幅百分比
- `[72]` 或 `[76]`: 流通股本（股数）

### 历史K线API

**接口地址**: `http://web.ifzq.gtimg.cn/appstock/app/fqkline/get`

**参数**:
```python
params = {
    "param": f"{market}{code},day,,,{days},qfq"
}
```

**返回格式**: JSON
```json
{
  "code": 0,
  "data": {
    "sz002706": {
      "qfqday": [
        ["2024-01-01", "开盘", "收盘", "最高", "最低", "成交量", "成交额"],
        ...
      ]
    }
  }
}
```

## 🔧 计算方法

### 日涨跌幅
直接从实时行情API的字段 `[32]` 获取，无需计算。

### 周涨跌幅（近5个交易日）
```python
latest_close = klines['收盘'].iloc[-1]
price_1w_ago = klines['收盘'].iloc[-6]  # 5个交易日前
weekly_change = ((latest_close - price_1w_ago) / price_1w_ago) * 100
```

### 月涨跌幅（近20个交易日）
```python
latest_close = klines['收盘'].iloc[-1]
price_1m_ago = klines['收盘'].iloc[-21]  # 20个交易日前
monthly_change = ((latest_close - price_1m_ago) / price_1m_ago) * 100
```

### 流通市值
```python
current_price = float(parts[3])  # 当前价格
circulating_shares = float(parts[72])  # 流通股本（股数）
market_cap_billion = (circulating_shares * current_price) / 1e8  # 转换为亿元
```

## ⚠️ 注意事项

### 1. 编码问题
腾讯财经API返回的是**GBK编码**，必须设置：
```python
response.encoding = 'gbk'
```

### 2. K线数据异常
部分日期的K线数据第7个字段可能是字典（分红信息），需要跳过：
```python
if isinstance(line, dict):
    continue  # 跳过分红数据
```

### 3. 边界检查
计算涨跌幅前必须检查数据量：
- 周涨幅: 至少需要6条K线数据
- 月涨幅: 至少需要21条K线数据

### 4. 请求频率
建议每次请求之间间隔1秒，避免被限流：
```python
import time
time.sleep(1)
```

## 🧪 测试

### 运行测试脚本
```bash
# 测试单个股票的行情指标
python test_tencent_stock_metrics.py

# 测试完整的资讯监控流程
python test_news_monitor_integration.py
```

### 调试字段结构
```bash
# 查看腾讯财经API返回的完整字段
python debug_tencent_fields.py
```

## 📈 优势对比

| 特性 | 腾讯财经 | 雪球 | AKShare | BaoStock |
|------|---------|------|---------|----------|
| 稳定性 | ✅ 高 | ⚠️ 中 | ⚠️ 中 | ⚠️ 中 |
| 响应速度 | ✅ 快 | ⚠️ 慢 | ⚠️ 慢 | ⚠️ 慢 |
| 依赖安装 | ❌ 无 | ❌ 无 | ✅ 需安装 | ✅ 需安装 |
| 数据完整性 | ✅ 完整 | ✅ 完整 | ✅ 完整 | ✅ 完整 |
| 维护成本 | ✅ 低 | ⚠️ 中 | ⚠️ 中 | ⚠️ 中 |

## 🔗 相关文档

- [重构总结](TENCENT_API_REFACTOR_SUMMARY.md)
- [项目README](README.md)
- [快速开始](QUICKSTART.md)

---

**最后更新**: 2026-04-19
