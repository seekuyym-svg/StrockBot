# ETF与上证指数相关系数计算工具使用说明

## 📋 功能说明

本工具用于计算指定ETF与上证指数（000001.SS）的相关系数，帮助投资者了解ETF与大盘的联动性，为马丁格尔策略参数调整提供数据支持。

### 核心功能

1. ✅ 获取ETF历史K线数据（默认121天）
2. ✅ 获取上证指数历史K线数据
3. ✅ 计算日对数收益率
4. ✅ 计算整体皮尔逊相关系数
5. ✅ 计算滚动相关系数（60日、120日）
6. ✅ 生成详细分析报告

---

## 🚀 快速开始

### 基本用法

```bash
python calculate_correlation.py
```

运行后会输出：
- 每个ETF的整体相关系数
- 60日和120日滚动相关系数
- 相关性解读和建议
- 两个ETF的对比分析

### 输出示例

```
============================================================
📊 相关系数分析报告
============================================================

📌 港股创新药ETF (513120)
   数据点数: 122个交易日
   整体相关系数: 0.5590
   相关程度: 中度正相关 🟡
   60日滚动相关: 0.6018
   120日滚动相关: 0.5603

📌 中概互联网ETF (513050)
   数据点数: 122个交易日
   整体相关系数: 0.6676
   相关程度: 中度正相关 🟡
   60日滚动相关: 0.6096
   120日滚动相关: 0.6693

💡 对比总结
按相关系数从高到低排序：
  1. 中概互联网ETF: 0.6676
  2. 港股创新药ETF: 0.5590

结论:
  • 中概互联网ETF 与上证指数相关性最高（0.6676）
  • 港股创新药ETF 与上证指数相关性最低（0.5590）
```

---

## ⚙️ 自定义配置

### 修改分析的ETF

编辑 `calculate_correlation.py` 文件中的 `main()` 函数：

```python
def main():
    # 定义要分析的ETF列表
    etfs = [
        {"code": "513120", "name": "港股创新药ETF"},
        {"code": "513050", "name": "中概互联网ETF"},
        # 添加更多ETF...
        {"code": "510300", "name": "沪深300ETF"},
        {"code": "510500", "name": "中证500ETF"},
    ]
    
    # ... 其余代码保持不变
```

### 修改数据周期

在 `analyze_etf()` 调用时修改 `days` 参数：

```python
result = calculator.analyze_etf(
    etf_code=etf["code"],
    etf_name=etf["name"],
    days=250  # 改为250天（约1年）
)
```

### 修改滚动窗口

在 `calculate_correlation()` 调用时修改窗口大小：

```python
# 计算30日滚动相关性
rolling_30d = self.calculate_correlation(merged_df.copy(), window=30)

# 计算180日滚动相关性
rolling_180d = self.calculate_correlation(merged_df.copy(), window=180)
```

---

## 📊 结果解读

### 相关系数范围与含义

| 相关系数 | 含义 | 投资策略 |
|---------|------|---------|
| 0.7 ~ 1.0 | 高度正相关 🔴 | 紧密跟随大盘，β值高，系统性风险大 |
| 0.3 ~ 0.7 | 中度正相关 🟡 | 正常水平，有一定独立性 |
| -0.3 ~ 0.3 | 弱相关 ⚪ | 独立走势，分散效果好 |
| -0.7 ~ -0.3 | 中度负相关 🔵 | 与大盘反向，罕见 |
| -1.0 ~ -0.7 | 高度负相关 🔵 | 完全反向，极罕见 |

### 滚动相关性的意义

- **短期窗口（30-60日）**: 反映近期市场情绪和资金流向
- **中期窗口（120-180日）**: 反映中期趋势和结构性变化
- **长期窗口（250日以上）**: 反映基本面和长期关联性

**判断标准**:
- 短期 > 长期：近期同步性增强，可能受共同因素驱动
- 短期 < 长期：近期出现背离，可能有独立行情
- 波动大：相关性不稳定，需要更频繁监控

---

## 💡 应用场景

### 场景 1: 马丁格尔策略参数优化

根据相关性调整加仓阈值：

```yaml
# 高相关性ETF（>0.7）：更稳健
add_drop_threshold: 4.0  # 更大的加仓间隔
take_profit_threshold: 3.0  # 追求更高收益

# 中等相关性ETF（0.3-0.7）：平衡
add_drop_threshold: 3.0
take_profit_threshold: 2.0

# 低相关性ETF（<0.3）：更激进
add_drop_threshold: 2.0  # 更小的加仓间隔
take_profit_threshold: 1.5  # 快速止盈
```

### 场景 2: 组合分散效果评估

- **理想情况**: 组合内ETF相关性差异 > 0.2
- **一般情况**: 相关性差异 0.1-0.2
- **需调整**: 相关性差异 < 0.1，分散效果有限

### 场景 3: 系统性风险预警

当多个ETF的相关性同时显著上升时：
- 可能预示系统性风险来临
- 建议降低总仓位或暂停加仓
- 关注宏观经济和政策变化

---

## 🔧 技术细节

### 数据源

- **API**: 腾讯财经 (`web.ifzq.gtimg.cn`)
- **数据类型**: 前复权日K线
- **更新频率**: 交易日每日更新

