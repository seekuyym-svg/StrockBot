# -*- coding: utf-8 -*-
"""
同花顺市场情绪数据爬虫

从 https://q.10jqka.com.cn/ 获取涨跌家数、涨跌停、大盘评级等数据，
追加到 data/market_emotion.txt 中。

使用方法：
    python tools/fetch_market_emotion.py

依赖：
    pip install playwright
    playwright install chromium
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime
import re

# 添加项目根目录
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

DATA_DIR = project_root / "data"


async def fetch_emotion_data() -> dict:
    """从同花顺页面爬取市场情绪数据"""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        page = await context.new_page()
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)

        await page.goto('https://q.10jqka.com.cn/', timeout=30000, wait_until='networkidle')
        await page.wait_for_timeout(5000)

        text = await page.inner_text('body')
        await browser.close()

    # ── 解析数据 ──
    result = {}

    # 涨跌家数
    m = re.search(r'上涨[：:]\s*(\d+)\s*只\s*下跌[：:]\s*(\d+)\s*只', text)
    if m:
        result['up'] = int(m.group(1))
        result['down'] = int(m.group(2))
    else:
        raise ValueError(f"未找到涨跌家数数据")

    # 涨跌停
    m = re.search(r'涨停[：:]\s*(\d+)\s*只\s*跌停[：:]\s*(\d+)\s*只', text)
    if m:
        result['limit_up'] = int(m.group(1))
        result['limit_down'] = int(m.group(2))
    else:
        raise ValueError(f"未找到涨跌停数据")

    # 昨涨停今收益
    m = re.search(r'今收益[：:]\s*([\d.+-]+)%', text)
    if m:
        result['zt_percent'] = float(m.group(1))
    else:
        result['zt_percent'] = 0.0

    # 大盘评级
    m = re.search(r'大盘评级[：:\s]*([\d.]+)分', text)
    if m:
        result['score'] = float(m.group(1))
    else:
        result['score'] = 0.0

    # 投资建议
    m = re.search(r'投资建议[：:\s]*([^\n]+)', text)
    if m:
        result['suggestion'] = m.group(1).strip()
    else:
        result['suggestion'] = ''

    return result


def append_to_file(data: dict, filepath: Path):
    """追加数据到 market_emotion.txt"""
    today = datetime.now().strftime('%Y-%m-%d')
    up = data.get('up', 0)
    down = data.get('down', 0)
    limit_up = data.get('limit_up', 0)
    limit_down = data.get('limit_down', 0)
    zt_pct = data.get('zt_percent', 0.0)
    score = data.get('score', 0.0)
    suggestion = data.get('suggestion', '')

    # 文件不存在时写入表头
    if not filepath.exists():
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('date,up,down,limit_up,limit_down,zt_percent,score,suggestion\n')

    # 检查是否已有今日数据
    lines = filepath.read_text(encoding='utf-8').splitlines()
    for line in lines[1:]:
        if line.startswith(today):
            print(f"  ⚠ 今日({today})数据已存在，覆盖更新")
            # 覆盖
            new_lines = [lines[0]]
            for line in lines[1:]:
                if not line.startswith(today):
                    new_lines.append(line)
            new_lines.append(f'{today},{up},{down},{limit_up},{limit_down},{zt_pct},{score},{suggestion}')
            filepath.write_text('\n'.join(new_lines) + '\n', encoding='utf-8')
            return

    # 追加
    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(f'{today},{up},{down},{limit_up},{limit_down},{zt_pct},{score},{suggestion}\n')


def main():
    print("=" * 50)
    print("  📡 同花顺市场情绪数据爬取")
    print(f"  ⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    print("\n  🚀 正在启动浏览器爬取数据...")
    try:
        data = asyncio.run(fetch_emotion_data())
    except Exception as e:
        print(f"\n  ❌ 爬取失败: {e}")
        sys.exit(1)

    print(f"\n  ✅ 获取成功:")
    print(f"     📈 上涨: {data['up']}只  📉 下跌: {data['down']}只")
    print(f"     🟢 涨停: {data['limit_up']}只  🔴 跌停: {data['limit_down']}只")
    print(f"     💰 昨涨停今收益: {data['zt_percent']:+.2f}%")
    if data['score']:
        print(f"     ⭐ 大盘评级: {data['score']}分")
    if data['suggestion']:
        print(f"     💡 投资建议: {data['suggestion']}")

    # 追加到文件
    emotion_file = DATA_DIR / "market_emotion.txt"
    append_to_file(data, emotion_file)
    print(f"\n  📝 已追加到: {emotion_file}")
    print(f"  ✅ 完成\n")


if __name__ == "__main__":
    main()
