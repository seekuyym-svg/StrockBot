# 故障排查 - "未获取到 K 线数据"

## 🐛 问题描述

运行 `test_baostock.py` 时报错：`❌ 未获取到 K 线数据`

---

## 🔍 可能的原因

### 1. 网络连接问题
BaoStock 需要联网获取数据，如果网络不通会导致获取失败。

**诊断方法:**
```bash
# 测试能否访问 BaoStock 服务器
ping baostock.com
```

### 2. 日期范围问题
如果日期范围设置不当（如未来日期），可能获取不到数据。

**检查点:**
- 开始日期不能晚于结束日期
- 结束日期不能是未来日期
- 股票在指定日期范围内必须有交易数据

### 3. 股票代码格式问题
BaoStock 要求特定的股票代码格式。

**正确格式:**
- 上交所股票：`sh.600938`
- 深交所股票：`sz.000792`
- 上证指数：`sh.000001`

### 4. BaoStock 服务维护
BaoStock 服务器可能在进行维护或升级。

**检查方法:**
- 访问官网：http://baostock.com/
- 查看是否有公告

### 5. 防火墙/代理问题
公司防火墙或代理服务器可能阻止了连接。

**解决方法:**
- 关闭代理
- 添加防火墙白名单

---

## ✅ 解决方案

### 方案 1: 运行调试脚本

我已创建了详细的调试脚本，可以提供更多信息：

```bash
python test_baostock_debug.py
```

这个脚本会：
1. 显示登录状态
2. 显示查询参数
3. 显示返回的状态码
4. 逐行打印读取的数据
5. 尝试扩大日期范围
6. 测试其他股票

### 方案 2: 检查并修改日期范围

**修改 test_baostock.py:**

```python
# 原来的代码（30 天）
start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

# 修改为 90 天（增加获取数据的概率）
start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
```

### 方案 3: 测试多个股票

有些股票可能因为上市时间短或其他原因没有数据，测试多个股票可以确认是否是单个股票的问题：

```python
stocks_to_test = [
    ("sh.600938", "中国海油"),
    ("sz.000792", "盐湖股份"),
    ("sh.600519", "贵州茅台"),
]

for code, name in stocks_to_test:
    rs = bs.query_history_k_data_plus(
        code=code,
        fields="date,close",
        start_date="2026-01-01",
        end_date="2026-03-19",
        frequency="d",
        adjustflag="2"
    )
    
    data_list = []
    while rs.next():
        data_list.append(rs.get_row_data())
    
    print(f"{name}: {len(data_list)} 条数据")
```

### 方案 4: 检查复权类型

不同的复权类型可能影响数据获取：

```python
# 不复权（推荐用于实时价格）
adjustflag="3"

# 前复权（推荐用于回测）
adjustflag="2"

# 后复权
adjustflag="1"
```

**建议：** 如果使用前复权获取不到数据，尝试不复权。

### 方案 5: 验证 BaoStock 连接

创建一个简单的测试脚本：

```python
import baostock as bs

# 登录
lg = bs.login()
print(f"登录状态：{lg.error_code}")
print(f"登录消息：{lg.error_msg}")

if lg.error_code == '0':
    # 测试获取上证指数
    rs = bs.query_index_history(
        code="sh.000001",
        start_date="20260301",
        end_date="20260319",
        fields="date,close"
    )
    
    print(f"查询状态：{rs.error_code}")
    
    data_list = []
    while rs.next():
        data_list.append(rs.get_row_data())
    
    print(f"获取到 {len(data_list)} 条数据")
    
    if data_list:
        print(f"第一条数据：{data_list[0]}")
        print(f"最后一条数据：{data_list[-1]}")
    
    bs.logout()
```

---

## 🛠️ 代码修复建议

### 修复 test_baostock.py

如果确认是日期范围问题，修改测试文件：

