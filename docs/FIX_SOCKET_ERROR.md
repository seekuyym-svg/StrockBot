# Bug 修复 - WinError 10038 Socket 操作错误

## 🐛 问题描述

运行测试 4（获取实时行情）时报错：
```
[WinError 10038] 在一个非套接字上尝试了一个操作
```

## 🔍 问题原因

在 Windows 系统上，BaoStock 的 `logout()` 函数被**多次调用**或在**已经关闭的连接**上调用，导致 Socket 错误。

### 错误场景

```python
def test_realtime_quote():
    lg = bs.login()
    
    # 第一次查询
    rs = bs.query_history_k_data_plus(...)
    bs.logout()  # ❌ 第一次 logout，连接已关闭
    
    # 如果第一次没有数据，尝试第二次查询
    if not data_list:
        rs2 = bs.query_history_k_data_plus(...)  # ⚠️ 使用已关闭的连接
        # ...
        bs.logout()  # ❌ 第二次 logout，报错！
```

---

## ✅ 修复方案

### 核心原则

**每个测试函数中只调用一次 `logout()`，并且在函数结束前调用。**

### 修复后的代码结构

```python
def test_realtime_quote():
    """测试 4: 获取实时行情"""
    try:
        import baostock as bs
        
        lg = bs.login()
        if lg.error_code != '0':
            return False
        
        # 场景 1: 获取 5 分钟 K 线
        rs = bs.query_history_k_data_plus(...)
        data_list = []
        while rs.next():
            data_list.append(rs.get_row_data())
        
        if data_list:
            # 处理数据...
            bs.logout()  # ✅ 成功则 logout 并返回
            return True
        
        # 场景 2: 获取日线数据（不先 logout）
        else:
            rs2 = bs.query_history_k_data_plus(...)
            data_list2 = []
            while rs2.next():
                data_list2.append(rs2.get_row_data())
            
            if data_list2:
                # 处理数据...
                bs.logout()  # ✅ 成功则 logout 并返回
                return True
            else:
                bs.logout()  # ✅ 无数据也要 logout
                return False
    
    except Exception as e:
        # 异常时也要 logout
        try:
            bs.logout()
        except:
            pass
        return False
```

---

## 📊 已修复的文件

### test_baostock.py

**修复位置：** `test_realtime_quote()` 函数

**修复内容：**
1. ✅ 移除了第 184 行的提前 `logout()`
2. ✅ 在每个分支的末尾调用 `logout()`
3. ✅ 异常处理中也添加 `logout()`

**修复后的逻辑流程：**

```
登录 BaoStock
    ↓
查询 5 分钟 K 线
    ↓
有数据？
    ├─ YES → 显示数据 → logout() → return True
    └─ NO
        ↓
        查询日线数据
        ↓
        有数据？
            ├─ YES → 显示数据 → logout() → return True
            └─ NO → logout() → return False
        ↓
异常？
    └─ 捕获异常 → 尝试 logout() → return False
```

---

## 💡 最佳实践

### 1. 单一出口原则（推荐）

每个测试函数只有一个 `logout()` 调用点：

```python
def test_xxx():
    lg = bs.login()
    try:
        # ... 业务逻辑 ...
        return result
    finally:
        bs.logout()  # ✅ 总是执行
```

### 2. 多出口时的处理

如果有多个返回点，确保每个路径都调用 `logout()`：

```python
def test_xxx():
    lg = bs.login()
    
    if condition1:
        # ...
        bs.logout()
        return True
    
    if condition2:
        # ...
        bs.logout()
        return False
    
    # ...
    bs.logout()
    return result
```

### 3. 使用上下文管理器（最优）

如果可能，使用上下文管理器自动管理连接：

```python
class BaoStockSession:
    def __enter__(self):
        self.lg = bs.login()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        bs.logout()  # 自动清理
    
    def query(self, ...):
        # ...

# 使用
with BaoStockSession() as session:
    data = session.query(...)
# 自动 logout，即使发生异常
```

---

## 🧪 验证修复

运行测试脚本：

```bash
python test_baostock.py
```

**预期输出：**
```
测试 4: 获取实时行情（5 分钟 K 线）
============================================================
✅ 最新行情:
   时间：2026-03-19 XX:XX
   现价：XX.XX
   涨跌幅：X.XX%
   成交量：XXXXXX

✅ 通过 - 实时行情
```

或者（非交易时间）：
```
测试 4: 获取实时行情（5 分钟 K 线）
============================================================
⚠️  今日无实时数据（非交易时间）
   将使用最近一天的日线数据

✅ 最近交易日数据:
   日期：2026-03-XX
   收盘价：XX.XX
   涨跌幅：X.XX%

✅ 通过 - 实时行情
```

---

## 📝 相关知识

### WinError 10038 错误含义

**错误名称：** WSAENOTSOCK  
**错误代码：** 10038  
**含义：** 尝试在一个不是套接字的对象上执行套接字操作。

**常见原因：**
1. ❌ 重复关闭已关闭的 Socket
2. ❌ 在未初始化的 Socket 上操作
3. ❌ 使用已过期的 Socket 引用

### BaoStock 连接管理

```python
# 正确的使用方式
lg = bs.login()          # 建立连接
# ... 执行查询 ...
bs.logout()              # 关闭连接（只能调用一次）

# 错误的使用方式
lg = bs.login()
bs.logout()              # 关闭连接
bs.logout()              # ❌ 再次关闭 → WinError 10038
```

---

## 🎯 总结

### 核心要点

1. ✅ **每个测试函数只调用一次 `logout()`**
2. ✅ **在函数结束前调用 `logout()`**
3. ✅ **所有分支路径都要覆盖**
4. ✅ **异常处理中也要调用 `logout()`**

### 修复效果

- ✅ 消除 WinError 10038 错误
- ✅ 确保连接正确释放
- ✅ 提高代码健壮性
- ✅ 避免资源泄漏

---

*修复日期：2026-03-19*  
*版本：v1.3.5*
