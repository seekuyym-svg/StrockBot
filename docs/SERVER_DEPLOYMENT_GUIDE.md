# 服务器部署指南

## 📋 环境要求

### Python 依赖
```bash
pip install -r requirements.txt
```

**注意**：`mootdx` 是可选依赖，用于读取通达信本地数据以提升性能。

---

## 🔧 关键配置调整

### ⚠️ 重要：服务器必须禁用本地数据

在 `config.yaml` 中修改以下配置：

```yaml
# 回测配置
backtest:
  use_local_data: false          # ✅ 服务器环境必须设置为 false
  data_consistency_check: false  # ✅ 关闭数据一致性检查
```

**原因**：
- ❌ 服务器通常没有安装通达信客户端
- ❌ 没有本地 `.day` 数据文件
- ❌ 即使安装了 `mootdx`，也无法读取不存在的数据
- ✅ 设置为 `false` 后，系统直接使用腾讯财经API，完全不需要 `mootdx`

---

## 🚀 部署步骤

### 方案A：纯网络API模式（强烈推荐）⭐

#### 优点
- ✅ 无需安装通达信
- ✅ 无需安装 mootdx
- ✅ 无需配置本地数据
- ✅ 开箱即用
- ✅ 零报错风险

#### 步骤

1. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

2. **修改配置**（必须）
   ```yaml
   # config.yaml
   
   backtest:
     use_local_data: false          # ← 必须设置为 false
     data_consistency_check: false  # ← 建议设置为 false
   ```

3. **运行系统**
   ```bash
   python main.py
   ```

#### 工作原理
当 `use_local_data: false` 时：
- 系统**完全不尝试**加载 `mootdx` 模块
- 直接调用腾讯财经API获取K线数据
- 避免所有与本地数据相关的错误

---

### 方案B：混合模式（不推荐用于服务器）

#### 适用场景
- 服务器上已安装通达信并同步了数据
- 已安装 `mootdx` Python包
- 希望获得更好的性能

#### 步骤

1. **安装 mootdx**
   ```bash
   pip install mootdx
   ```

2. **配置通达信目录**
   ```yaml
   TDX_DIR: "/home/ubuntu/tdx"  # 实际路径
   backtest:
     use_local_data: true         # 启用本地数据
   ```

3. **确保数据存在**
   ```bash
   # 检查数据文件是否存在
   ls /home/ubuntu/tdx/vipdoc/sh/lday/*.day
   ls /home/ubuntu/tdx/vipdoc/sz/lday/*.day
   ```

4. **运行系统**
   ```bash
   python main.py
   ```

---

## ⚠️ 常见问题处理

### 问题1：ModuleNotFoundError: No module named 'mootdx'

**错误信息**：
```
❌ 本地数据读取失败 (sz000792): No module named 'mootdx'
Traceback (most recent call last):
  File "/home/ubuntu/sb/local/utils.py", line 188, in _get_klines_from_local
    from mootdx.reader import Reader
ModuleNotFoundError: No module named 'mootdx'
```

**原因**：
- 配置了 `use_local_data: true`（或未设置，默认为 true）
- 但未安装 `mootdx` 包

**解决方案**：

**✅ 推荐方案**：禁用本地数据
```yaml
# config.yaml
backtest:
  use_local_data: false
```

**备选方案**：安装 mootdx
```bash
pip install mootdx
```

---

### 问题2：tdxdir 目录不存在

**错误信息**：
```
❌ 本地数据读取失败 (sz000792): tdxdir 目录不存在
Traceback (most recent call last):
  File "/home/ubuntu/sb/local/utils.py", line 244, in _get_klines_from_local
    reader = Reader.factory(market='std', tdxdir=tdx_dir)
Exception: tdxdir 目录不存在
```

**原因**：
- 配置了 `use_local_data: true`
- 但 `TDX_DIR` 指向的目录不存在（服务器上未安装通达信）

