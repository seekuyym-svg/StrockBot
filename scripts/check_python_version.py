# -*- coding: utf-8 -*-
"""检查Python环境一致性"""
import sys
import platform
from pathlib import Path

print("="*70)
print("🔍 Python环境检查")
print("="*70)

print(f"\n📋 当前环境信息:")
print(f"   Python版本: {sys.version}")
print(f"   版本号: {sys.version_info}")
print(f"   平台: {platform.platform()}")
print(f"   架构: {platform.architecture()}")
print(f"   可执行文件: {sys.executable}")

print(f"\n📁 项目路径: {Path(__file__).parent.absolute()}")

# 检查关键依赖
print(f"\n📦 关键依赖检查:")
try:
    import apscheduler
    print(f"   ✅ APScheduler: {apscheduler.__version__}")
except ImportError:
    print(f"   ❌ APScheduler: 未安装")

try:
    import fastapi
    print(f"   ✅ FastAPI: {fastapi.__version__}")
except ImportError:
    print(f"   ❌ FastAPI: 未安装")

try:
    import pydantic
    print(f"   ✅ Pydantic: {pydantic.__version__}")
except ImportError:
    print(f"   ❌ Pydantic: 未安装")

try:
    import loguru
    print(f"   ✅ Loguru: {loguru.__version__}")
except ImportError:
    print(f"   ❌ Loguru: 未安装")

print("\n" + "="*70)
print("💡 建议:")
print("   服务器Python版本: 3.12.3")
print(f"   当前Python版本: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")

if sys.version_info[:2] == (3, 12):
    print("   ✅ 版本匹配！可以正常运行")
else:
    print("   ⚠️ 版本不匹配，建议使用pyenv或conda切换到Python 3.12.3")
    print("\n   切换方法:")
    print("   1. 使用pyenv: pyenv local 3.12.3")
    print("   2. 使用conda: conda activate stockbot-py312")
    print("   3. 重新创建虚拟环境: python3.12 -m venv venv")

print("="*70)
