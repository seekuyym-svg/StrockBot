# Bug 修复 - BaoStock 字段名错误

## 🐛 问题描述

运行测试时报错：
```
❌ 查询失败：日线指标参数传入错误:vol
结果：0 条数据
```

## 🔍 问题原因

BaoStock 的 `query_history_k_data_plus()` API **不支持 `vol` 字段名**，必须使用 **`volume`**。

### 错误的字段名
```python
fields="date,open,high,low,close,vol,pctChg"  # ❌ vol 是错误的
```

### 正确的字段名
```python
fields="date,open,high,low,close,volume,pctChg"  # ✅ volume 是正确的
```

---

## ✅ 已修复的文件

### 1. test_600519.py

**修改位置：** 3 处

```python
# 场景 1: 不复权 + 90 天
fields="date,open,high,low,close,volume,pctChg"  # ✅

# 场景 2: 前复权 + 90 天
fields="date,open,high,low,close,volume,pctChg"  # ✅

# 场景 3: 不复权 + 1 年
fields="date,open,high,low,close,volume,pctChg"  # ✅
```

### 2. src/market/data_provider.py

**修改位置：** `_get_klines()` 方法

```python
rs = bs.query_history_k_data_plus(
    code=bs_code,
    fields="date,open,high,low,close,volume,amount,pctChg,turn",  # ✅
    start_date=start_date,
    end_date=end_date,
    frequency=period,
    adjustflag="3"
)
```

### 3. test_baostock.py

**修改位置：** `test_klines()` 函数

```python
rs = bs.query_history_k_data_plus(
    code="sh.600938",
    fields="date,open,high,low,close,volume,pctChg",  # ✅
    start_date=start_date,
    end_date=end_date,
    frequency="d",
    adjustflag="3"
)
```

---

## 📊 BaoStock 支持的字段列表

根据 BaoStock 官方文档，`query_history_k_data_plus()` 支持的字段如下：

| 字段代码 | 字段名称 | 说明 |
|---------|---------|------|
| date | 日期 | 交易日期 |
| open | 开盘价 | 开盘价格 |
| high | 最高价 | 最高价格 |
| low | 最低价 | 最低价格 |
| close | 收盘价 | 收盘价格 |
| **volume** | 成交量 | 成交股数（注意：不是 vol） |
| amount | 成交额 | 成交金额 |
| pctChg | 涨跌幅 | 涨跌幅百分比 |
| turn | 换手率 | 换手率百分比 |
| pe1 | 市盈率（TTM） | 滚动市盈率 |
| pb | 市净率 | 市净率 |
| ps | 市销率 | 市销率 |
| pcf | 市现率 | 市现率 |

**重要提示：**
- ✅ 使用 `volume` 表示成交量
- ❌ **不要使用** `vol`（不支持）

---

## 🧪 验证修复

运行测试脚本验证修复效果：

```bash
# 测试贵州茅台
python test_600519.py

# 预期输出：
# ✅ 查询成功，开始读取数据...
# 结果：XX 条数据
# ✅ 成功！最新数据：['2026-03-19', 'XXXX.XX', ...]
```

---

## 💡 经验教训

### 1. 字段名规范
不同数据源的字段命名规范不同：
- **BaoStock**: `volume`
- **Tushare**: `vol`
- **AKShare**: 可能是 `volume` 或 `vol`

**建议：** 查阅官方文档确认字段名

### 2. 错误处理优化

在代码中添加更详细的错误提示：

```python
rs = bs.query_history_k_data_plus(...)

if rs.error_code != '0':
    print(f"❌ 查询失败：{rs.error_msg}")
    print(f"💡 可能的原因:")
    print(f"   - 字段名错误（vol vs volume）")
    print(f"   - 股票代码格式错误")
    print(f"   - 日期范围无效")
    return False
```

### 3. 统一字段映射

在数据提供者中使用字段映射字典：

```python
# BaoStock 字段映射
BAOSTOCK_FIELDS = {
    'date': '日期',
    'open': '开盘',
    'high': '最高',
    'low': '最低',
    'close': '收盘',
    'volume': '成交量',  # 注意：不是 vol
    'amount': '成交额',
    'pctChg': '涨跌幅',
    'turn': '换手率'
}
```

---

## 📚 参考资料

- [BaoStock 官方文档 - K 线数据](http://baostock.com/baostock/index.php/%E8%AF%81%E5%88%B8%E5%8E%86%E5%8F%B2%E6%95%B0%E6%8D%AE)
- [BaoStock API 字段说明](http://baostock.com/baostock/index.php/API_%E6%96%87%E6%A1%A3#.E6.A0.BC.E5.BC.8F.E8.AF.B4.E6.98.8E)

---

*修复日期：2026-03-19*  
*版本：v1.3.3*
