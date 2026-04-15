# 环境管理指南

## 📋 目录

- [快速开始](#快速开始)
- [Conda环境管理](#conda环境管理)
- [Pip虚拟环境](#pip虚拟环境)
- [版本锁定](#版本锁定)
- [常见问题](#常见问题)

---

## 🚀 快速开始

### 方法1: 使用Conda（推荐）✅

**Windows用户：**
```bash
# 双击运行或使用命令行
setup_env.bat
```

**Linux/Mac用户：**
```bash
# 添加执行权限
chmod +x setup_env.sh

# 运行脚本
./setup_env.sh
```

**手动操作：**
```bash
# 1. 创建环境
conda env create -f environment.yml -n stockbot-py312

# 2. 激活环境
conda activate stockbot-py312

# 3. 验证环境
python --version  # 应显示 Python 3.12.3

# 4. 启动服务
python main.py
```

### 方法2: 使用Pip虚拟环境

```bash
# 1. 创建虚拟环境
python -m venv venv

# 2. 激活环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 启动服务
python main.py
```

---

## 🔧 Conda环境管理

### 环境配置文件

项目提供 `environment.yml` 文件，包含所有依赖和Python版本信息。

**文件结构：**
```yaml
name: stockbot
channels:
  - defaults
  - conda-forge
dependencies:
  - python=3.12.3        # 固定Python版本
  - pip
  - pip:
    - fastapi>=0.104.0   # pip包列表
    - ...
```

### 常用命令

#### 创建环境
```bash
# 从配置文件创建
conda env create -f environment.yml

# 指定环境名称
conda env create -f environment.yml -n myenv

# 从现有环境导出配置
conda env export > environment.yml
```

#### 管理环境
```bash
# 查看所有环境
conda env list

# 激活环境
conda activate stockbot-py312

# 退出环境
conda deactivate

# 删除环境
conda env remove -n stockbot-py312

# 克隆环境
conda create -n stockbot-backup --clone stockbot-py312
```

#### 更新环境
```bash
# 根据配置文件更新
conda env update -f environment.yml

# 更新并清理未使用的包
conda env update -f environment.yml --prune

# 更新特定包
conda update pandas
```

#### 安装包
```bash
# 使用conda安装
conda install package_name

# 使用pip安装（在conda环境中）
pip install package_name

# 批量安装
pip install -r requirements.txt
```

### 环境隔离最佳实践

1. **每个项目独立环境**
   ```bash
   conda create -n project1 python=3.12
   conda create -n project2 python=3.11
   ```

2. **定期清理缓存**
   ```bash
   conda clean --all
   ```

3. **导出环境配置**
   ```bash
   # 完整导出（包含所有依赖）
   conda env export > environment_full.yml
   
   # 仅导出手动安装的包
   conda env export --from-history > environment.yml
   ```

---

## 🐍 Pip虚拟环境

### 创建和管理

```bash
# 创建虚拟环境
python -m venv venv

# 激活环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 查看已安装的包
pip list

# 导出依赖
pip freeze > requirements.txt

# 从文件安装
pip install -r requirements.txt

# 删除环境
# 直接删除venv文件夹即可
rm -rf venv  # Linux/Mac
rmdir /s venv  # Windows
```

### 版本锁定

**requirements.txt** - 宽松版本（推荐开发使用）
```txt
fastapi>=0.104.0
pandas>=2.0.0
```

**requirements_locked.txt** - 精确版本（推荐生产使用）
```txt
fastapi==0.109.0
pandas==2.2.0
```

**生成锁定文件：**
```bash
# 在当前环境中
pip freeze > requirements_locked.txt
```

---

## 🎯 版本管理策略

### Python版本对齐

**目标：** 本地开发环境与服务器生产环境保持一致

**当前配置：**
- 服务器: Python 3.12.3
- 本地: 应设置为 Python 3.12.3

**实现方式：**

1. **使用 `.python-version` 文件**
   ```
   3.12.3
   ```
   
   pyenv会自动读取此文件并切换到对应版本。

2. **使用conda环境**
   ```bash
   conda create -n stockbot-py312 python=3.12.3
   ```

3. **检查版本**
   ```bash
   python check_python_version.py
   ```

### 依赖版本管理

| 文件 | 用途 | 适用场景 |
|------|------|---------|
| `requirements.txt` | 宽松版本约束 | 日常开发 |
| `requirements_locked.txt` | 精确版本锁定 | 生产部署、CI/CD |
| `environment.yml` | Conda环境配置 | Conda用户 |
| `.python-version` | Python版本指定 | pyenv用户 |

---

## 🔍 常见问题

### Q1: Conda环境创建失败

**错误信息：**
```
ResolvePackageNotFound: python=3.12.3
```

**解决方法：**
```bash
# 1. 更新conda
conda update conda

# 2. 尝试其他渠道
conda config --add channels conda-forge

# 3. 使用可用版本
conda search python

# 4. 手动指定版本
conda create -n stockbot python=3.12
```

### Q2: 依赖冲突

**错误信息：**
```
ConflictingDependenciesError
```

**解决方法：**
```bash
# 1. 创建新环境
conda create -n stockbot-new python=3.12.3

# 2. 逐个安装包
conda install pandas numpy
pip install fastapi uvicorn

# 3. 使用pip解决
pip install --upgrade pip
pip install -r requirements.txt --force-reinstall
```

### Q3: 激活环境后Python版本不对

**检查步骤：**
```bash
# 1. 确认当前环境
conda info --envs

# 2. 查看Python路径
which python  # Linux/Mac
where python  # Windows

# 3. 重新激活
conda deactivate
conda activate stockbot-py312

# 4. 验证版本
python --version
```

### Q4: Pip包安装缓慢

**优化方法：**
```bash
# 使用国内镜像源
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 或使用阿里云镜像
pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/

# 临时使用
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### Q5: 如何同步开发和生产环境？

**步骤：**

1. **在开发环境导出依赖**
   ```bash
   pip freeze > requirements_dev.txt
   ```

2. **在生产环境安装**
   ```bash
   pip install -r requirements_dev.txt
   ```

3. **或使用conda**
   ```bash
   # 导出
   conda env export > environment_prod.yml
   
   # 导入
   conda env create -f environment_prod.yml
   ```

### Q6: 如何备份环境？

**方法1: 导出配置**
```bash
conda env export > environment_backup_20260413.yml
```

**方法2: 克隆环境**
```bash
conda create -n stockbot-backup --clone stockbot-py312
```

**方法3: 打包环境**
```bash
# 导出为tarball
conda pack -n stockbot-py312 -o stockbot-env.tar.gz

# 在其他机器恢复
conda create -n stockbot
conda unpack -n stockbot stockbot-env.tar.gz
```

---

## 📊 环境对比

| 特性 | Conda | Pip + venv |
|------|-------|-----------|
| Python版本管理 | ✅ 支持 | ❌ 需单独安装 |
| 非Python包管理 | ✅ 支持 | ❌ 不支持 |
| 环境隔离 | ✅ 优秀 | ✅ 良好 |
| 依赖解析 | ✅ 智能 | ⚠️ 简单 |
| 跨平台 | ✅ 优秀 | ✅ 良好 |
| 学习曲线 | 中等 | 简单 |
| 磁盘占用 | 较大 | 较小 |
| 推荐场景 | 数据科学、多语言项目 | 纯Python项目 |

---

## 💡 最佳实践

### 1. 环境命名规范

```bash
# 项目名-Python版本
conda create -n stockbot-py312 python=3.12.3

# 项目名-环境类型
conda create -n stockbot-dev python=3.12.3
conda create -n stockbot-prod python=3.12.3
```

### 2. 定期维护

```bash
# 每周清理缓存
conda clean --all -y

# 每月更新包
conda update --all

# 每季度审查依赖
pip audit  # 检查安全漏洞
```

### 3. 文档化

在项目README中记录：
- Python版本要求
- 环境设置步骤
- 常见问题解决方案

### 4. CI/CD集成

```yaml
# .github/workflows/test.yml
name: Test
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Conda
        uses: conda-incubator/setup-miniconda@v2
        with:
          environment-file: environment.yml
          activate-environment: stockbot
      - name: Run tests
        run: python -m pytest
```

---

## 📝 相关文件清单

| 文件 | 说明 |
|------|------|
| `environment.yml` | Conda环境配置 |
| `requirements.txt` | Pip依赖（宽松版本） |
| `requirements_locked.txt` | Pip依赖（精确版本） |
| `.python-version` | Python版本指定 |
| `setup_env.bat` | Windows环境设置脚本 |
| `setup_env.sh` | Linux/Mac环境设置脚本 |
| `check_python_version.py` | 环境检查脚本 |
| `ENVIRONMENT_GUIDE.md` | 本文档 |

---

## 🆘 获取帮助

如果遇到问题：

1. 查看日志输出
2. 运行 `python check_python_version.py` 诊断
3. 查阅本文档的常见问题部分
4. 检查Conda/Pip官方文档

---

**文档版本**: v1.0.0  
**更新日期**: 2026-04-13  
**维护者**: StockBot Team
