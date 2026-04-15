# Tushare Pro 数据源配置指南

## 📋 目录
- [为什么选择 Tushare Pro](#为什么选择-tushare-pro)
- [快速开始](#快速开始)
- [配置方法](#配置方法)
- [常见问题](#常见问题)
- [积分说明](#积分说明)

---

## 🎯 为什么选择 Tushare Pro

### AKShare vs Tushare Pro 对比

| 特性 | AKShare（原方案） | Tushare Pro（新方案） |
|------|------------------|---------------------|
| **稳定性** | ⭐⭐ 接口经常变更 | ⭐⭐⭐⭐⭐ 专业维护 |
| **实时性** | ⭐⭐ 延迟较大 | ⭐⭐⭐⭐ 准实时 |
| **数据质量** | ⭐⭐⭐ 一般 | ⭐⭐⭐⭐⭐ 机构级 |
| **技术支持** | ❌ 社区支持 | ✅ 官方支持 |
| **费用** | ✅ 完全免费 | ✅ 基础免费 |
| **使用门槛** | ✅ 无门槛 | ⚠️ 需注册 token |

### 解决的问题
1. ✅ **数据准确性提升** - 消除价格、成交量等数据错误
2. ✅ **实时性增强** - 减少延迟，提高交易信号时效性
3. ✅ **接口稳定性** - 避免因接口变更导致的系统故障
4. ✅ **丰富的数据** - 支持资金流向、基本面等更多维度

---

## 🚀 快速开始

### 步骤 1: 注册 Tushare 账号

1. 访问官网：https://tushare.pro/
2. 点击右上角"注册"
3. 填写邮箱、密码完成注册

### 步骤 2: 获取 API Token

1. 登录后进入"个人中心"
2. 在"接口 TOKEN"标签页复制你的 token
3. 格式类似：`a1b2c3d4e5f6g7h8i9j0...`

### 步骤 3: 安装依赖

```bash
pip install tushare
```

或安装完整依赖：

```bash
pip install -r requirements.txt
```

### 步骤 4: 配置 Token（三选一）

#### 方法一：环境变量（推荐）

**Windows PowerShell:**
```powershell
$env:TUSHARE_TOKEN="your_token_here"
```

**Windows CMD (永久):**
```cmd
setx TUSHARE_TOKEN "your_token_here"
```

**Linux/Mac:**
```bash
export TUSHARE_TOKEN="your_token_here"
```

#### 方法二：修改代码

编辑 `src/market/data_provider.py`:

```python
def __init__(self):
    self.config = get_config()
    self.api = None
    
    if TUSHARE_AVAILABLE:
        # 直接在这里填写你的 token
        token = "your_token_here"  # 替换为你的 token
        if token and token != 'your_token_here':
            ts.set_token(token)
            self.api = ts.pro_api()
            logger.info("Tushare Pro 初始化成功")
```

#### 方法三：配置文件

编辑 `config.yaml`:

```yaml
data_source:
  tushare:
    enabled: true
    token: "your_token_here"
```

---

## 🔧 验证安装

创建测试脚本 `test_tushare.py`:

```python
import tushare as ts
from datetime import datetime, timedelta

# 设置 token
ts.set_token('your_token_here')

# 初始化 API
pro = ts.pro_api()

# 测试 1: 获取股票基本信息
print("=" * 50)
print("测试 1: 获取贵州茅台基本信息")
df = pro.stock_basic(ts_code='600519.SH', fields='ts_code,name,industry,list_date')
print(df)

# 测试 2: 获取日 K 线
print("\n" + "=" * 50)
print("测试 2: 获取贵州茅台最近 30 天 K 线")
end_date = datetime.now().strftime('%Y%m%d')
start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
df = pro.daily(ts_code='600519.SH', start_date=start_date, end_date=end_date)
print(df[['trade_date', 'open', 'high', 'low', 'close', 'vol']])

# 测试 3: 获取上证指数
print("\n" + "=" * 50)
print("测试 3: 获取上证指数")
df = pro.index_daily(ts_code='000001.SH', start_date=start_date, end_date=end_date)
print(df[['trade_date', 'close']].tail())

# 测试 4: 获取资金流向
print("\n" + "=" * 50)
print("测试 4: 获取贵州茅台资金流向")
df = pro.moneyflow(ts_code='600519.SH', start_date=start_date, end_date=end_date)
print(df[['trade_date', 'buy_sm_amount', 'sell_sm_amount', 'buy_md_amount', 'sell_md_amount']].tail())

print("\n✅ 所有测试完成！")
```

运行测试：
```bash
python test_tushare.py
```

---

## 💰 积分说明

### 新手福利
- **注册即送**: 120 积分/天
- **绑定手机**: +20 积分
- **完善资料**: +20 积分
- **每日签到**: +5~20 积分

### 基础数据消耗

| 接口 | 消耗积分 | 说明 |
|------|---------|------|
| `daily` (日 K 线) | 1 积分/次 | 每天调用 1 次足够 |
| `quote_daily` (实时行情) | 1 积分/次 | 按需调用 |
| `index_daily` (指数) | 1 积分/次 | 获取大盘指数 |
| `moneyflow` (资金流) | 5 积分/次 | 可选调用 |
| `stock_basic` (股票信息) | 1 积分/次 | 偶尔调用 |

### 积分优化策略

本项目日均消耗：**约 20-40 积分/天**

优化建议：
1. ✅ 缓存历史 K 线数据（减少重复调用）
2. ✅ 只在交易时间获取实时数据
3. ✅ 批量获取多只股票数据
4. ✅ 利用本地缓存避免重复请求

### 提升积分

如需更多积分，可以：
1. 充值赞助（推荐 99 元/年，享 5000 积分）
2. 邀请好友注册
3. 参与社区贡献

---

## ❓ 常见问题

### Q1: Token 安全吗？
**A:** Token 是你的身份凭证，请妥善保管：
- ✅ 不要提交到 Git 仓库
- ✅ 使用环境变量存储
- ✅ 不要在公开场合分享

### Q2: 积分不够用怎么办？
**A:** 
- 新手期 120 积分/天足够个人使用
- 如果不够，可以优化调用频率
- 或考虑充值（99 元/年性价比最高）

### Q3: 数据更新频率？
**A:**
- 日 K 线：每个交易日 17:30 后更新当日数据
- 实时行情：交易时间每 3 秒刷新
- 资金流向：交易时间实时更新

### Q4: 非交易时间有数据吗？
**A:**
- 非交易时间获取的是最近一个交易日的数据
- 建议在交易时间（9:30-15:00）获取实时数据

### Q5: Tushare 和 AKShare 能同时用吗？
**A:** 
- ✅ 可以同时安装
- ✅ 代码已实现自动 fallback 机制
- ✅ Tushare 不可用时会自动切换到 AKShare 或模拟数据

---

## 🔍 故障排查

### 问题 1: 提示"未配置 TUSHARE_TOKEN"
**解决:**
```bash
# 检查环境变量
echo $env:TUSHARE_TOKEN  # Windows PowerShell
echo $TUSHARE_TOKEN      # Linux/Mac

# 如果没有输出，说明未配置，请按上述方法配置
```

### 问题 2: 提示"积分不足"
**解决:**
1. 登录 tushare.pro 查看剩余积分
2. 减少不必要的调用
3. 考虑充值或签到获取积分

### 问题 3: 数据获取失败
**解决:**
```python
# 添加错误日志
try:
    df = pro.daily(ts_code='600938.SH')
except Exception as e:
    print(f"错误：{e}")
    # 检查网络连接
    # 检查 token 是否正确
    # 检查积分是否充足
```

---

## 📞 技术支持

- **官方文档**: https://tushare.pro/document/2
- **官方 QQ 群**: 加入用户群获取帮助
- **GitHub Issues**: 项目相关问题可提 issue

---

## 🎉 配置完成

完成上述配置后，系统将自动使用 Tushare Pro 作为数据源：

```bash
# 启动项目
python main.py

# 访问 API
curl http://localhost:8000/api/v1/signals/600938
```

**祝你投资顺利！** 📈