### 计算方法

1. **对数收益率**:
   ```python
   ret_t = ln(Close_t / Close_{t-1})
   ```

2. **皮尔逊相关系数**:
   ```python
   r = corr(ret_etf, ret_index)
   ```

3. **滚动窗口**:
   ```python
   rolling_corr = ret_etf.rolling(window).corr(ret_index)
   ```

### 注意事项

⚠️ **停牌处理**: 自动剔除停牌日，只保留共同交易日  
⚠️ **缺失值**: 使用 `dropna()` 删除缺失数据  
⚠️ **数据对齐**: 以日期为键进行内连接（inner join）  
⚠️ **样本量**: 至少需要30个有效数据点才能计算  

---

## 🐛 常见问题

### Q1: 为什么获取数据失败？

**可能原因**:
- 网络连接问题
- 腾讯财经API临时不可用
- ETF代码错误

**解决方法**:
- 检查网络连接
- 重试几次（脚本会自动重试）
- 确认ETF代码格式正确（6位数字）

### Q2: 相关系数为 NaN 怎么办？

**可能原因**:
- 数据量不足（少于2个交易日）
- 所有收益率都为0（极端情况）

**解决方法**:
- 增加 `days` 参数，获取更多历史数据
- 检查数据源是否正常

### Q3: 滚动相关性波动很大正常吗？

**正常**。滚动相关性会随市场环境和资金流向变化而波动。

**建议**:
- 关注长期趋势，而非单日数值
- 结合多个窗口（60日、120日、250日）综合判断
- 如果波动异常大，检查是否有异常交易日

### Q4: 可以计算与其他指数的相关性吗？

可以！修改 `get_sh_index_klines()` 方法，传入不同的指数代码：

```python
# 恒生指数
params = {"param": f"hsi,day,,,{days},qfq"}

# 纳斯达克指数
params = {"param": f"us.IXIC,day,,,{days},qfq"}
```

注意：不同指数的代码格式可能不同，需要查阅腾讯财经API文档。

---

## 📈 进阶用法

### 批量分析多个ETF

创建批处理脚本 `batch_correlation.py`:

```python
from calculate_correlation import CorrelationCalculator

# 定义ETF列表
etfs = [
    ("513120", "港股创新药ETF"),
    ("513050", "中概互联网ETF"),
    ("510300", "沪深300ETF"),
    ("510500", "中证500ETF"),
    ("512880", "证券ETF"),
]

calculator = CorrelationCalculator()
results = []

for code, name in etfs:
    result = calculator.analyze_etf(code, name, days=121)
    results.append(result)

calculator.generate_report(results)
```

### 保存结果为CSV

在 `CorrelationCalculator` 类中添加方法：

```python
def save_to_csv(self, results: list, filename: str = "correlation_results.csv"):
    """保存结果为CSV文件"""
    import csv
    
    with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['ETF名称', '代码', '整体相关性', '60日滚动', '120日滚动'])
        
        for result in results:
            if result is None:
                continue
            
            writer.writerow([
                result['etf_name'],
                result['etf_code'],
                f"{result['overall_correlation']:.4f}",
                f"{result['rolling_60d']['corr_60d'].iloc[-1]:.4f}" if result['rolling_60d'] is not None else "N/A",
                f"{result['rolling_120d']['corr_120d'].iloc[-1]:.4f}" if result['rolling_120d'] is not None else "N/A",
            ])
    
    logger.info(f"✓ 结果已保存到 {filename}")
```

### 可视化相关性趋势

使用 matplotlib 绘制滚动相关性曲线：

```python
import matplotlib.pyplot as plt

def plot_rolling_correlation(self, result: dict):
    """绘制滚动相关性曲线"""
    if result['rolling_60d'] is None:
        return
    
    plt.figure(figsize=(12, 6))
    plt.plot(result['rolling_60d']['date'], 
             result['rolling_60d']['corr_60d'], 
             label='60日滚动相关')
    plt.plot(result['rolling_120d']['date'], 
             result['rolling_120d']['corr_120d'], 
             label='120日滚动相关')
    plt.axhline(y=result['overall_correlation'], 
                color='r', linestyle='--', 
                label=f"整体相关 ({result['overall_correlation']:.2f})")
    
    plt.title(f"{result['etf_name']} 滚动相关性")
    plt.xlabel('日期')
    plt.ylabel('相关系数')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(f"{result['etf_code']}_correlation.png", dpi=150)
    plt.show()
```

---

## 📚 相关文档

- **详细分析报告**: [CORRELATION_ANALYSIS_REPORT.md](CORRELATION_ANALYSIS_REPORT.md)
- **相关系数理论**: [relation.md](relation.md)
- **马丁格尔策略**: [README.md](README.md)

---

## 🔄 更新日志

### v1.0.0 (2026-04-15)
- ✅ 初始版本发布
- ✅ 支持整体和相关系数计算
- ✅ 支持60日和120日滚动相关性
- ✅ 自动生成分析报告
- ✅ 支持多个ETF对比分析

---

## 💬 反馈与支持

如有问题或建议，请：
1. 检查本文档的"常见问题"部分
2. 查看日志输出中的错误信息
3. 联系项目维护者

---

**祝投资顺利！** 🚀
