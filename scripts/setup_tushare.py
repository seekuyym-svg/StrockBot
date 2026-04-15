# -*- coding: utf-8 -*-
"""Tushare Pro 快速配置脚本"""
import os
import sys

def print_banner():
    """打印欢迎横幅"""
    print("=" * 60)
    print("🚀 Tushare Pro 快速配置工具")
    print("=" * 60)
    print()


def check_installation():
    """检查是否已安装 tushare"""
    print("📦 步骤 1/3: 检查 Tushare 安装状态...")
    
    try:
        import tushare as ts
        print(f"   ✅ Tushare 已安装 (版本：{ts.__version__})")
        return True
    except ImportError:
        print("   ❌ Tushare 未安装")
        print("\n   正在安装 Tushare...")
        import subprocess
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "tushare"])
            print("   ✅ Tushare 安装成功")
            return True
        except Exception as e:
            print(f"   ❌ 安装失败：{e}")
            print("\n   请手动运行：pip install tushare")
            return False


def get_token():
    """获取用户输入的 token"""
    print("\n📝 步骤 2/3: 配置 Tushare Token")
    print("-" * 60)
    print("\n如果您还没有 Tushare Token，请按以下步骤获取:")
    print("   1. 访问 https://tushare.pro/")
    print("   2. 注册账号并登录")
    print("   3. 进入'个人中心' -> '接口 TOKEN'")
    print("   4. 复制您的 Token")
    print("-" * 60)
    
    while True:
        token = input("\n请输入您的 Tushare Token (或直接回车跳过): ").strip()
        
        if not token:
            print("\n⚠️  您选择跳过 Token 配置")
            print("   系统将使用模拟数据或 AKShare 作为备用数据源")
            return None
        
        if len(token) < 20:
            print("   ❌ Token 格式不正确，请重新输入")
            continue
        
        # 验证 token 格式（简单验证）
        if not token.replace('_', '').replace('-', '').isalnum():
            print("   ❌ Token 包含非法字符，请重新输入")
            continue
        
        print(f"   ✅ Token 格式验证通过：{token[:10]}...{token[-5:]}")
        return token


def save_token(token):
    """保存 token 到环境变量"""
    if not token:
        return False
    
    print("\n💾 步骤 3/3: 保存 Token")
    print("-" * 60)
    
    # 检测操作系统
    if sys.platform == 'win32':
        # Windows
        print("\n检测到 Windows 系统")
        
        # 方法 1: 设置当前会话的环境变量
        os.environ['TUSHARE_TOKEN'] = token
        print("   ✅ 已设置当前会话的环境变量")
        
        # 方法 2: 永久保存到用户环境变量
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment', 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, 'TUSHARE_TOKEN', 0, winreg.REG_SZ, token)
            winreg.CloseKey(key)
            print("   ✅ 已永久保存到用户环境变量")
            print("   ⚠️  注意：需要重启终端或重新登录才能生效")
        except Exception as e:
            print(f"   ⚠️  无法永久保存：{e}")
            print("   建议手动设置:")
            print("   - PowerShell: $env:TUSHARE_TOKEN='your_token'")
            print("   - CMD: setx TUSHARE_TOKEN 'your_token'")
    
    else:
        # Linux/Mac
        os.environ['TUSHARE_TOKEN'] = token
        print("   ✅ 已设置当前会话的环境变量")
        print("   ⚠️  如需永久保存，请添加到 ~/.bashrc 或 ~/.zshrc:")
        print("   export TUSHARE_TOKEN='your_token'")
    
    # 创建 .env 文件（备选方案）
    env_file = os.path.join(os.path.dirname(__file__), '.env')
    try:
        with open(env_file, 'w') as f:
            f.write(f"TUSHARE_TOKEN={token}\n")
        print(f"   ✅ 已保存到 {env_file}")
    except Exception as e:
        print(f"   ⚠️  无法保存 .env 文件：{e}")
    
    return True


def verify_token(token):
    """验证 token 是否有效"""
    if not token:
        return False
    
    print("\n🔍 验证 Token 有效性...")
    
    try:
        import tushare as ts
        ts.set_token(token)
        pro = ts.pro_api()
        
        # 尝试获取股票基本信息
        df = pro.stock_basic(ts_code='600938.SH', fields='ts_code,name')
        
        if not df.empty:
            print(f"   ✅ Token 有效！(股票名称：{df.iloc[0]['name']})")
            return True
        else:
            print("   ⚠️  Token 可能无效或积分不足")
            return False
            
    except Exception as e:
        error_msg = str(e)
        if "积分" in error_msg or "auth" in error_msg.lower():
            print(f"   ❌ Token 验证失败：{error_msg}")
            return False
        else:
            print(f"   ⚠️  网络连接问题：{error_msg}")
            return False


def print_summary(success, token):
    """打印配置总结"""
    print("\n" + "=" * 60)
    print("📊 配置总结")
    print("=" * 60)
    
    if success and token:
        print("\n✅ Tushare Pro 配置成功！")
        print("\n下一步操作:")
        print("   1. 运行测试脚本验证数据源:")
        print("      python test_tushare.py")
        print("\n   2. 启动交易系统:")
        print("      python main.py")
        print("\n   3. 访问 API 测试:")
        print("      curl http://localhost:8080/api/v1/signals/600938")
        print("\n提示:")
        print("   - 查看详细配置文档：TUSHARE_CONFIG.md")
        print("   - 如果遇到问题，请查看文档中的故障排查部分")
        
    else:
        print("\n⚠️  配置未完成，系统将使用备用数据源")
        print("\n可选方案:")
        print("   1. 使用 AKShare 作为数据源（已自动支持）")
        print("   2. 使用模拟数据进行测试")
        print("\n如需配置 Tushare Pro，请重新运行此脚本:")
        print("   python setup_tushare.py")
    
    print("\n" + "=" * 60)


def main():
    """主函数"""
    print_banner()
    
    # 步骤 1: 检查安装
    installed = check_installation()
    if not installed:
        print_summary(False, None)
        return
    
    # 步骤 2: 获取 token
    token = get_token()
    if not token:
        print_summary(False, None)
        return
    
    # 步骤 3: 保存 token
    saved = save_token(token)
    if not saved:
        print_summary(False, None)
        return
    
    # 验证 token
    verified = verify_token(token)
    
    # 打印总结
    print_summary(verified, token if verified else None)


if __name__ == "__main__":
    main()
