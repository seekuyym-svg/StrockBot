# Bug 修复 - Pandas 变量作用域错误

## 🐛 问题描述

运行测试 4（获取实时行情）时报错：
```
今日无实时数据（非交易时间）
将使用最近一天的日线数据
❌ 错误：cannot access local variable 'pd' where it is not associated with a value
```

## 🔍 问题原因

`import pandas as pd` 被放在了 **if 分支内部**，导致当代码进入 else 分支时，`pd` 变量未定义。

### 错误示例

```python
def test_realtime_quote():
    try:
        import baostock as bs
        
        # ... 业务逻辑 ...
        
        if data_list:
            import pandas as pd  # ❌ 只在 if 分支内有效
            df = pd.DataFrame(data_list, columns=rs.fields)
            # ...
            return True
        else:
            # 进入 else 分支
            rs2 = bs.query_history_k_data_plus(...)
            data_list2 = []
            while rs2.next():
                data_list2.append(rs2.get_row_data())
            
            if data_list2:
                df = pd.DataFrame(data_list2, columns=rs2.fields)  # ❌ pd 未定义！
                # ...
```

### Python 变量作用域规则

在 Python 中，**import 语句也是赋值操作**，遵循局部作用域规则：

```python
def func():
    if condition:
        x = 10  # x 只在 if 块内定义
    else:
        print(x)  # ❌ NameError: name 'x' is not defined
```

---

## ✅ 修复方案

### 核心原则

**将所有 `import` 语句移到函数开头或 try 块开头**，确保整个函数都能访问。

### 修复后的代码结构

```python
def test_realtime_quote():
    """测试 4: 获取实时行情"""
    print("\n" + "=" * 60)
    print("测试 4: 获取实时行情（5 分钟 K 线）")
    print("=" * 60)
    
    try:
        import baostock as bs
        import pandas as pd  # ✅ 移到函数开头，所有分支都能访问
        
        lg = bs.login()
        if lg.error_code != '0':
            return False
        
        # 场景 1: 获取 5 分钟 K 线
        rs = bs.query_history_k_data_plus(...)
        data_list = []
        while rs.next():
            data_list.append(rs.get_row_data())
        
        if data_list:
            df = pd.DataFrame(data_list, columns=rs.fields)  # ✅ pd 可用
            # ...
            bs.logout()
            return True
        else:
            # 场景 2: 获取日线数据
            rs2 = bs.query_history_k_data_plus(...)
            data_list2 = []
            while rs2.next():
                data_list2.append(rs2.get_row_data())
            
            if data_list2:
                df = pd.DataFrame(data_list2, columns=rs2.fields)  # ✅ pd 可用
                # ...
                bs.logout()
                return True
            else:
                bs.logout()
                return False
    
    except Exception as e:
        return False
```

---

## 📊 已修复的文件和函数

### test_baostock.py

**修复位置：** 3 个测试函数

#### 1. test_klines() (第 93 行)

**修改前：**
```python
def test_klines():
    try:
        import baostock as bs
        # ...
        if data_list:
            import pandas as pd  # ❌ 在 if 内部
```

**修改后：**
```python
def test_klines():
    try:
        import baostock as bs
        import pandas as pd  # ✅ 移到 try 开头
        # ...
```

#### 2. test_realtime_quote() (第 160 行)

**修改前：**
```python
def test_realtime_quote():
    try:
        import baostock as bs
        # ...
        if data_list:
            import pandas as pd  # ❌ 在 if 内部
```

**修改后：**
```python
def test_realtime_quote():
    try:
        import baostock as bs
        import pandas as pd  # ✅ 移到 try 开头
        # ...
```

#### 3. test_sh_index() (第 240 行)

**修改前：**
```python
def test_sh_index():
    try:
        import baostock as bs
        # ...
        if data_list:
            import pandas as pd  # ❌ 在 if 内部
```

**修改后：**
```python
def test_sh_index():
    try:
        import baostock as bs
        import pandas as pd  # ✅ 移到 try 开头
        # ...
```

---

## 💡 Python Import 最佳实践

### 1. 模块级导入（推荐）

```python
# 文件开头
import pandas as pd
import numpy as np
import baostock as bs

def func1():
    # 直接使用
    df = pd.DataFrame()

def func2():
    # 也能使用
    df = pd.DataFrame()
```

### 2. 函数级导入（按需）

如果只在特定函数中使用，可以在函数内导入：

```python
def heavy_computation():
    import numpy as np  # 延迟导入，节省启动时间
    return np.array([1, 2, 3])
```

### 3. Try 块内导入（条件依赖）

当依赖是可选的时候：

```python
def optional_feature():
    try:
        import pandas as pd
        # 使用 pandas 处理数据
    except ImportError:
        print("pandas 未安装，使用备用方案")
```

**关键：** 必须确保在整个函数作用域内都能访问导入的模块。

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

### Python 作用域规则

Python 使用 **LEGB 规则** 查找变量：

1. **L**ocal - 当前函数/方法作用域
2. **E**nclosing - 外层函数作用域
3. **G**lobal - 模块级作用域
4. **B**uilt-in - 内置作用域

**Import 语句** 在当前作用域创建变量绑定：

```python
def func():
    if True:
        import pandas as pd  # pd 绑定在 func 的局部作用域
    print(pd)  # ✅ 可以访问（只要在 if 之后使用）
```

但如果 if 条件为 False，则 pd 不会被定义：

```python
def func():
    if False:
        import pandas as pd
    print(pd)  # ❌ NameError: name 'pd' is not defined
```

### 为什么会有这个错误？

```python
def func():
    condition = False
    
    if condition:
        import pandas as pd  # 这行不会执行
        print("In if branch")
    else:
        df = pd.DataFrame()  # ❌ pd 未定义！
```

当 `condition` 为 False 时，import 语句不会执行，导致 `pd` 变量不存在。

---

## 🎯 总结

### 核心要点

1. ✅ **Import 语句要放在函数/try 块开头**
2. ✅ **避免在 if/else 分支内部导入模块**
3. ✅ **确保所有代码路径都能访问导入的模块**
4. ✅ **遵循 Python 作用域规则**

### 修复效果

- ✅ 消除 "cannot access local variable" 错误
- ✅ 确保所有分支都能正确使用 pandas
- ✅ 提高代码可读性和可维护性
- ✅ 符合 Python 最佳实践

---

*修复日期：2026-03-19*  
*版本：v1.3.6*
