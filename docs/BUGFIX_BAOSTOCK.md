# Bug 修复 - BaoStock 数据格式处理

## 🐛 问题描述

### 错误信息
```
测试 2: 获取股票基本信息时，发生 错误：a bytes-like object is required, not 'list'
```

### 问题原因

BaoStock 的 `query_stock_basic()` 返回的数据格式不是 XML 字符串，而是一个类似 DataFrame 的对象，需要通过 `rs.next()` 和 `rs.get_row_data()` 来遍历获取。

**错误代码：**
```python
# ❌ 错误的方式
if rs.error_code == '0' and rs.data:
    import xml.etree.ElementTree as ET
    root = ET.fromstring(rs.data)  # 这里会报错，因为 rs.data 不是 XML 字符串
```

## ✅ 修复方案

### 1. 修复 data_provider.py

**文件：** `src/market/data_provider.py`

**修复前：**
```python
def _get_stock_name(self, symbol: str) -> str:
    if rs.error_code == '0' and rs.data:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(rs.data)  # ❌ 错误
        for child in root:
            if child.tag == 'row':
                return child.attrib.get('code_name', symbol)
```

**修复后：**
```python
def _get_stock_name(self, symbol: str) -> str:
    if rs.error_code == '0':
        # ✅ 正确的方式：遍历结果集
        data_list = []
        while rs.next():
            data_list.append(rs.get_row_data())
        
        if data_list:
            row = data_list[0]
            if len(row) >= 2:
                return row[1]  # code_name 是第二个字段
```

### 2. 修复 test_baostock.py

**文件：** `test_baostock.py`

**修复前：**
```python
if rs.error_code == '0' and rs.data:
    import xml.etree.ElementTree as ET
    root = ET.fromstring(rs.data)  # ❌ 错误
    for child in root:
        if child.tag == 'row':
            code_name = child.attrib.get('code_name', '未知')
```

**修复后：**
```python
if rs.error_code == '0':
    # ✅ 正确的方式：遍历结果集
    data_list = []
    while rs.next():
        data_list.append(rs.get_row_data())
    
    if data_list:
        row = data_list[0]
        code = row[0]
        code_name = row[1]
        exchange = row[2] if len(row) >= 3 else 'N/A'
```

## 📊 BaoStock 数据格式说明

### query_stock_basic 返回值

`query_stock_basic(code)` 返回的结果是一个对象，包含：

- `error_code`: 错误代码（'0' 表示成功）
- `error_msg`: 错误信息
- `data`: 数据（注意：这不是 XML，不要直接使用）

### 正确的数据获取方式

```python
import baostock as bs

# 登录
lg = bs.login()

# 查询
rs = bs.query_stock_basic(code="sh.600938")

if rs.error_code == '0':
    # 遍历结果集
    data_list = []
    while rs.next():
        data_list.append(rs.get_row_data())
    
    # data_list 现在是二维列表
    # 每个元素是一行数据，每行是一个列表
    if data_list:
        row = data_list[0]  # 第一行
        # 字段顺序：code, code_name, exchange, ipo_date, ...
        code = row[0]           # 股票代码
        code_name = row[1]      # 股票名称
        exchange = row[2]       # 交易所
```

### 字段顺序

`query_stock_basic` 返回的字段顺序为：
1. `code` - 证券代码
2. `code_name` - 证券名称
3. `exchange` - 交易所
4. `ipo_date` - 上市日期
5. `issue_price` - 发行价格
6. `undivided_per_share` - 每股未分配利润
7. `surplus_reserve_per_share` - 每股盈余公积金
8. `per_share_retained_earnings` - 每股留存收益
9. `eps` - 每股收益
10. `bvps` - 每股净资产
11. `total_shares` - 总股本
12. `circulating_shares` - 流通股本

## 🔍 其他 BaoStock API 的数据获取方式

### 1. query_history_k_data_plus (K 线数据)

```python
rs = bs.query_history_k_data_plus(
    code="sh.600938",
    fields="date,open,high,low,close,vol,pctChg",
    start_date="2026-01-01",
    end_date="2026-03-19",
    frequency="d",
    adjustflag="2"
)

# 正确获取数据
data_list = []
while rs.next():
    data_list.append(rs.get_row_data())

# 转换为 DataFrame（可选）
import pandas as pd
df = pd.DataFrame(data_list, columns=rs.fields)
```

### 2. query_realtime_quotes (实时行情)

```python
rs = bs.query_realtime_quotes(code="sh.600938")

# 获取数据
data_list = []
while rs.next():
    data_list.append(rs.get_row_data())
```

### 3. query_index_history (指数历史)

```python
rs = bs.query_index_history(
    code="sh.000001",
    start_date="2026-01-01",
    end_date="2026-03-19",
    fields="date,close,pctChg"
)

# 同样的方式获取数据
data_list = []
while rs.next():
    data_list.append(rs.get_row_data())
```

## 🧪 验证修复

运行以下命令验证修复是否成功：

```bash
# 方法 1: 运行快速验证脚本
python verify_fix.py

# 方法 2: 运行完整测试
python test_baostock.py

# 方法 3: 直接启动系统测试
python main.py
curl http://localhost:8000/api/market/600938
```

## 📝 关键要点

### ✅ 正确做法
1. 使用 `rs.next()` 遍历结果集
2. 使用 `rs.get_row_data()` 获取每一行数据
3. 返回的是列表（list），按索引访问字段
4. 使用 `rs.fields` 可以获取字段名列表

### ❌ 错误做法
1. ~~不要尝试解析 `rs.data` 为 XML~~
2. ~~不要直接使用 `rs.data` 属性~~
3. ~~不要假设返回的是字典或 JSON~~

## 🎯 修复后的效果

修复后可以正常获取：

- ✅ 股票名称（如 "中国海油"）
- ✅ 股票代码（如 "600938"）
- ✅ 交易所（如 "上海证券交易所"）
- ✅ 所有通过 `query_stock_basic` 返回的字段

## 📚 参考资料

- [BaoStock 官方文档 - 股票基本信息](http://baostock.com/baostock/index.php/%E8%82%A1%E7%A5%A8%E5%9F%BA%E6%9C%AC%E4%BF%A1%E6%81%AF)
- [BaoStock API 文档](http://baostock.com/baostock/index.php/API_%E6%96%87%E6%A1%A3)

---

*修复日期：2026-03-19*  
*版本：v1.3.1*