**解决方案**：

**✅ 推荐方案**：禁用本地数据（一劳永逸）
```yaml
# config.yaml
backtest:
  use_local_data: false          # ← 关键配置
```

**自动降级机制**（v3.2.1+）：
- ✅ 代码已增强：在尝试加载本地数据前，会先检查 `TDX_DIR` 是否存在
- ✅ 如果目录不存在，**自动降级**到腾讯财经API
- ✅ 即使配置了 `use_local_data: true`，也不会报错

**但仍建议**：服务器环境直接设置 `use_local_data: false`，避免不必要的检查和日志输出。

---

### 问题3：本地数据文件不存在

**错误信息**：
```
⚠️  本地数据不存在: sz000792
```

**原因**：
- 配置了 `use_local_data: true`
- 但通达信目录下没有对应的 `.day` 文件

**解决方案**：
1. ✅ 改为使用网络API（`use_local_data: false`）
2. 或从Windows机器复制通达信数据到服务器

---

### 问题4：数据过期警告

**警告信息**：
```
⚠️  警告: sz000792 的本地数据已超过7天未更新
```

**原因**：
- 本地数据文件最后修改时间超过7天

**解决方案**：
1. ✅ 改为使用网络API（`use_local_data: false`）
2. 或更新通达信数据
3. 或调整阈值：
   ```yaml
   backtest:
     max_data_age_days: 30  # 放宽到30天
   ```

---

## 📊 性能对比

| 数据源 | 速度 | 准确性 | 依赖 | 适用场景 |
|--------|------|--------|------|---------|
| 本地通达信 | ⚡ 快（毫秒级） | ✅ 高 | 需要通达信+数据文件+mootdx | 本地开发环境 |
| 腾讯财经API | 🐢 慢（秒级） | ✅ 高 | 仅需网络连接 | **服务器部署** |

**建议**：
- **开发/测试环境**：使用本地数据（性能更好）
- **生产环境（服务器）**：使用网络API（稳定可靠，零配置）

---

## 🔍 验证部署

### 快速测试命令

```bash
# 测试单只股票数据获取
python -c "
from local.utils import _get_historical_klines
df = _get_historical_klines('sz', '000792', days=10)
print(f'成功获取 {len(df)} 条K线数据')
print(df.tail())
"
```

**预期输出**（use_local_data=false）：
```
🔄 正在从腾讯财经API获取数据...
成功获取 10 条K线数据
            open    high     low   close      volume
date
2026-05-10  10.50   10.80   10.40   10.65   12345678
2026-05-11  10.65   10.90   10.55   10.75   13456789
2026-05-12  10.75   11.00   10.70   10.90   14567890
```

---

## 📝 总结

### ✅ 服务器推荐配置

```yaml
# config.yaml

# 回测配置
backtest:
  use_local_data: false          # ✅ 禁用本地数据（关键！）
  data_consistency_check: false  # ✅ 关闭一致性检查
  max_data_age_days: 7           # （可选）保持默认

# TDX_DIR 可以注释掉或保留（不影响）
# TDX_DIR: "/path/to/tdx"
```

### 优势
1. ✅ 无需安装 `mootdx`
2. ✅ 无需配置通达信
3. ✅ 代码不会尝试加载本地数据
4. ✅ 完全避免 ModuleNotFoundError
5. ✅ 适合云端/容器化部署

### 注意事项
- ⚠️ 网络API速度较慢，批量获取时需耐心等待
- ⚠️ 确保服务器可以访问腾讯财经API（`qt.gtimg.cn`）
- ⚠️ 建议在非高峰时段执行大批量选股任务
- ✅ 代码已优化：当 `use_local_data=false` 时，**完全不尝试**导入 `mootdx`

---

<div align="center">

**最后更新**: 2026-05-14  
**适用版本**: v3.2.0+  
**关键变更**: 新增 use_local_data 配置项，支持优雅降级

</div>
