# 🚀 新对话快速启动指南

**适用场景**：开启新对话后，快速继续回测策略优化工作

**最后更新**：2026-06-02 18:30

---

## 📋 当前状态（2026-06-02最新修复）

### ✅ **已完成的工作**

#### 1. 换手率评分规则优化 - 新版双重条件评分系统 ⭐⭐⭐⭐⭐ 【NEWEST】
- **更新时间**：2026-06-02 18:30
- **文件**：[local/utils.py](file://e:\LearnPY\Projects\StockBot\local\utils.py)
- **问题**：旧版换手率评分仅基于累计值，无法识别每日波动过大的风险股票
- **解决方案**：实现新版双重条件评分规则，强调稳定性和合理性
- **核心改进**：
  - ✅ **去除负分机制**：最低得分为0分，避免过度惩罚
  - ✅ **双重条件控制**：同时要求"每日换手率稳定"和"累计换手率合理"
  - ✅ **排除极端情况**：单日>25%（过度活跃）或<2%（过于冷清）直接0分
  - ✅ **配置化支持**：天数从 [config.yaml](file://e:\LearnPY\Projects\StockBot\config.yaml) 的 `backtest.volume_period` 读取
  - ✅ **可配置最小数据长度**：新增 `min_data_length` 参数，解决历史日期截断导致的数据不足问题
- **新版评分规则**：
  | 得分 | 条件 | 说明 |
  |------|------|------|
  | **5分** | 每日换手率均在 5%~15% 且 3日累计 15%~45% | 优质活跃度 |
  | **3分** | 每日换手率均在 3%~20% 且 3日累计 12%~50% | 一般活跃度 |
  | **0分** | 任一日换手率 >25% 或 <2%，或其他不满足条件的情况 | 不活跃或异常 |
- **判断优先级**：
  ```python
  # 1. 检查排除条件：任一日换手率 >25% 或 <2%
  if any(t > 25 or t < 2 for t in daily_turnovers):
      return 0
  
  # 2. 判断5分条件：每日均在 5%~15% 且 累计 15%~45%
  if all(5 <= t <= 15 for t in daily_turnovers) and 15 <= cumulative_turnover <= 45:
      return 5
  
  # 3. 判断3分条件：每日均在 3%~20% 且 累计 12%~50%
  if all(3 <= t <= 20 for t in daily_turnovers) and 12 <= cumulative_turnover <= 50:
      return 3
  
  # 4. 其他情况
  return 0
  ```
- **关键技术实现**：
  - **真实换手率计算**：`换手率 = 成交量 / 流通股本 × 100%`
  - **流通股本获取**：通过腾讯财经API字段[72]或[76]获取
  - **容错处理**：API失败时返回0分并输出警告，不中断主流程
  - **边界包含**：恰好等于阈值时按更高档位计分（如正好5%计为满足条件）
- **测试验证结果**：
  | 股票 | 每日换手率 | 累计换手率 | 评分 | 原因 |
  |------|-----------|-----------|------|------|
  | **良信股份** (sz002706) | [8.69%, 6.78%, 10.81%] | 26.28% | **5分** | ✅ 每日5%~15%，累计15%~45% |
  | **贵州茅台** (sh600519) | [0.61%, 0.35%, 0.29%] | 1.25% | **0分** | ❌ 单日<2%，触发排除条件 |
  | **金螳螂** (sz002081) | [13.75%, 23.96%, 26.71%] | 64.42% | **0分** | ❌ 单日>25%，触发排除条件 |
- **实施效果**：
  - ✅ 更精准选股：不仅关注活跃度，还要求稳定性
  - ✅ 降低风险：排除单日过度活跃或过于冷清的股票
  - ✅ 简化调优：3个等级比7个等级更容易理解和调整
  - ✅ 符合策略理念："宽粗筛，严评分"
- **使用方法**：
  ```bash
  # 运行股票池评分（自动应用新规则）
  python backtest/score_stockpool.py --date 2026-06-02
  
  # 批量评分
  python backtest/score_stockpool.py --start-date 2026-06-01 --end-date 2026-06-02
  ```
- **注意事项**：
  - 每只股票评分时需要调用一次腾讯API获取流通股本
  - 由于选股后股票数量不多，性能影响可接受
  - 如需调整累计换手率的天数，修改 [config.yaml](file://e:\LearnPY\Projects\StockBot\config.yaml) 中的 `backtest.volume_period` 值

#### 2. K线数据获取函数增强 - 支持可配置的最小数据长度 ⭐⭐⭐⭐⭐ 【NEWEST】
- **更新时间**：2026-06-02 18:20
- **文件**：[local/utils.py](file://e:\LearnPY\Projects\StockBot\local\utils.py)
- **问题**：[_get_historical_klines()](file://e:\LearnPY\Projects\StockBot\local\utils.py#L265-L318) 函数硬编码最小数据长度为60条，导致在回测历史日期时，如果截断后数据不足60条就返回空DataFrame
- **解决方案**：添加 `min_data_length` 参数，默认为60，但可以自定义
- **核心改进**：
  - ✅ **参数化最小数据长度**：所有K线获取函数支持 `min_data_length` 参数
  - ✅ **向后兼容**：默认值为60，不影响现有调用方
  - ✅ **灵活可控**：不同场景可以设置不同的最小数据量要求
  - ✅ **代码清晰**：参数命名明确，易于理解和维护
- **修改的函数**：
  - [_get_historical_klines()](file://e:\LearnPY\Projects\StockBot\local\utils.py#L265-L318)：添加 `min_data_length: int = 60` 参数
  - [_get_klines_from_local()](file://e:\LearnPY\Projects\StockBot\local\utils.py#L320-L431)：添加 `min_data_length: int = 60` 参数
  - [_get_klines_from_tencent()](file://e:\LearnPY\Projects\StockBot\local\utils.py#L498-L570)：添加 `min_data_length: int = 60` 参数
  - [calculate_cumulative_turnover_score()](file://e:\LearnPY\Projects\StockBot\local\utils.py#L109-L195)：从配置文件读取 `volume_period` 作为 `min_data_length`
- **使用示例**：
  ```python
  # 默认使用60条最小长度
  df = _get_historical_klines('sz', '002706', days=300)
  
  # 自定义最小长度为3条（用于换手率评分）
  df = _get_historical_klines('sz', '002706', days=10, min_data_length=3)
  ```
- **实施效果**：
  - ✅ 解决了回测历史日期时"K线数据不足（仅0条）"的问题
  - ✅ 提高了函数的灵活性和复用性
  - ✅ 符合项目规范中的"历史数据分析日期一致性规范"

#### 3. 回测引擎交易周期跳转逻辑修复 - 实现资金无缝衔接 ⭐⭐⭐⭐⭐
- **更新时间**：2026-05-05 01:00
- **文件**：[backtest/backtest_engine.py](file://e:\LearnPY\Projects\StockBot\backtest\backtest_engine.py)
- **问题**：回测工具在交易周期之间存在一个交易日的空档期
  - **错误逻辑**：卖出日后跳过一个交易日才进行下一轮选股
  - **正确设计**：卖出日应该同时作为下一周期的选股日
  - **影响**：资金闲置一个交易日，利用率降低，收益率失真
- **时间线对比**：
  ```
  修复前（错误）：
  周期1: T0(选股) → T1(买入) → T2 → T3(卖出)
         ↓ 跳过T3
  周期2: T4(选股) → T5(买入) → T6 → T7(卖出)
  
  修复后（正确）：
  周期1: T0(选股) → T1(买入) → T2 → T3(卖出+选股)
                                      ↓
  周期2: T3(已选股) → T4(买入) → T5 → T6(卖出+选股)
  ```
- **解决方案**：
  - ✅ **修复核心bug** - 修改 `run_backtest()` 方法中的跳转逻辑
    - 修改前：`i = sell_date_idx + 1`（跳到卖出日的下一个交易日）
    - 修改后：`i = sell_date_idx`（跳到卖出日，卖出日同时也是下一周期的选股日）
- **实施效果**：
  - ✅ 卖出当日立即作为下一周期的选股日
  - ✅ 资金无缝衔接，提高利用率
  - ✅ 符合项目规范中的"交易周期执行规范"
  - ✅ 与设计原则完全一致（注释中已明确说明）
- **验证要点**：
  - 查看"交易周期汇总"中的日期连续性
  - 确认卖出日和下一周期的选股日是否相同
  - 对比修复前后的交易周期数量和收益率
- **使用方法**：
  ```bash
  # 运行短期回测验证修复效果
  python backtest/run_backtest.py --start-date 2026-04-01 --end-date 2026-04-10
  ```
- **预期输出示例**：
  ```
  周期   选股日        买入日        卖出日        股票数  期初资金         期末资金         周期收益    
  --------------------------------------------------------------------------------
  1      2026-04-01   2026-04-02   2026-04-06   10     1,000,000.00   1,015,234.56   +1.52%     
  2      2026-04-06   2026-04-07   2026-04-10   10     1,015,234.56   1,028,456.78   +1.30%     
  ```
  注意：**周期1的卖出日（2026-04-06）= 周期2的选股日（2026-04-06）** ✅

#### 4. 回测引擎资金计算Bug修复 - 正确处理闲置资金 ⭐⭐⭐⭐⭐
- **更新时间**：2026-05-05 00:30
- **文件**：[backtest/backtest_engine.py](file://e:\LearnPY\Projects\StockBot\backtest\backtest_engine.py)、[backtest/run_backtest.py](file://e:\LearnPY\Projects\StockBot\backtest\run_backtest.py)
- **问题**：回测工具在计算交易周期期初资金和期末资金时存在严重bug
  - **错误假设**：将期初资金默认当作全部投入资金
  - **实际情况**：由于A股最小交易单位为100股，会有闲置资金未投入
  - **影响**：期末资金被低估，复利计算错误，收益率失真
- **四个资金概念的正确关系**：
  ```
  期初资金 = 本周期投入资金 + 本周期闲置资金
  期末资金 = 本周期投入资金 × (1 + 周期收益率) + 本周期闲置资金
  周期收益率 = (期末市值 - 实际投入) / 实际投入 × 100%
  ```
- **解决方案**：
  - ✅ **方案A：修复核心bug** - 修改 `_calculate_cycle_final_capital()` 方法
    - 正确计算每只股票的闲置资金：`idle_capital = capital_per_stock - investment`
    - 期末价值包含闲置资金：`final_value = investment * (1 + return_pct) + idle_capital`
  - ✅ **方案B：详细资金输出** - 增强 `calculate_cycle_metrics()` 方法
    - 新增字段：`total_investment`（实际投入）、`total_idle_capital`（闲置资金）
    - 新增字段：`capital_utilization`（资金利用率）、`skipped_stocks`（跳过股票数）
    - DEBUG日志输出详细的资金构成信息
  - ✅ **添加 --debug 参数** - 按需启用DEBUG日志
    - 默认模式：INFO级别，简洁清晰
    - DEBUG模式：显示详细的资金明细和调试信息
- **实施效果**：
  - ✅ 期末资金计算准确（包含闲置资金）
  - ✅ 收益率计算正确（基于实际投入资金）
  - ✅ 复利效应正确传递到下一周期
  - ✅ 提供详细的资金流水，便于审计和调试
  - ✅ 符合项目规范中的"资金使用原则"
- **使用方法**：
  ```bash
  # 默认模式（简洁）
  python backtest/run_backtest.py --start-date 2026-04-01 --end-date 2026-04-10
  
  # DEBUG模式（查看详细资金明细）
  python backtest/run_backtest.py --start-date 2026-04-01 --end-date 2026-04-10 --debug
  ```
- **验证要点**：
  - 闲置资金 > 0（除非恰好整除）
  - 资金利用率 < 100%（通常95%-99%）
  - 期末资金 ≈ 投入资金×(1+收益率) + 闲置资金
- **注意事项**：
  - 日志文件始终是DEBUG级别，无论是否使用--debug参数
  - --debug参数仅影响控制台输出，不影响日志文件
  - DEBUG模式会输出更多信息，可能略微降低执行速度（影响很小）

#### 5. 评分工具性能优化 - 本地数据源切换 ⭐⭐⭐⭐⭐
- **更新时间**：2026-05-04 23:15
- **文件**：[local/utils.py](file://e:\LearnPY\Projects\StockBot\local\utils.py)、[config.yaml](file://e:\LearnPY\Projects\StockBot\config.yaml)
- **问题**：评分工具每次从腾讯财经API获取数据，批量处理617只股票需要约15分钟，速度慢且依赖网络
- **解决方案**：切换到本地通达信数据源，实现5-10倍性能提升
- **核心改进**：
  - ✅ **配置化数据源切换**：通过 `use_local_data` 配置项控制
  - ✅ **数据更新日期检查**：超过7天未更新自动警告
  - ✅ **数据一致性验证**：可选功能，对比本地与腾讯API数据
  - ✅ **自动降级机制**：本地数据失败时自动切换到腾讯API
  - ✅ **前复权数据处理**：直接使用通达信本地数据（已是前复权）
- **性能提升**：
  - 单只股票：从1-2秒降至0.2-0.3秒
  - 617只股票：从15分钟降至3分钟
  - **总体提升**：5-10倍（节省80%时间）
- **数据一致性验证结果**：
  - 贵州茅台 (sh.600519)：差异 0.00% ✅
  - 平安银行 (sz.000001)：差异 0.00% ✅
  - 特力A (sz.000025)：差异 0.00% ✅
- **配置项**（config.yaml）：
  ```yaml
  backtest:
    use_local_data: true          # 是否使用本地数据（默认true）
    data_consistency_check: false # 是否启用一致性验证（首次使用建议true）
    max_data_age_days: 7          # 数据最大允许年龄（交易日）
  ```
- **测试工具**：
  - [backtest/test_data_source.py](file://e:\LearnPY\Projects\StockBot\backtest\test_data_source.py) - 数据一致性测试
  - [backtest/test_performance.py](file://e:\LearnPY\Projects\StockBot\backtest\test_performance.py) - 性能对比测试
- **重要发现**：
  - 通达信 `.day` 文件本身已是前复权数据，无需额外转换
  - mootdx 的 `to_adjust()` 函数在当前版本有bug，暂不使用
  - 本地数据与腾讯API完全一致，可以放心使用
- **使用方法**：
  ```bash
  # 正常使用（推荐）
  python backtest/score_stockpool.py --date 2026-01-13
  
  # 首次使用（验证数据一致性）
  # 修改 config.yaml: data_consistency_check: true
  
  # 测试数据一致性
  python backtest/test_data_source.py --code 600519 --market sh
  ```
- **注意事项**：
  - 定期更新通达信数据（打开通达信执行"盘后数据下载"）
  - 系统会在数据超过7天未更新时发出警告
  - 如需临时切换回腾讯API，设置 `use_local_data: false`

#### 6. 评分工具进度展示优化 ⭐⭐⭐⭐⭐
- **文件**：[score_stockpool.py](file://e:\LearnPY\Projects\StockBot\backtest\score_stockpool.py)
- **问题**：批量评分时无法实时看到进度，处理大量股票时需要等待很久才有反馈
- **解决方案**：添加实时进度展示功能
  - 使用 `\r` 实现单行动态刷新，避免刷屏
  - 每处理10只股票更新一次进度
  - 显示日期进度、股票进度、百分比、已耗时
- **效果**：用户可以清晰看到评分进度，提升用户体验
- **技术实现**：
  ```python
  # 每25只股票或最后一只时更新进度
  if stock_index % 25 == 0 or stock_index == len(stocks):
      elapsed = time.time() - day_start_time
      progress_pct = (stock_index / len(stocks)) * 100
      print(f"\r[{processed_count+1}/{total_days}] {date_str} | "
            f"股票 {stock_index}/{len(stocks)} ({progress_pct:.0f}%) | "
            f"已耗时: {elapsed:.0f}秒", end='', flush=True)
  ```
- **特性**：无额外依赖、保留原有日志、简洁直观

#### 7. 回测引擎非交易日过滤修复 ⭐⭐⭐⭐⭐
- **文件**：[backtest_engine.py](file://e:\LearnPY\Projects\StockBot\backtest\backtest_engine.py)
- **问题**：回测引擎的 `get_trading_days()` 方法仅过滤周末，未处理法定节假日，导致回测时出现日期跳跃
- **解决方案**：复用 [generate_stockpool.py](file://e:\LearnPY\Projects\StockBot\backtest\generate_stockpool.py) 中的 akshare 交易日历获取逻辑
- **效果**：回测时自动识别并过滤所有非交易日（周末+节假日），确保交易周期计算准确
- **降级机制**：API失败时自动降级为仅过滤周末
- **测试验证**：2026年4月正确识别21个交易日（跳过清明假期4月4-6日）

#### 8. 股票池生成器非交易日过滤 ⭐⭐⭐⭐⭐
- **文件**：[generate_stockpool.py](file://e:\LearnPY\Projects\StockBot\backtest\generate_stockpool.py)
- **问题**：原逻辑仅过滤周末，未处理法定节假日
- **解决方案**：使用 akshare 获取准确的A股交易日历
- **效果**：自动识别并过滤所有非交易日（周末+节假日）
- **降级机制**：API失败时自动降级为仅过滤周末

#### 9. 粗筛参数配置化与优化 ⭐⭐⭐⭐⭐
- **文件**：[config.yaml](file://e:\LearnPY\Projects\StockBot\config.yaml)、[generate_stockpool.py](file://e:\LearnPY\Projects\StockBot\backtest\generate_stockpool.py)
- **新增配置项**：
  ```yaml
  backtest:
    # 涨跌幅过滤区间（%）
    min_price_change_pct: -5.0    # 收紧：从-10%改为-5%
    max_price_change_pct: 25.0    # 收紧：从+30%改为+25%
    
    # 成交量放大倍数范围
    min_volume_ratio: 1.3         # 提高：从1.1x改为1.3x
    max_volume_ratio: 8.0         # 保持不变
  ```
- **代码改进**：从配置文件读取参数，替代硬编码
- **实测效果**：选股数量从平均119只减少到91只（**-23%**）

#### 10. 新版100分评分系统 ⭐⭐⭐⭐⭐
- **文件**：[local/utils.py](file://e:\LearnPY\Projects\StockBot\local\utils.py)
- **新增函数**：[calculate_trend_score_v2()](file://e:\LearnPY\Projects\StockBot\local\utils.py#L729-L928) - 满分100分的综合评分系统
- **评分维度**：
  | 维度 | 权重 | 说明 |
  |------|------|------|
  | **量能因子** | 30分 | 成交量递增、量比、换手率 |
  | **趋势因子** | 25分 | 均线排列、均线斜率 |
  | **动量因子** | 20分 | 5日/10日涨幅、相对强度 |
  | **形态因子** | 15分 | MACD、布林带位置 |
  | **风险因子** | 10分 | RSI、波动率控制 |
- **评级标准**：
  - 80-100分：⭐⭐⭐⭐⭐ 优秀
  - 60-79分：⭐⭐⭐⭐ 良好
  - 40-59分：⭐⭐⭐ 中等
  - 20-39分：⭐⭐ 较差
  - 0-19分：⭐ 很差

#### 11. 回测引擎集成新评分系统 ⭐⭐⭐⭐⭐
- **文件**：[score_stockpool.py](file://e:\LearnPY\Projects\StockBot\backtest\score_stockpool.py)
- **关键修改**：第208行已调用新版评分系统
  ```python
  from local.utils import calculate_trend_score_v2
  score = calculate_trend_score_v2(market, code, days=300)
  ```
- **配置读取**：从 [config.yaml](file://e:\LearnPY\Projects\StockBot\config.yaml) 读取 `min_score: 60`

#### 12. 实测验证（2026-04-13）⭐⭐⭐⭐⭐
- **筛选流程**：
  ```
  白名单 (5014只) 
      ↓ 粗筛（放量+趋势+涨幅+量比）
  候选池 (46只)
      ↓ 精筛（100分评分系统）
  评分>=60 (18只)
      ↓ Top N排序
  最终选股 (10只)
  ```
- **Top 10股票详情**：
  | 排名 | 代码 | 名称 | 行业 | 评分 | 评级 |
  |------|------|------|------|------|------|
  | 1 | 600379 | 宝光股份 | 电网设备 | 78.0 | ⭐⭐⭐⭐ 良好 |
  | 2 | 000036 | 华联控股 | 房地产开发 | 77.0 | ⭐⭐⭐⭐ 良好 |
  | 3 | 688155 | 先惠技术 | 电池 | 74.0 | ⭐⭐⭐⭐ 良好 |
  | 4 | 603773 | 沃格光电 | 光学光电子 | 72.0 | ⭐⭐⭐⭐ 良好 |
  | 5 | 603800 | 洪田股份 | 专用设备 | 72.0 | ⭐⭐⭐⭐ 良好 |
  | 6 | 002497 | 雅化集团 | 化学制品 | 71.0 | ⭐⭐⭐⭐ 良好 |
  | 7 | 002192 | 融捷股份 | 能源金属 | 70.0 | ⭐⭐⭐⭐ 良好 |
  | 8 | 301526 | 国际复材 | 玻璃玻纤 | 70.0 | ⭐⭐⭐⭐ 良好 |
  | 9 | 603045 | 福达合金 | 金属新材料 | 70.0 | ⭐⭐⭐⭐ 良好 |
  | 10 | 688719 | 爱科赛博 | 其他电源设备Ⅱ | 69.0 | ⭐⭐⭐⭐ 良好 |
- **统计摘要**：
  - 最高评分：**78.0分**（宝光股份）
  - 最低评分：**69.0分**（爱科赛博）
  - 平均评分：**72.3分**
  - 评级分布：**全部为"⭐⭐⭐⭐ 良好"**

---

## 🎯 **核心设计原则**

### "宽粗筛，严评分"策略
- **第一阶段（粗筛）**：放宽条件，选出100-200只候选股票
  - 放量天数：3天（从5天降低，提升灵敏度）
  - 涨跌幅区间：[-5%, +25%]（收紧，过滤极端值）
  - 量比范围：[1.3x, 8.0x]（提高下限，过滤温和放量）
- **第二阶段（精筛）**：严格评分，筛选出Top 10高分股票
  - 评分阈值：60分（满分100分）
  - 选股数量：最多10只，最少3只
  - 按评分降序排序

---

## 🛠️ **实用工具清单**

### 1. 查看原始股票池（粗筛结果）
```bash
python backtest/view_stockpool.py --date 2026-04-13 --top 20
```
**功能**：显示未经评分的候选股票列表

### 2. 对股票池进行批量评分 ⭐推荐
```bash
# 单日评分
python backtest/score_stockpool.py --date 2026-04-13

# 批量评分（带实时进度展示）
python backtest/score_stockpool.py --start-date 2026-04-13 --end-date 2026-04-24
```
**功能**：对股票池中的股票进行100分制技术评分，自动筛选Top N高分股票
**特性**：
- ✅ 实时进度展示（每25只股票更新一次）
- ✅ 自动应用评分阈值和数量限制
- ✅ 支持单日和批量处理

### 3. 查看评分后的股票池（精筛结果）⭐推荐
```bash
python backtest/view_scored_results.py --date 2026-04-13
python backtest/view_scored_results.py --date 2026-04-13 --top 5
```
**功能**：显示评分后的Top N股票，包含代码、名称、行业、评分、评级

### 4. 统计分析选股数量
```bash
python backtest/analyze_stockpool.py --start-date 2026-04-13 --end-date 2026-04-24
```
**功能**：统计指定日期范围内的选股数量、平均值、最大最小值

### 5. 测试单只股票的评分
```bash
python backtest/test_new_score.py --code 000036
python backtest/test_new_score.py --code 600707 --market sh
```
**功能**：对比新旧评分系统，显示详细评分结果

### 6. 测试换手率评分规则 ⭐⭐⭐⭐⭐ 【NEWEST】
```bash
# 测试新版换手率评分规则
python tests/test_new_turnover_rules.py

# 详细验证换手率计算过程
python tests/verify_turnover_scoring.py
```
**功能**：
- 验证新版双重条件评分规则的正确性
- 展示每日换手率和累计换手率的详细计算过程
- 显示评分判断的完整逻辑
**特性**：
- ✅ 自动获取流通股本
- ✅ 计算最近3天（或配置的volume_period天）的每日换手率
- ✅ 根据新规则判断评分（5分/3分/0分）
- ✅ 输出详细的判断依据

### 7. 测试数据源一致性 ⭐⭐⭐⭐⭐ 【NEWEST】
```bash
# 测试单只股票的数据一致性
python backtest/test_data_source.py --code 600519 --market sh
python backtest/test_data_source.py --code 000001 --market sz

# 性能对比测试（自动对比本地数据和腾讯API）
python backtest/test_performance.py
```
**功能**：
- 验证本地通达信数据与腾讯API数据的一致性
- 对比两种数据源的性能差异
- 显示最近10个交易日的收盘价对比
- 计算最大差异和平均差异
**特性**：
- ✅ 数据一致性评级（优秀/良好/较差）
- ✅ 性能提升倍数统计
- ✅ 自动切换配置进行测试

---

## 📂 **重要文件清单**

### 核心代码文件
- `backtest/generate_stockpool.py` - 股票池生成（✅ 已优化：缓存+配置化+非交易日过滤）
- `backtest/score_stockpool.py` - 评分筛选（✅ 已集成100分评分系统 + 实时进度展示）⭐NEW
- `local/utils.py` - 技术指标计算（✅ 新增 calculate_trend_score_v2 + 本地数据源支持）⭐NEWEST
- `backtest/backtest_engine.py` - 回测引擎（✅ 已修复非交易日过滤 + 资金计算bug + 交易周期跳转逻辑）⭐NEWEST
- `backtest/run_backtest.py` - 回测入口（✅ 已添加--debug参数）⭐NEWEST

### 配置文件
- `config.yaml` - 全局配置（✅ 已更新粗筛参数、评分阈值、数据源配置）⭐NEWEST

### 数据文件
- `data/stockpool_*.txt` - 每日股票池（含评分数据）
- `data/backtest_trades_*.csv` - 交易明细
- `data/backtest_cumulative_returns_*.png` - 收益曲线图
- `data/backtest_monthly_returns_*.png` - 月度收益图
- `data/backtest.log` - 回测日志文件（始终记录DEBUG级别）

### 工具文件
- `backtest/view_stockpool.py` - 查看原始股票池
- `backtest/view_scored_results.py` - 查看评分结果 ⭐新增
- `backtest/analyze_stockpool.py` - 统计分析 ⭐新增
- `backtest/test_new_score.py` - 测试评分系统 ⭐新增

### 文档文件
- `backtest/NEWCHAT_START.md` - 本文档
- `backtest/PHASE1_IMPLEMENTATION_STATUS.md` - 第一阶段实施状态
- `backtest/PHASE1_OPTIMIZATION_SUMMARY.md` - 详细总结

---

## 🧪 **快速验证命令**

### 场景1：生成新的股票池
```bash
# 单日测试
python backtest/generate_stockpool.py --date 2026-04-13

# 多日测试（10个交易日）
python backtest/generate_stockpool.py --start-date 2026-04-13 --end-date 2026-04-24
```

### 场景2：对股票池进行评分
```bash
# 单日评分
python backtest/score_stockpool.py --date 2026-04-13

# 批量评分
python backtest/score_stockpool.py --start-date 2026-04-13 --end-date 2026-04-24
```

### 场景3：查看评分结果
```bash
# 查看全部
python backtest/view_scored_results.py --date 2026-04-13

# 查看前N只
python backtest/view_scored_results.py --date 2026-04-13 --top 5
```

### 场景4：运行完整回测 ⭐⭐⭐⭐⭐ 【NEWEST】
```
# 生成股票池
python backtest/generate_stockpool.py --start-date 2026-04-01 --end-date 2026-04-30

# 评分筛选
python backtest/score_stockpool.py --start-date 2026-04-01 --end-date 2026-04-30

# 执行回测（默认模式 - 简洁）
python backtest/run_backtest.py --start-date 2026-04-01 --end-date 2026-04-30

# 执行回测（DEBUG模式 - 查看详细资金明细）⭐NEW
python backtest/run_backtest.py --start-date 2026-04-01 --end-date 2026-04-30 --debug
```
**功能**：
- 模拟真实交易过程（次日开盘买入，N个交易日后收盘卖出）
- 计算各项统计指标并与沪深300对比
- 生成详细的回测报告和可视化图表
- **DEBUG模式新增**：显示每个周期的详细资金构成
  - 实际投入资金、闲置资金、资金利用率
  - 跳过的股票数量（因不足100股无法买入）
**特性**：
- ✅ 严格交易周期隔离（上一周期卖出后才能开始下一周期）
- ✅ 自动过滤非交易日（周末+法定节假日）
- ✅ 正确处理闲置资金（100股整数倍限制）
- ✅ 支持--debug参数按需启用详细日志
- ✅ 日志文件始终记录DEBUG级别信息
**验证要点**（DEBUG模式）：
- 闲置资金 > 0（除非恰好整除）
- 资金利用率 < 100%（通常95%-99%）
- 期末资金 ≈ 投入资金×(1+收益率) + 闲置资金

---

## 📊 **配置参数说明**

### config.yaml - backtest 节点

```yaml
backtest:
  # === 基础配置 ===
  hold_days: 3                    # 持仓天数（交易日）
  volume_period: 3                # 连续放量天数
  initial_capital: 1000000        # 初始资金（元）
  
  # === 第一阶段粗筛参数 ===
  min_price_change_pct: -5.0      # 最小允许涨跌幅（%）
  max_price_change_pct: 25.0      # 最大允许涨跌幅（%）
  min_volume_ratio: 1.3           # 最小量比（倍数）
  max_volume_ratio: 8.0           # 最大量比（倍数）
  
  # === 第二阶段评分参数 ===
  min_score: 60                   # 最低评分阈值（满分100分）
  max_stocks_per_cycle: 10        # 每个周期最多选10只股票
  min_stocks_per_cycle: 3         # 最少选3只（保证分散）
  
  # === 数据源配置（2026-05-04新增）===
  use_local_data: true            # 是否使用本地通达信数据（默认true，性能提升5-10倍）
  data_consistency_check: false   # 是否启用数据一致性验证（首次使用建议true）
  max_data_age_days: 7            # 数据最大允许年龄（交易日），超过则警告
```

### 参数调优建议

#### 如果选股数量太多（>150只/天）
- 提高 `min_volume_ratio`：1.3 → 1.5
- 收紧涨跌幅区间：[-5%, +25%] → [-3%, +20%]
- 提高评分阈值：60 → 65

#### 如果选股数量太少（<50只/天）
- 降低 `min_volume_ratio`：1.3 → 1.2
- 放宽涨跌幅区间：[-5%, +25%] → [-8%, +30%]
- 降低评分阈值：60 → 55

#### 如果回测收益率不佳
- 增加持仓天数：3 → 5-7
- 提高评分阈值：60 → 70（只选优质股票）
- 考虑增加止损机制

---

## ❓ **常见问题**

### Q1: 新版评分系统和旧版有什么区别？
**答**：
- **旧版**：满分约6.5分，维度简单（均线3+MACD 1+RSI 1+布林带1+成交量0.5）
- **新版**：满分100分，5大维度15个子项，更科学全面
- **优势**：更直观、更易理解、更容易调整权重

### Q2: 为什么评分阈值设置为60分？
**答**：根据实测结果，60分对应"⭐⭐⭐⭐ 良好"级别，能够在选股质量和数量之间取得平衡。可以根据策略偏好调整：
- 保守策略：70分（只选优秀股票）
- 平衡策略：60分（默认，选良好及以上）
- 激进策略：40-50分（选中等的也可考虑）

### Q3: 粗筛参数如何影响选股数量？
**答**：
- **放量天数**：5天→3天，选股数量增加约30-50%
- **涨跌幅区间**：越宽松，选股越多
- **量比范围**：下限越高，选股越少（过滤温和放量）

### Q4: 内存缓存如何工作？
**答**：首次访问某只股票时从磁盘读取并缓存到 `self.data_cache`，后续同一股票的多次访问直接从内存获取，避免重复IO操作。性能提升约20-30倍，5000只股票约占用72MB内存。

### Q5: 非交易日过滤是如何实现的？
**答**：使用 akshare 库获取中国A股官方交易日历，准确识别所有非交易日（包括周末和法定节假日）。如果API失败，会自动降级为仅过滤周末的简化方案。

### Q6: 新版换手率评分规则是什么？⭐⭐⭐⭐⭐ 【NEWEST】
**答**：新版换手率评分采用双重条件判断，强调稳定性和合理性。

**评分规则**：
- **5分**：每日换手率均在 5%~15% 且 3日累计 15%~45%（优质活跃度）
- **3分**：每日换手率均在 3%~20% 且 3日累计 12%~50%（一般活跃度）
- **0分**：任一日换手率 >25% 或 <2%，或其他不满足条件的情况

**核心特点**：
- ✅ 去除负分机制，最低得分为0分
- ✅ 双重条件控制（每日范围+累计范围）
- ✅ 排除极端情况（单日过度活跃或过于冷清）
- ✅ 边界包含（恰好等于阈值时按更高档位计分）

**如何调整**：
- 修改累计天数：编辑 [config.yaml](file://e:\LearnPY\Projects\StockBot\config.yaml) 中的 `backtest.volume_period`
- 调整阈值：修改 [local/utils.py](file://e:\LearnPY\Projects\StockBot\local\utils.py) 中 [calculate_cumulative_turnover_score()](file://e:\LearnPY\Projects\StockBot\local\utils.py#L109-L195) 函数的阈值参数

### Q7: 评分工具的进度展示如何工作？⭐NEW
**答**：[score_stockpool.py](file://e:\LearnPY\Projects\StockBot\backtest\score_stockpool.py) 已添加实时进度展示功能：
- **显示内容**：`[日期进度] 日期 | 股票 X/N (XX%) | 已耗时: X秒`
- **更新频率**：每处理25只股票更新一次进度
- **技术实现**：使用 `\r` 实现单行动态刷新，不会刷屏
- **优势**：清晰了解处理进度，无需等待很久才有反馈

### Q8: 本地数据源和腾讯API有什么区别？⭐⭐⭐⭐⭐ 【NEWEST】
**答**：
- **本地数据源（推荐）**：
  - ✅ 速度快：性能提升5-10倍（3分钟 vs 15分钟）
  - ✅ 离线可用：不依赖网络连接
  - ✅ 稳定可靠：不受网络波动影响
  - ⚠️ 需定期更新：打开通达信执行"盘后数据下载"
  - 📊 数据一致性：与腾讯API完全一致（差异0.00%）
  
- **腾讯API**：
  - ❌ 速度慢：每只股票需要1-2秒网络请求
  - ❌ 依赖网络：需要稳定的互联网连接
  - ❌ 可能限流：频繁请求可能被限制
  - ✅ 数据最新：实时获取最新行情
  
- **降级机制**：本地数据失败时自动切换到腾讯API，确保系统健壮性

### Q9: 如何知道本地数据是否过期？
**答**：系统会自动检查，如果数据超过配置的天数（默认7天）未更新，会显示警告：
```
⚠️  警告: sh.600519 的本地数据已超过7天未更新 (最后更新: 2026-04-25)
```
**解决方法**：打开通达信软件，执行"盘后数据下载"。

### Q10: 如何验证本地数据的准确性？
**答**：使用测试工具进行验证：
```bash
# 测试单只股票
python backtest/test_data_source.py --code 600519 --market sh

# 性能对比测试
python backtest/test_performance.py
```
输出示例：
```
数据一致性优秀（差异<0.5%）
最大差异: 0.00%
平均差异: 0.00%
```

### Q11: 回测引擎的资金计算是如何处理的？⭐⭐⭐⭐⭐ 【NEWEST】
**答**：回测引擎正确处理了A股100股整数倍限制导致的资金闲置问题。

**四个资金概念的关系**：
```
期初资金 = 本周期投入资金 + 本周期闲置资金
期末资金 = 本周期投入资金 × (1 + 周期收益率) + 本周期闲置资金
周期收益率 = (期末市值 - 实际投入) / 实际投入 × 100%
```

**核心修复**（2026-05-05）：
- ✅ 修改 `_calculate_cycle_final_capital()` 方法，正确计算包含闲置资金的期末资金
- ✅ 增强 `calculate_cycle_metrics()` 方法，输出详细的资金构成
- ✅ 添加 `--debug` 参数，按需启用DEBUG日志查看详细资金明细

**验证方法**：
```bash
# 使用DEBUG模式查看详细的资金明细
python backtest/run_backtest.py --start-date 2026-04-01 --end-date 2026-04-10 --debug
```

**正常表现**：
- 闲置资金 > 0（除非恰好整除）
- 资金利用率 < 100%（通常95%-99%）
- 期末资金 ≈ 投入资金×(1+收益率) + 闲置资金

### Q12: 如何启用DEBUG日志查看详细资金明细？⭐⭐⭐⭐⭐ 【NEWEST】
**答**：有两种方式：

**方式1：使用 --debug 参数（推荐）**
```bash
# 默认模式（INFO级别，简洁清晰）
python backtest/run_backtest.py --start-date 2026-04-01 --end-date 2026-04-10

# DEBUG模式（显示详细资金明细）
python backtest/run_backtest.py --start-date 2026-04-01 --end-date 2026-04-10 --debug
```

**方式2：修改代码（不推荐）**
在 `backtest/run_backtest.py` 中将控制台日志级别从 `"INFO"` 改为 `"DEBUG"`

**注意事项**：
- 日志文件（`data/backtest.log`）始终记录DEBUG级别信息，无论是否使用--debug参数
- --debug参数仅影响控制台输出，不影响日志文件
- DEBUG模式会输出更多信息，可能略微降低执行速度（影响很小）

### Q13: 回测引擎的交易周期是如何衔接的？⭐⭐⭐⭐⭐ 【NEWEST】
**答**：回测引擎采用"卖出日 = 下一周期选股日"的无缝衔接机制。

**时间线示例**（hold_days = 3）：
```
周期1: T0(选股) → T1(买入) → T2 → T3(卖出+选股)
                                ↓
周期2: T3(已选股) → T4(买入) → T5 → T6(卖出+选股)
```

**核心原则**：
- ✅ 选股日 = 卖出日（同一天完成卖出和选股）
- ✅ 买入日 = 选股日 + 1个交易日
- ✅ 卖出日 = 买入日 + (hold_days - 1)个交易日
- ✅ 下一个周期的选股日 = 当前周期的卖出日
- ✅ 周期之间绝不重叠

**修复历史**（2026-05-05）：
- **问题**：之前代码在卖出后跳过一个交易日才选股，导致资金闲置
- **修复**：将跳转逻辑从 `i = sell_date_idx + 1` 改为 `i = sell_date_idx`
- **效果**：实现资金无缝衔接，提高利用率

**验证方法**：
```bash
# 运行短期回测，查看交易周期汇总
python backtest/run_backtest.py --start-date 2026-04-01 --end-date 2026-04-10
```

**正常表现**：
- 周期N的卖出日 = 周期N+1的选股日
- 交易周期连续，无空档期
- 资金利用率高，收益率准确

### Q14: 下一步应该做什么？
**答**：建议按以下顺序进行：
1. **短期验证**：运行1个月回测（2026-04-01至2026-04-30），验证新评分系统效果
2. **参数调优**：根据回测结果调整评分阈值、持仓天数等参数
3. **长期测试**：运行3-6个月回测，验证策略稳定性
4. **进一步优化**：考虑增加板块热度评分、资金流向因子等

---

## 🚀 **立即行动建议**

### 选项A：快速验证新版换手率评分系统（推荐）⭐⭐⭐⭐⭐ 【NEWEST】
```bash
# 1. 测试新版换手率评分规则
python tests/test_new_turnover_rules.py
python tests/verify_turnover_scoring.py

# 2. 生成股票池
python backtest/generate_stockpool.py --start-date 2026-06-01 --end-date 2026-06-02

# 3. 对所有股票池进行评分（自动应用新换手率评分规则）
python backtest/score_stockpool.py --start-date 2026-06-01 --end-date 2026-06-02

# 4. 查看评分结果
python backtest/view_scored_results.py --date 2026-06-02

# 5. 运行回测
python backtest/run_backtest.py --start-date 2026-06-01 --end-date 2026-06-02
```

### 选项B：快速验证新评分系统（原有100分系统）⭐
```
# 1. 生成1个月的股票池
python backtest/generate_stockpool.py --start-date 2026-04-01 --end-date 2026-04-30

# 2. 对所有股票池进行评分（使用本地数据源，速度快5-10倍）
python backtest/score_stockpool.py --start-date 2026-04-01 --end-date 2026-04-30

# 3. 运行回测
python backtest/run_backtest.py --start-date 2026-04-01 --end-date 2026-04-30

# 4. 查看结果
# 回测报告会保存在 data/ 目录下
```

### 选项C：先验证数据源一致性（首次使用推荐）⭐⭐⭐⭐⭐ 【NEWEST】
```bash
# 1. 测试单只股票的数据一致性
python backtest/test_data_source.py --code 600519 --market sh
python backtest/test_data_source.py --code 000001 --market sz

# 2. 性能对比测试
python backtest/test_performance.py

# 3. 如果验证通过，开始正常使用
python backtest/score_stockpool.py --date 2026-01-13
```

### 选项D：先手动审查选股质量
```bash
# 查看几个典型日期的选股结果
python backtest/view_scored_results.py --date 2026-04-13
python backtest/view_scored_results.py --date 2026-04-16
python backtest/view_scored_results.py --date 2026-04-24
```

### 选项E：调整参数后再测试
```bash
# 1. 修改 config.yaml 中的参数
# 2. 重新生成股票池
python backtest/generate_stockpool.py --start-date 2026-04-01 --end-date 2026-04-30
# 3. 评分和回测...
```

---

## 📝 **待办事项清单**

### 高优先级（建议立即执行）
- [x] ✅ 评分工具性能优化 - 切换到本地数据源（2026-05-04完成）
- [x] ✅ 回测引擎资金计算Bug修复 - 正确处理闲置资金（2026-05-05完成）⭐NEWEST
- [x] ✅ 回测引擎交易周期跳转逻辑修复 - 实现资金无缝衔接（2026-05-05完成）⭐NEWEST
- [x] ✅ 换手率评分规则优化 - 新版双重条件评分系统（2026-06-02完成）⭐NEWEST
- [x] ✅ K线数据获取函数增强 - 支持可配置的最小数据长度（2026-06-02完成）⭐NEWEST
- [ ] 运行1个月回测，验证新评分系统效果
- [ ] 分析回测结果，评估胜率、收益率、最大回撤
- [ ] 根据结果调整评分阈值和持仓天数
- [ ] 定期更新通达信本地数据（建议每周更新一次）

### 中优先级（1-2周内）
- [ ] 增加板块热度评分
- [ ] 优化相对强度计算（对比沪深300）
- [ ] 引入OBV能量潮指标
- [ ] 实现数据自动更新提醒功能

### 低优先级（1-2月内）
- [ ] 接入财务数据（PE、PB、ROE等）
- [ ] 增加资金流向因子
- [ ] 实现动态权重调整
- [ ] 建立多数据源智能切换机制

---

## 💡 **关键经验总结**

### 成功经验
1. **"宽粗筛，严评分"是正确的设计思路**：粗筛阶段放宽条件，精筛阶段严格评分
2. **配置化管理优于硬编码**：便于快速调优和A/B测试
3. **内存缓存显著提升性能**：从4小时降至10分钟
4. **100分评分系统更直观**：便于理解和调整
5. **本地数据源大幅提升性能**：从15分钟降至3分钟，提升5-10倍 ⭐⭐⭐⭐⭐ 【NEWEST】
6. **数据一致性验证很重要**：首次使用时必须验证，建立信任 ⭐⭐⭐⭐⭐ 【NEWEST】
7. **降级机制提高系统健壮性**：本地失败时自动切换到腾讯API ⭐⭐⭐⭐⭐ 【NEWEST】
8. **正确处理闲置资金至关重要**：回测引擎必须区分期初资金、投入资金、闲置资金和期末资金 ⭐⭐⭐⭐⭐ 【NEWEST】
9. **灵活的日志控制提升调试效率**：通过--debug参数按需启用详细日志，平衡简洁性和可观测性 ⭐⭐⭐⭐⭐ 【NEWEST】
10. **交易周期无缝衔接提高资金效率**：卖出日应同时作为下一周期的选股日，避免资金闲置 ⭐⭐⭐⭐⭐ 【NEWEST】
11. **双重条件评分提升质量**：换手率评分同时要求每日稳定性和累计合理性，有效排除极端波动股票 ⭐⭐⭐⭐⭐ 【NEWEST - 2026-06-02】
12. **可配置的最小数据长度**：K线获取函数支持 `min_data_length` 参数，解决历史日期截断导致的数据不足问题 ⭐⭐⭐⭐⭐ 【NEWEST - 2026-06-02】

### 需要避免的陷阱
1. **评分阈值要与评分系统匹配**：旧版6.5分制不能用60分阈值
2. **粗筛参数要平衡灵敏度和准确性**：过于宽松会增加噪音，过于严格会错过机会
3. **回测周期要足够长**：至少3-6个月才能验证策略稳定性
4. **要考虑市场环境变化**：牛市、熊市、震荡市需要不同的参数
5. **不要忽视数据复权问题**：必须使用前复权数据，否则技术指标失真 ⚠️ 【重要教训】
6. **第三方库功能需先验证**：mootdx的to_adjust函数有bug，不能直接使用 ⚠️ 【重要教训】
7. **本地数据需定期更新**：过期的本地数据会导致评分不准确 ⚠️ 【重要提醒】
8. **严禁将期初资金等同于投入资金**：必须考虑100股整数倍限制导致的资金闲置 ⚠️ 【重要教训 - 2026-05-05修复】
9. **严禁在卖出后跳过交易日才选股**：卖出日必须同时作为下一周期的选股日 ⚠️ 【重要教训 - 2026-05-05修复】
10. **换手率评分需注意边界条件**：恰好等于阈值时应按更高档位计分，确保逻辑一致性 ⚠️ 【重要提醒 - 2026-06-02】

### 性能优化最佳实践 ⭐⭐⭐⭐⭐ 【NEWEST】
1. **优先使用本地数据源**：避免对每只股票发起独立的网络API请求
2. **实现内存缓存机制**：对频繁访问的数据建立缓存，避免重复计算
3. **配置化控制数据源**：通过yaml配置灵活切换，支持A/B测试
4. **实时进度反馈**：长时间操作显示百分比和预计剩余时间
5. **自动降级方案**：主数据源失败时自动切换到备用方案
6. **数据质量监控**：定期检查数据新鲜度和一致性
7. **正确的资金管理**：准确计算投入资金、闲置资金和期末资金，确保复利效应正确传递 ⭐⭐⭐⭐⭐ 【NEWEST】
8. **无缝的交易周期衔接**：卖出日同时作为下一周期的选股日，最大化资金利用率 ⭐⭐⭐⭐⭐ 【NEWEST】

---

## 📚 **相关文档**

### 详细技术文档
- [backtest/SCORE_OPTIMIZATION_REPORT.md](file://e:\LearnPY\Projects\StockBot\backtest\SCORE_OPTIMIZATION_REPORT.md) - 评分工具性能优化详细报告 ⭐⭐⭐⭐⭐ 【NEWEST】
- [backtest/OPTIMIZATION_QUICKSTART.md](file://e:\LearnPY\Projects\StockBot\backtest\OPTIMIZATION_QUICKSTART.md) - 数据源优化快速使用指南 ⭐⭐⭐⭐⭐ 【NEWEST】
- [backtest/PHASE1_IMPLEMENTATION_STATUS.md](file://e:\LearnPY\Projects\StockBot\backtest\PHASE1_IMPLEMENTATION_STATUS.md) - 第一阶段实施状态
- [backtest/PHASE1_OPTIMIZATION_SUMMARY.md](file://e:\LearnPY\Projects\StockBot\backtest\PHASE1_OPTIMIZATION_SUMMARY.md) - 详细总结

### 核心代码文件
- [local/utils.py](file://e:\LearnPY\Projects\StockBot\local\utils.py) - 技术指标计算（✅ 新增新版换手率评分规则 + K线获取函数增强）⭐⭐⭐⭐⭐ 【NEWEST - 2026-06-02】
- [backtest/score_stockpool.py](file://e:\LearnPY\Projects\StockBot\backtest\score_stockpool.py) - 评分工具主程序（✅ 已集成100分评分系统 + 实时进度展示）⭐NEW
- [backtest/backtest_engine.py](file://e:\LearnPY\Projects\StockBot\backtest\backtest_engine.py) - 回测引擎（✅ 已修复资金计算bug + 交易周期跳转逻辑）⭐NEWEST
- [backtest/run_backtest.py](file://e:\LearnPY\Projects\StockBot\backtest\run_backtest.py) - 回测入口（✅ 已添加--debug参数）⭐NEWEST
- [config.yaml](file://e:\LearnPY\Projects\StockBot\config.yaml) - 全局配置文件

### 测试工具
- [tests/test_new_turnover_rules.py](file://e:\LearnPY\Projects\StockBot\tests\test_new_turnover_rules.py) - 新版换手率评分规则测试工具 ⭐⭐⭐⭐⭐ 【NEWEST - 2026-06-02】
- [tests/verify_turnover_scoring.py](file://e:\LearnPY\Projects\StockBot\tests\verify_turnover_scoring.py) - 换手率评分详细验证工具 ⭐⭐⭐⭐⭐ 【NEWEST - 2026-06-02】
- [backtest/test_data_source.py](file://e:\LearnPY\Projects\StockBot\backtest\test_data_source.py) - 数据一致性测试工具
- [backtest/test_performance.py](file://e:\LearnPY\Projects\StockBot\backtest\test_performance.py) - 性能对比测试工具

---

**准备好开始了吗？** 请告诉我你想执行哪个选项，或者有其他问题需要解答！🎯
