# -*- coding: utf-8 -*-
"""
临时脚本：为 buy_decision_history.txt 补全 weekday（星期几）字段

- 在 date 字段后插入 weekday 列（一、二、三、四、五，周末用 六、日）
- 更新表头为17列
- 幂等：若表头已含 weekday 则跳过（避免重复执行损坏数据）
"""
from pathlib import Path
from datetime import datetime

HIST_FILE = Path(__file__).parent.parent / "data" / "buy_decision_history.txt"

NEW_HEADER = ("date,weekday,vol_ratio,kc_change,kospi_pct,score_lb,score_kc,"
              "score_ks,score_hs,raw_total,penalty,emotion_bonus,final_total,"
              "advice,actual_return,nikkei_pct,nasdaq_pct")


def weekday_of(date_str: str) -> str:
    """YYYY-MM-DD → 一/二/三/四/五/六/日"""
    return "一二三四五六日"[datetime.strptime(date_str, '%Y-%m-%d').weekday()]


def main():
    if not HIST_FILE.exists():
        print(f"❌ 文件不存在: {HIST_FILE}")
        return

    lines = HIST_FILE.read_text(encoding='utf-8').splitlines()
    if not lines:
        print("❌ 文件为空")
        return

    old_header = lines[0]
    if old_header.startswith('date,weekday'):
        print("✅ 表头已含 weekday 字段，跳过（幂等保护）")
        return

    print(f"原表头({old_header.count(',') + 1}列): {old_header}")

    new_lines = [NEW_HEADER]
    fixed = 0
    for line in lines[1:]:
        if not line.strip():
            continue
        parts = line.split(',')
        if not parts or not parts[0]:
            continue
        date_str = parts[0]
        try:
            wd = weekday_of(date_str)
        except ValueError:
            print(f"⚠️ 日期格式异常，跳过: {date_str}")
            new_lines.append(line)  # 原样保留
            continue
        parts.insert(1, wd)
        new_lines.append(','.join(parts))
        fixed += 1

    HIST_FILE.write_text('\n'.join(new_lines) + '\n', encoding='utf-8')
    print(f"✅ 已补全 {fixed} 行历史数据")
    print(f"新表头({NEW_HEADER.count(',') + 1}列): {NEW_HEADER}")


if __name__ == "__main__":
    main()
