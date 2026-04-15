# 更新日志 - v2.1.0

## 📅 发布日期
2026-04-15

## ✨ 新功能

### 个性化策略参数配置

从 v2.1.0 开始，StockBot 支持为不同的 ETF 分别配置个性化的马丁格尔策略参数。

#### 核心特性

1. **灵活的参数配置**
   - 每个 ETF 可以独立设置加仓跌幅阈值（`add_drop_threshold`）
   - 每个 ETF 可以独立设置止盈涨幅阈值（`take_profit_threshold`）
   - 每个 ETF 可以独立设置最大加仓次数（`max_add_positions`）
   - 每个 ETF 可以独立设置初始建仓比例（`initial_position_pct`）

2. **智能优先级机制**
   - 个性化配置优先：如果 symbol 配置了参数，使用该值
   - 全局配置兜底：如果 symbol 未配置，使用全局默认值
   - 向后兼容：不配置个性化参数时，系统行为与之前完全一致

3. **保持统一的参数**
   - 加仓倍数（`add_position_multiplier`）在所有 ETF 间保持一致
   - 单只股票最大持仓比例（`max_position_pct`）在所有 ETF 间保持一致

#### 使用示例

```yaml
symbols:
  - code: "sh.513120"  # 港股创新药ETF
    name: "港股创新药ETF"
    enabled: true
    add_drop_threshold: 3.0  # 下跌3%加仓
    take_profit_threshold: 2.0  # 盈利2%止盈
    
  - code: "sh.513050"  # 中概互联网ETF
    name: "中概互联网ETF"
    enabled: true
    add_drop_threshold: 3.5  # 下跌3.5%加仓
    take_profit_threshold: 2.5  # 盈利2.5%止盈
```

#### 适用场景

- ✅ 不同波动性的 ETF 需要不同的加仓间隔
- ✅ 不同风险偏好的 ETF 需要不同的止盈策略
- ✅ 不同资金规模的 ETF 需要不同的仓位管理
- ✅ 根据市场环境灵活调整各 ETF 的策略

## 🔧 技术改进

### 代码重构

1. **配置模型增强**
   - `SymbolConfig` 新增可选字段：`add_drop_threshold`, `take_profit_threshold`, `max_add_positions`, `initial_position_pct`
   - 所有新字段默认值为 `None`，确保向后兼容

2. **策略引擎优化**
   - 新增 `_get_symbol_strategy_config()` 方法，负责合并个性化和全局配置
   - 所有信号生成方法接收 `strategy_config` 参数
   - 修改的方法列表：
     - `analyze()`
     - `_generate_signal()`
     - `_check_add_or_sell()`
     - `_check_profit_taking()`
     - `_create_buy_signal()`
     - `_create_add_signal()`

3. **启动信息增强**
   - `main.py` 启动时显示每个 ETF 的个性化配置
   - 使用图标标识是否使用个性化配置（✓ = 个性化，○ = 全局默认）

### 测试与验证

- 新增测试脚本：`test_personalized_config.py`
- 验证个性化配置的读取和应用逻辑
- 确保向后兼容性

## 📚 文档更新

### 新增文档

1. **[PERSONALIZED_CONFIG_GUIDE.md](docs/PERSONALIZED_CONFIG_GUIDE.md)**
   - 详细的个性化配置功能说明
   - 配置优先级规则详解
   - 最佳实践建议
   - 多种配置示例

2. **[PERSONALIZED_CONFIG_QUICKSTART.md](docs/PERSONALIZED_CONFIG_QUICKSTART.md)**
   - 5分钟快速上手指南
   - 实用技巧和常见误区
   - 参数调整记录表模板

### 更新文档

1. **[README.md](README.md)**
   - 更新配置示例，展示个性化配置
   - 添加个性化配置功能提示

## 🐛 Bug 修复

无

## ⚠️ 破坏性变更

**无**。本版本完全向后兼容：
- 不配置个性化参数时，系统行为与 v2.0.0 完全一致
- 现有配置文件无需修改即可正常使用
- 所有 API 接口保持不变

## 📋 升级指南

### 从 v2.0.x 升级到 v2.1.0

1. **备份现有配置**
   ```bash
   cp config.yaml config.yaml.backup
   ```

2. **更新代码**
   ```bash
   git pull origin main
   ```

3. **安装依赖**（如有新增）
   ```bash
   pip install -r requirements.txt
   ```

4. **验证配置**
   ```bash
   python test_personalized_config.py
   ```

5. **（可选）添加个性化配置**
   
   编辑 `config.yaml`，为需要的 ETF 添加个性化参数：
   ```yaml
   symbols:
     - code: "sh.513120"
       name: "港股创新药ETF"
       enabled: true
       add_drop_threshold: 3.0
       take_profit_threshold: 2.0
   ```

6. **启动系统**
   ```bash
   python main.py
   ```

## 🎯 后续计划

- [ ] 支持更多个性化参数（如加仓倍数、最大持仓比例等）
- [ ] 提供参数优化工具，基于历史数据自动推荐最佳参数
- [ ] 增加参数对比功能，直观展示不同参数的效果差异
- [ ] 支持动态调整参数，无需重启系统

## 👥 贡献者

- StockBot Team

## 📝 反馈与支持

如有问题或建议，请提交 Issue 或 Pull Request。

---

**感谢使用 StockBot！** 🚀
