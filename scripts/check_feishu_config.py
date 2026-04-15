# -*- coding: utf-8 -*-
"""飞书通知频率限制检查工具"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.notification import get_feishu_notifier


def check_feishu_config():
    """检查飞书通知配置"""
    print("\n" + "="*70)
    print("飞书通知配置检查")
    print("="*70)
    
    notifier = get_feishu_notifier()
    
    print(f"\n✅ 飞书通知状态: {'已启用' if notifier.enabled else '未启用'}")
    
    if notifier.enabled:
        print(f"📡 Webhook URL: {notifier.webhook_url[:50]}...")
        print(f"📨 通知信号类型: {notifier.notify_signals}")
        print(f"⏱️ 最小发送间隔: {notifier.min_interval_seconds} 秒")
        
        # 显示最近发送记录
        if notifier.last_send_time:
            print(f"\n📊 最近发送记录:")
            for key, timestamp in notifier.last_send_time.items():
                from datetime import datetime
                send_time = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                print(f"   - {key}: {send_time}")
        else:
            print(f"\n📊 最近发送记录: 暂无")
    
    print("\n" + "="*70)
    print("💡 建议:")
    print("   1. 如果频繁触发限流，增加 min_interval_seconds 值")
    print("   2. 检查是否有多个程序实例同时运行")
    print("   3. 考虑减少 notify_signals 中的信号类型")
    print("="*70 + "\n")


def test_feishu_connection():
    """测试飞书连接"""
    print("\n" + "="*70)
    print("测试飞书通知连接")
    print("="*70)
    
    notifier = get_feishu_notifier()
    
    if not notifier.enabled:
        print("\n❌ 飞书通知未启用，请在 config.yaml 中设置 enabled: true")
        return
    
    print("\n🧪 发送测试通知...")
    success = notifier.test_notification()
    
    if success:
        print("✅ 测试通知发送成功！")
    else:
        print("❌ 测试通知发送失败，请检查：")
        print("   1. Webhook URL 是否正确")
        print("   2. 网络连接是否正常")
        print("   3. 飞书机器人是否有效")
    
    print("="*70 + "\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_feishu_connection()
    else:
        check_feishu_config()
