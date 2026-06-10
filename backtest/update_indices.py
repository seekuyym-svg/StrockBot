# -*- coding: utf-8 -*-
"""
批量更新所有参考指数本地数据

从 config.yaml 的 trade_decision.indices 读取所有 enabled 的指数，
逐个执行增量更新，一次命令搞定。

使用示例:
    python backtest/update_indices.py

配置参考（config.yaml）:
    trade_decision:
      indices:
        - name: "沪深300"
          code: "1.000300"
          data_file: "data/index_hs300.csv"
          enabled: true
        - name: "科创综指"
          code: "1.000680"
          data_file: "data/index_kc.csv"
          enabled: true
"""

import sys
from pathlib import Path
import yaml

# 确保能导入 update_index_data
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backtest.update_index_data import update_index_data


def load_indices_config() -> list:
    """从 config.yaml 加载所有 enabled 的指数配置"""
    config_file = project_root / "config.yaml"
    if not config_file.exists():
        print(f"❌ config.yaml 不存在")
        return []

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            full_config = yaml.safe_load(f)

        indices = full_config.get('trade_decision', {}).get('indices', [])
        enabled = [ic for ic in indices if ic.get('enabled', True)]

        if not enabled:
            print("⚠️  trade_decision.indices 中没有启用的指数")

        return enabled

    except Exception as e:
        print(f"❌ 读取配置失败: {e}")
        return []


def main():
    print("=" * 80)
    print("  📊 批量更新参考指数数据")
    print("=" * 80)

    indices = load_indices_config()
    if not indices:
        print("\n💡 请先在 config.yaml 的 trade_decision.indices 中配置指数")
        return

    success_count = 0
    fail_count = 0

    for i, ic in enumerate(indices, 1):
        name = ic['name']
        secid = ic['code']
        data_file = ic.get('data_file')
        print(f"\n[{i}/{len(indices)}] {name} ({secid})")

        ok = update_index_data(
            index_name=name,
            secid=secid,
            output_path=data_file,
        )

        if ok:
            success_count += 1
        else:
            fail_count += 1

    print()
    print("=" * 80)
    print(f"  ✅ 完成: {success_count} 个成功", end="")
    if fail_count > 0:
        print(f"  ⚠️  {fail_count} 个失败")
    else:
        print()
    print("=" * 80)


if __name__ == "__main__":
    main()
