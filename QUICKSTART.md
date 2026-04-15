# ETF链接基金T+0马丁格尔量化交易系统 - 快速启动指南

## 🚀 快速开始（3步启动）

### 第1步：安装依赖

```bash
pip install -r requirements.txt
```

### 第2步：测试系统

```bash
python test_etf_system.py
```

如果看到类似以下输出，说明系统正常：
```
✓ 上证指数: 3985.32
✓ 港股创新药ETF广发 (sh.513120)
  当前价格: 12.710
  涨跌幅: -0.86%
✓ 中概互联网ETF易方达 (sh.513050)
  当前价格: 11.850
  涨跌幅: -1.90%
```

**注意**：如果遇到502错误，可能是东方财富API临时故障，请稍后重试。

### 第3步：启动服务

```bash
python main.py
```

服务将在 `http://localhost:8080` 启动。

## 📊 访问API文档

打开浏览器访问：
- **API文档**: http://localhost:8080/docs
- **健康检查**: http://localhost:8080/api/health
- **所有信号**: http://localhost:8080/api/signals
- **持仓信息**: http://localhost:8080/api/positions

## 🔧 配置调整

编辑 `config.yaml` 文件，根据您的风险偏好调整参数：

### 保守型配置（适合新手）
```yaml
initial_capital: 500000  # 初始资金50万

strategy:
  initial_position_pct: 5      # 初始仓位5%（更保守）
  max_add_positions: 3         # 最多加仓3次
  add_position_multiplier: 1.5 # 加仓倍数1.5倍
  add_drop_threshold: 8        # 下跌8%才加仓
  take_profit_threshold: 5     # 上涨5%止盈
```

### 激进型配置（适合有经验者）
```yaml
initial_capital: 500000

strategy:
  initial_position_pct: 15     # 初始仓位15%
  max_add_positions: 5         # 最多加仓5次
  add_position_multiplier: 2.5 # 加仓倍数2.5倍
  add_drop_threshold: 3        # 下跌3%就加仓
  take_profit_threshold: 2     # 上涨2%快速止盈
```

## 💡 使用示例

### 1. 查看实时交易信号

```bash
curl http://localhost:8080/api/signals
```

返回示例：
```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "symbol": "sh.513120",
      "name": "港股创新药ETF",
      "signal_type": "BUY",
      "price": 12.710,
      "change_pct": -0.86,
      "reason": "初始建仓：买入3934份，成本12.710元/份",
      "target_shares": 3934
    }
  ]
}
```

### 2. 查看单个ETF信号

```bash
curl http://localhost:8080/api/signal/sh.513120
```

### 3. 查看持仓状态

```bash
curl http://localhost:8080/api/positions
```

### 4. 重置持仓（重新开始策略）

```bash
curl -X POST http://localhost:8080/api/position/sh.513120/reset
```

## ⚠️ 常见问题

### Q1: 遇到502错误怎么办？

A: 这是东方财富API的临时故障，可以：
1. 等待几分钟后重试
2. 检查网络连接
3. 系统已内置重试机制，会自动重试3次

### Q2: 如何确认ETF支持T+0？

A: 这两个ETF都支持T+0：
- **sh.513120** (港股创新药ETF): 跨境ETF，支持T+0
- **sh.513050** (中概互联网ETF): 跨境ETF，支持T+0

您可以在券商软件中验证：当天买入后可以当天卖出。

### Q3: 策略什么时候会发出BUY信号？

A: 当满足以下条件时：
- 通过大盘环境过滤（上证指数在2800-4500之间）
- RSI < 40（超卖区域）或价格接近日内低点
- 当前无持仓

### Q4: 如何监控策略运行？

A: 有以下几种方式：
1. **API接口**: 定期调用 `/api/signals` 查看信号
2. **日志文件**: 查看控制台输出的日志
3. **Web界面**: 访问 `/docs` 查看交互式API文档

### Q5: 实盘交易需要注意什么？

A: 
1. **先用模拟盘测试**: 建议先用小资金测试1-2周
2. **设置止损**: 严格执行止损纪律
3. **控制仓位**: 不要一次性投入全部资金
4. **监控网络**: 确保API服务稳定运行
5. **记录交易日志**: 便于后续分析和优化

## 📈 策略原理图解

```
价格走势图：

     /\          SELL (止盈)
    /  \        /
   /    \______/
  /            \
BUY            ADD1    ADD2
 |              |       |
 v              v       v
10%仓位      +20%    +40%
             (累计30%) (累计70%)

关键参数：
- 加仓阈值: 每跌5%加仓一次
- 加仓倍数: 每次是上一次的2倍
- 止盈目标: 平均成本上涨3%全部卖出
```

## 🎯 下一步

1. **阅读完整文档**: 查看 README.md 了解详细说明
2. **模拟测试**: 用历史数据回测策略效果
3. **小资金实盘**: 用少量资金验证策略
4. **参数优化**: 根据实际效果调整参数
5. **风险控制**: 设置每日最大亏损限额

## 📞 技术支持

如遇到问题：
1. 检查日志输出
2. 查看API返回的错误信息
3. 确认网络连接正常
4. 验证配置文件格式正确

---

**免责声明**: 本系统仅供学习和研究使用，不构成投资建议。使用本系统进行实盘交易的风险由用户自行承担。
