# -*- coding: utf-8 -*-
"""快速启动脚本"""
import sys
import subprocess
from pathlib import Path

def check_dependencies():
    """检查依赖是否已安装"""
    print("🔍 检查依赖...")
    
    required_packages = [
        "fastapi",
        "uvicorn",
        "requests",
        "pandas",
        "numpy",
        "sqlalchemy",
        "pyyaml",
        "loguru",
        "pydantic"
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"❌ 缺少以下依赖: {', '.join(missing)}")
        print("\n请运行以下命令安装:")
        print("pip install -r requirements.txt")
        return False
    
    print("✅ 所有依赖已安装")
    return True


def run_tests():
    """运行测试"""
    print("\n🧪 运行系统测试...")
    result = subprocess.run([sys.executable, "test_etf_system.py"], cwd=Path(__file__).parent)
    
    if result.returncode != 0:
        print("\n⚠️  测试未完全通过，但仍可尝试启动服务")
        response = input("是否继续启动？(y/n): ")
        if response.lower() != 'y':
            return False
    
    return True


def start_server():
    """启动服务"""
    print("\n🚀 启动ETF T+0交易系统...")
    print("=" * 60)
    print("服务地址: http://0.0.0.0:8080")
    print("API文档: http://localhost:8080/docs")
    print("=" * 60)
    print("\n按 Ctrl+C 停止服务\n")
    
    subprocess.run([sys.executable, "main.py"], cwd=Path(__file__).parent)


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("ETF链接基金T+0马丁格尔量化交易系统")
    print("=" * 60 + "\n")
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    # 询问是否运行测试
    response = input("\n是否运行测试？(y/n): ")
    if response.lower() == 'y':
        if not run_tests():
            sys.exit(0)
    
    # 启动服务
    start_server()


if __name__ == "__main__":
    main()
