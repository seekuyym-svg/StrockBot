# -*- coding: utf-8 -*-
"""清理Python文件中的不可见控制字符"""
import os
import re
import sys


def clean_file(filepath):
    """
    清理文件中的不可见控制字符（保留换行符、制表符等常用空白字符）
    
    Args:
        filepath: 文件路径
    """
    print(f"处理文件: {filepath}")
    
    # 读取原始文件
    with open(filepath, 'rb') as f:
        original_content = f.read()
    
    original_size = len(original_content)
    
    # 移除所有控制字符，但保留：
    # \t (0x09) - 制表符
    # \n (0x0A) - 换行符
    # \r (0x0D) - 回车符
    cleaned_content = re.sub(b'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', b'', original_content)
    
    cleaned_size = len(cleaned_content)
    removed_count = original_size - cleaned_size
    
    if removed_count > 0:
        print(f"  ⚠️  发现并移除了 {removed_count} 个控制字符")
        
        # 备份原文件
        backup_path = filepath + '.backup'
        with open(backup_path, 'wb') as f:
            f.write(original_content)
        print(f"  💾 已备份原文件到: {backup_path}")
        
        # 写入清理后的内容
        with open(filepath, 'wb') as f:
            f.write(cleaned_content)
        print(f"  ✅ 文件已清理并保存")
    else:
        print(f"  ✓ 文件干净，无需清理")
    
    return removed_count


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python clean_control_chars.py <文件路径>")
        print("示例: python clean_control_chars.py src/utils/scheduler.py")
        sys.exit(1)
    
    filepath = sys.argv[1]
    
    if not os.path.exists(filepath):
        print(f"❌ 错误: 文件不存在 - {filepath}")
        sys.exit(1)
    
    try:
        removed = clean_file(filepath)
        print(f"\n{'='*60}")
        if removed > 0:
            print(f"✅ 清理完成！共移除 {removed} 个控制字符")
            print(f"⚠️  请重新测试程序")
        else:
            print(f"✅ 文件检查完成，未发现控制字符")
        print(f"{'='*60}")
    except Exception as e:
        print(f"❌ 处理失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