```python
def test_klines():
    """测试 3: 获取日 K 线数据"""
    print("\n" + "=" * 60)
    print("测试 3: 获取日 K 线数据（最近 90 天）")
    print("=" * 60)
    
    try:
        import baostock as bs
        
        lg = bs.login()
        if lg.error_code != '0':
            print(f"❌ 登录失败：{lg.error_msg}")
            return False
        
        # 修改为 90 天
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
        
        print(f"日期范围：{start_date} 至 {end_date}")
        
        # 获取日线数据（不改用不复权）
        rs = bs.query_history_k_data_plus(
            code="sh.600938",
            fields="date,open,high,low,close,vol,pctChg",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="3"  # 改为不复权
        )
        
        data_list = []
        while rs.next():
            data_list.append(rs.get_row_data())
        
        bs.logout()
        
        if data_list:
            import pandas as pd
            df = pd.DataFrame(data_list, columns=rs.fields)
            
            print(f"✅ 获取到 {len(df)} 条 K 线数据")
            print(f"\n最近 5 个交易日:")
            print(df[['date', 'open', 'high', 'low', 'close', 'pctChg']].tail())
            return True
        else:
            print("❌ 未获取到 K 线数据")
            print(f"提示：可能是日期范围问题或股票代码问题")
            return False
            
    except Exception as e:
        print(f"❌ 错误：{e}")
        import traceback
        traceback.print_exc()
        return False
```

### 修复 data_provider.py

确保使用正确的参数：

```python
def _get_klines(self, symbol: str, period: str = "d", count: int = 120):
    """获取 K 线数据"""
    if not BAOSTOCK_AVAILABLE or not self.session:
        return pd.DataFrame()
    
    try:
        bs_code = self._format_bs_code(symbol)
        
        # 使用更大的日期范围确保能获取到数据
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')  # 2 年
        
        rs = bs.query_history_k_data_plus(
            code=bs_code,
            fields="date,open,high,low,close,vol,amount,pctChg,turn",
            start_date=start_date,
            end_date=end_date,
            frequency=period,
            adjustflag="3"  # 不复权用于实时数据
        )
        
        data_list = []
        while rs.next():
            data_list.append(rs.get_row_data())
        
        if not data_list:
            logger.warning(f"未获取到 {symbol} 的 K 线数据")
            return pd.DataFrame()
        
        df = pd.DataFrame(data_list, columns=rs.fields)
        df = df.rename(columns={
            'date': '日期',
            'open': '开盘',
            'high': '最高',
            'low': '最低',
            'close': '收盘',
            'vol': '成交量',
            'amount': '成交额'
        })
        
        return df.tail(count)
        
    except Exception as e:
        logger.error(f"获取 K 线失败：{e}")
        return pd.DataFrame()
```

---

## 📊 常见错误代码及含义

| 错误代码 | 含义 | 解决方法 |
|---------|------|---------|
| 10001 | 网络异常 | 检查网络连接 |
| 10002 | 服务器异常 | 稍后重试 |
| 10003 | 无权限 | 检查股票代码 |
| 10004 | 无数据 | 调整日期范围 |
| 10005 | 参数错误 | 检查参数格式 |

---

## 🎯 快速诊断流程

```
1. 运行调试脚本
   ↓
   python test_baostock_debug.py
   
2. 查看登录状态
   ↓
   error_code == '0'? 
   
3. 查看查询结果
   ↓
   有数据 → ✅ 成功
   无数据 → 继续下一步
   
4. 扩大日期范围
   ↓
   从 30 天改为 90 天或更长
   
5. 测试其他股票
   ↓
   如果其他股票有数据 → 原股票问题
   如果都没有数据 → 网络或服务问题
   
6. 检查网络
   ↓
   ping baostock.com
   访问 http://baostock.com/
```

---

## 💡 最佳实践

### 1. 日期范围设置

```python
# 实时数据：最近 1-2 年
start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

# 回测数据：根据需要设置
start_date = "2020-01-01"  # 固定开始日期
```

### 2. 复权选择

```python
# 实时行情/信号生成：不复权
adjustflag="3"

# 历史回测：前复权
adjustflag="2"
```

### 3. 错误处理

```python
try:
    data = get_market_data("600938")
    if data is None or data.current_price <= 0:
        logger.warning("数据异常，使用备用数据源")
        # Fallback logic
except Exception as e:
    logger.error(f"获取数据失败：{e}")
```

---

## 📞 获取帮助

如果以上方法都无法解决问题：

1. **查看官方文档**: http://baostock.com/
2. **检查 GitHub Issues**: 搜索类似问题
3. **运行完整诊断**: `python test_baostock_debug.py`
4. **查看日志**: 检查程序输出的详细错误信息

---

*最后更新：2026-03-19*
