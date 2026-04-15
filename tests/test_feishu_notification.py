# -*- coding: utf-8 -*-
"""测试飞书通知功能"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.notification import get_feishu_notifier, test_feishu_notification
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")


def test_feishu():
    """测试飞书通知"""
    print("\n" + "="*70)
    print("📱 飞书通知功能测试")
    print("="*70)
    
    # 获取通知器
    notifier = get_feishu_notifier()
    
    print("\n📋 当前配置:")
    print(f"   启用状态: {notifier.enabled}")
    print(f"   Webhook URL: {notifier.webhook_url if notifier.webhook_url else '未配置'}")
    print(f"   通知信号类型: {notifier.notify_signals}")
    
    if not notifier.enabled:
        print("\n⚠️ 飞书通知未启用")
        print("\n💡 如何启用:")
        print("   1. 在 config.yaml 中设置 notification.feishu.enabled: true")
        print("   2. 配置 notification.feishu.webhook_url 为您的飞书机器人Webhook地址")
        print("   3. 重启系统")
        print("\n📖 获取Webhook URL步骤:")
        print("   1. 打开飞书，进入目标群聊")
        print("   2. 点击右上角'...' -> '群机器人' -> '添加机器人'")
        print("   3. 选择'自定义机器人'，点击'添加'")
        print("   4. 设置机器人名称（如：ETF交易助手）")
        print("   5. 复制生成的 Webhook 地址")
        print("   6. 粘贴到 config.yaml 的 webhook_url 字段")
        return
    
    if not notifier.webhook_url:
        print("\n❌ Webhook URL 未配置")
        print("\n💡 请在 config.yaml 中配置 webhook_url")
        return
    
    print("\n🧪 发送测试通知...")
    success = test_feishu_notification()
    
    if success:
        print("\n✅ 测试通知发送成功！")
        print("   请检查您的飞书群聊是否收到测试消息")
    else:
        print("\n❌ 测试通知发送失败")
        print("   请检查:")
        print("   1. Webhook URL 是否正确")
        print("   2. 网络连接是否正常")
        print("   3. 飞书机器人是否已正确添加到群聊")
    
    print("\n" + "="*70)
    print("✅ 测试完成！")
    print("="*70 + "\n")


if __name__ == "__main__":
    test_feishu()
