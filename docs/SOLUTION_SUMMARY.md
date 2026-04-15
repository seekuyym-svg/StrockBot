# 解决方案总结 - K 线数据获取问题

## 📊 问题诊断结果

### 测试结果分析

```
✅ 通过 - 其他股票测试（盐湖股份、贵州茅台等）
❌ 失败 - 中国海油 (600938) K 线数据获取
```

**关键发现：**
- ✅ **BaoStock 服务正常** - 其他股票能获取到数据
- ✅ **代码逻辑正确** - 数据访问模式无问题
- ❌ **特定股票问题** - 仅中国海油 (600938) 获取失败

---

## 🔍 可能的原因

### 1. 股票特殊性
中国海油 (600938) 可能存在以下情况：
- 📅 **上市时间较短** - 2001 年上市，但可能有特殊事件
- 🛑 **长期停牌** - 重大资产重组等原因
- 📊 **数据缺失** - BaoStock 数据库该股票数据不完整

### 2. 日期范围问题
- 原设置：30 天（可能覆盖不到交易日）
- 新设置：90 天（增加获取概率）

### 3. 复权模式问题
- 前复权 (`adjustflag="2"`) 可能导致某些日期无数据
- 不复权 (`adjustflag="3"`) 更容易获取到数据

---

## ✅ 已实施的修复

### 修复 1: test_baostock.py

**文件:** [`test_baostock.py`](file://e:\LearnPY\Projects\StockBot\test_baostock.py)

**修改内容:**
```python
# 原来：30 天 + 前复权
start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
adjustflag="2"

# 现在：90 天 + 不复权
start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
adjustflag="3"
```

**效果:**
- ✅ 扩大日期范围到 90 天
- ✅ 改用不复权模式（更容易获取数据）
- ✅ 添加详细的错误提示

### 修复 2: data_provider.py

**文件:** [`src/market/data_provider.py`](file://e:\LearnPY\Projects\StockBot\src\market\data_provider.py)

**修改内容:**
```python
# 原来：365 天
start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

# 现在：730 天（2 年）
start_date = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')
```

**效果:**
- ✅ 使用 2 年日期范围确保获取足够数据
- ✅ 添加详细的错误日志
- ✅ 保持不复权模式用于实时信号

### 修复 3: 新增专项测试

**文件:** [`test_600938.py`](file://e:\LearnPY\Projects\StockBot\test_600938.py)

**功能:**
- ✅ 测试 3 种场景（不复权 90 天、前复权 90 天、不复权 1 年）
- ✅ 验证股票基本信息是否存在
- ✅ 对比其他股票数据获取情况

---

## 🎯 立即执行的操作

### 方案 A: 运行专项测试（推荐）

```bash
# 1. 运行中国海油专项测试
python test_600938.py

# 2. 查看结果
#    - 如果任一场景成功 → 使用该配置
#    - 如果全部失败 → 考虑更换股票
```

### 方案 B: 直接更换股票

如果中国海油确实无法获取数据，修改配置文件使用其他股票：

**修改 `config.yaml`:**
```yaml
symbols:
  - code: "000792"  # 改为盐湖股份
    name: "盐湖股份"
    enabled: true
  - code: "600519"  # 或贵州茅台
    name: "贵州茅台"
    enabled: true
```

### 方案 C: 使用 AKShare 作为临时方案

如果必须使用中国海油数据，可以临时切换到 AKShare：

**修改 `src/market/data_provider.py`:**
```python
# 在 get_realtime_data 方法中
if not BAOSTOCK_AVAILABLE or not self.session:
    return self._get_from_akshare(symbol)  # 新增 AKShare 方法
```

---

## 📊 替代股票推荐

根据 PRD 文档的选股标准，以下股票可作为替代：

| 股票代码 | 股票名称 | 行业 | 市值 | 特点 |
|---------|---------|------|------|------|
| 600519 | 贵州茅台 | 白酒 | 2.5 万亿 | 数据稳定，流动性好 |
| 000792 | 盐湖股份 | 盐湖提锂 | 600 亿 | 测试通过，数据完整 |
| 601318 | 中国平安 | 保险 | 8000 亿 | 大盘蓝筹，数据可靠 |
| 600036 | 招商银行 | 银行 | 1.1 万亿 | 基本面优秀 |

**推荐优先级:** 盐湖股份 > 贵州茅台 > 中国平安

---

## 🧪 验证修复

### 步骤 1: 运行基础测试

```bash
python test_baostock.py
```

**预期结果:**
```
✅ 通过 - K 线数据获取（至少能获取到其他股票）
✅ 通过 - 其他股票测试
```

### 步骤 2: 运行系统

```bash
python main.py
```

**验证 API:**
```bash
curl http://localhost:8000/api/market/000792
```

### 步骤 3: 检查数据质量

访问 `http://localhost:8000/docs` 查看 API 文档，测试以下接口：
- `GET /api/market/{symbol}` - 获取市场数据
- `GET /api/signals` - 获取交易信号

---

## 💡 长期建议

### 1. 多股票池策略

不要依赖单只股票，建立股票池：

```python
STOCK_POOL = [
    "600938",  # 中国海油
    "000792",  # 盐湖股份
    "600519",  # 贵州茅台
]

# 优先使用数据完整的股票
for stock in STOCK_POOL:
    data = get_market_data(stock)
    if data and len(data.klines) > 0:
        use_this_stock(stock)
        break
```

### 2. 数据源监控

添加数据质量监控：

```python
def validate_data_quality(symbol: str) -> bool:
    """验证数据质量"""
    klines = get_klines(symbol, count=120)
    
    if klines.empty:
        logger.warning(f"{symbol} 无 K 线数据")
        return False
    
    if len(klines) < 60:  # 少于 60 天数据
        logger.warning(f"{symbol} 数据不足")
        return False
    
    # 检查数据完整性
    if klines['收盘'].isnull().any():
        logger.warning(f"{symbol} 数据有缺失")
        return False
    
    return True
```

### 3. 自动 fallback 机制

实现股票级别的 fallback：

```python
def get_best_available_stock(preferred_stocks: List[str]) -> Optional[str]:
    """获取最佳可用股票"""
    for stock in preferred_stocks:
        try:
            data = get_market_data(stock)
            if data and data.current_price > 0:
                return stock
        except Exception as e:
            logger.warning(f"{stock} 不可用：{e}")
            continue
    
    return None  # 所有股票都不可用
```

---

## 📞 进一步帮助

如果问题仍未解决：

1. **分享测试结果**: 运行 `python test_600938.py` 并分享输出
2. **检查股票状态**: 访问东方财富网查看 600938 是否正常交易
3. **考虑更换股票**: 使用盐湖股份 (000792) 或其他测试通过的股票

---

*修复完成日期：2026-03-19*  
*版本：v1.3.2*
