# 股票评分插件 stock-scorer（DSH Plugin）

给 DeepSeek Harness (DSH) 注册一个 `score_stocks` 工具：输入单个或多个 A 股代码，输出每只股票的 **综合评分(0-100) + 优选分(0-25) + 股票名称 + 所属行业**。

## 架构

```
DSH Agent ──调用──> score_stocks 工具（plugin/src/score-stock.ts，TS 薄壳）
                        │ child_process 子进程
                        ▼
                backtest/score_api.py（JSON-in/JSON-out 评分桥）
                        │ 复用
                        ▼
        HistoricalStockScorer（backtest/score_stockpool_my.py 现有引擎）
        mootdx 本地通达信数据 → 腾讯 API 降级 + 东方财富行业接口
```

评分逻辑**只在 Python 侧一份**，TS 插件不复制算法，后续调参只改 `local/utils.py::calculate_trend_score_v2` / `backtest/score_stockpool_my.py`。

## 文件

| 文件 | 作用 |
| --- | --- |
| `plugin/src/score-stock.ts` | DSH 插件本体，注册 `score_stocks` 工具 |
| `plugin/cordis.yml` | DSH 挂载配置（路径需改绝对路径） |
| `backtest/score_api.py` | Python 评分桥，可脱离 DSH 独立命令行使用 |

## 安装 / 挂载

1. **依赖**：DSH 所在机器需 Python 3.x，并安装项目依赖（`pip install mootdx pandas requests pyyaml loguru`），且能访问本项目（`config.yaml`、`local/`、`backtest/` 完整目录）。

2. **数据源**：
   - 本机有通达信数据（`config.yaml` 的 `TDX_DIR` 指向通达信安装目录，`backtest.use_local_data: true`）→ 走本地，最快。
   - 服务器/无通达信 → 把 `backtest.use_local_data` 设为 `false`，自动走腾讯 API（每只需 1-2 秒）。

3. **改绝对路径**：编辑 `plugin/cordis.yml`，把 `/absolute/path/to/project` 换成项目真实根目录：

   ```yaml
   - insert:
     - id: stock-scorer
       name: 'D:/my-project/plugin/src/score-stock.ts'   # 示例（Windows）
   ```

4. **启动 DSH**：

   ```bash
   pnpm dsh web --patch ./plugin/cordis.yml
   ```

   启动后终端应出现 `[stock-scorer] plugin loaded!`，Agent 工具列表新增 `score_stocks`。

5. **环境变量（可选）**：插件默认用 `python` 命令和"插件文件上级上级"作为项目根，若不对，启动前设置：

   ```bash
   export STOCK_SCORE_PYTHON=/path/to/conda/envs/xxx/bin/python
   export STOCK_SCORE_ROOT=/path/to/project
   ```

## 使用示例

对 Agent 说：

> 帮我给 600519、000001、300750 这三只股票评分，要带名称和行业。

或指定日期（回测/历史场景）：

> 用 2026-07-28 的数据给 sh.600519 sz.000001 打分。

返回示例（Markdown 表格）：

| 代码 | 名称 | 行业 | 综合评分 | 优选分 | 备注 |
| --- | --- | --- | --- | --- | --- |
| 000001 | 平安银行 | 银行 | 60 | 14 | |
| 600519 | 贵州茅台 | 酿酒行业 | 35 | 9 | |
| 300750 | 宁德时代 | 电池 | 29 | 13 | |

## 独立命令行验证（不依赖 DSH）

```bash
# 单只 / 多只 / 指定日期
python backtest/score_api.py --codes 600519,000001
python backtest/score_api.py --codes "sh.600519 sz.000001" --date 2026-07-28
# 跳过行业查询（更快）
python backtest/score_api.py --codes 600519 --no-industry
```

输出 stdout 为 JSON（`{date, count, results:[{code, name, industry, score, pref_score}]}`），按综合分降序；失败个股带 `error` 字段排最后，不影响其余。

## 性能与限制

- 速度：本地通达信模式约 0.3-0.5 秒/只；网络模式约 1-2 秒/只（K线 + 换手率 + 行业三处网络请求）。
- 建议单次 ≤ 30 只，工具超时 180 秒。
- 行业信息走东方财富公司概况接口，**ETF（如 513120）拿不到行业**，返回空不报错。
- 综合评分需至少 60 条日K线，次新股/停牌股数据不足会返回"评分失败"。
- 优选分第⑤项"评分趋势"依赖 `data/score/{code}.txt` 历史（批量脚本会写入）；首次查询时会实时补算前两日评分，略慢属正常。

## 排障

| 现象 | 处理 |
| --- | --- |
| 工具报"未找到 Python 解释器" | 设置 `STOCK_SCORE_PYTHON` 指向真实解释器 |
| 评分脚本执行失败 | 先在命令行跑 `python backtest/score_api.py --codes 600519` 看报错（多为依赖缺失） |
| 行业全为 null | 东方财富接口被限/失败（脚本已静默降级）；或 `--no-industry` 被误传 |
| 超时 | 减少单次代码数量，或改用本地通达信模式 |
| 评分与昨日 stockpool 文件对不上 | 检查 `--date` 是否传了非交易日；本地 TDX 数据是否已更新（`max_data_age_days`） |
