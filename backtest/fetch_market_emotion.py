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
from datetime import datetime, timedelta
import re

# 添加项目根目录
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

DATA_DIR = project_root / "data"


def fetch_hsgt_data() -> dict:
    """从东方财富API获取沪深港通数据（北向成交总额、南向净买额）"""
    import requests as _req
    result = {}
    try:
        resp = _req.get(
            'https://push2.eastmoney.com/api/qt/kamt/get',
            params={
                'fields1': 'f1,f2,f3,f4',
                'fields2': 'f51,f52,f53,f54,f56,f60,f61,f62,f63,f65,f66',
                'ut': 'fa5fd1943c7b386f172d6893dbfba10',
            },
            headers={
                'User-Agent': 'Mozilla/5.0',
                'Referer': 'https://data.eastmoney.com/',
            },
            timeout=10
        )
        data = resp.json().get('data', {})

        # 北向资金成交总额 = 沪股通(hk2sh) + 深股通(hk2sz) 的 buySellAmt（万元→亿）
        hk2sh = data.get('hk2sh', {})
        hk2sz = data.get('hk2sz', {})
        north_total_wan = (hk2sh.get('buySellAmt', 0) or 0) + (hk2sz.get('buySellAmt', 0) or 0)
        if north_total_wan > 0:
            result['north_total'] = round(north_total_wan / 10000, 2)

        # 南向资金净买额 = 港股通(沪)(sh2hk) + 港股通(深)(sz2hk) 的 netBuyAmt（万元→亿）
        sh2hk = data.get('sh2hk', {})
        sz2hk = data.get('sz2hk', {})
        south_net_wan = (sh2hk.get('netBuyAmt', 0) or 0) + (sz2hk.get('netBuyAmt', 0) or 0)
        if 'netBuyAmt' in sh2hk or 'netBuyAmt' in sz2hk:
            result['south_net'] = round(south_net_wan / 10000, 2)

    except Exception:
        pass
    return result


def fetch_margin_balance() -> dict:
    """
    获取融资余额数据（T+1公布，取最新可用交易日）

    上海市场返回元、深圳市场返回亿元，统一转换为亿元。
    日期对齐：融资余额滞后一个交易日，取最新公布的交易日数据。

    Returns:
        dict: { margin_date, margin_balance }
        - margin_date: 融资余额对应交易日 YYYYMMDD
        - margin_balance: 全市场融资余额（亿元）
    """
    try:
        import akshare as ak
    except ImportError:
        print("     ⚠ akshare未安装，跳过融资余额")
        return {}

    result = {}
    try:
        today = datetime.now().strftime('%Y%m%d')
        start = (datetime.now() - timedelta(days=15)).strftime('%Y%m%d')

        # 1. 上海市场（返回元，取最新交易日）
        sh_df = ak.stock_margin_sse(start_date=start, end_date=today)
        if sh_df is None or sh_df.empty:
            return {}
        latest = sh_df.iloc[0]  # 已按日期倒序，最新在最前
        margin_date = str(latest['信用交易日期'])
        sh_balance_yi = float(latest['融资余额']) / 1e8  # 元→亿

        # 2. 深圳市场（返回亿元，需对齐到同一交易日）
        sz_df = ak.stock_margin_szse(date=margin_date)
        if sz_df is None or sz_df.empty:
            return {}
        sz_balance_yi = float(sz_df.iloc[0]['融资余额'])  # 已是亿

        result['margin_date'] = margin_date
        result['margin_balance'] = round(sh_balance_yi + sz_balance_yi, 2)

    except Exception as e:
        print(f"     ⚠ 融资余额获取失败: {e}")

    return result


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
    """追加数据到 market_emotion.txt（含沪深港通数据）"""
    today = datetime.now().strftime('%Y-%m-%d')
    up = data.get('up', 0)
    down = data.get('down', 0)
    limit_up = data.get('limit_up', 0)
    limit_down = data.get('limit_down', 0)
    zt_pct = data.get('zt_percent', 0.0)
    score = data.get('score', 0.0)
    suggestion = data.get('suggestion', '')
    north_total = data.get('north_total', '')
    south_net = data.get('south_net', '')
    # 注意：融资余额不写入今日行，由 update_margin_balance 回填到对应交易日

    # 新表头（含沪深港通 + 融资余额列）
    header = ('date,up,down,limit_up,limit_down,zt_percent,score,suggestion,'
              'north_total,south_net,margin_balance')

    # 格式化一行数据（今日行融资余额留空，等待回填）
    def format_row():
        n = str(north_total) if north_total != '' else ''
        s = str(south_net) if south_net != '' else ''
        return (f'{today},{up},{down},{limit_up},{limit_down},{zt_pct},{score},{suggestion},'
                f'{n},{s},')

    # 文件不存在时写入表头
    if not filepath.exists():
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(header + '\n')
            f.write(format_row() + '\n')
        return

    # 检查是否已有今日数据
    lines = filepath.read_text(encoding='utf-8').splitlines()
    old_header = lines[0] if lines else header

    for i, line in enumerate(lines[1:], 1):
        if line.startswith(today):
            print(f"  ⚠ 今日({today})数据已存在，覆盖更新")
            lines[i] = format_row()
            # 如果旧表头没有新列，更新表头
            if 'margin_balance' not in old_header:
                lines[0] = header
            filepath.write_text('\n'.join(lines) + '\n', encoding='utf-8')
            return

    # 追加：如果旧表头没有新列，更新表头；否则保持
    if 'margin_balance' not in old_header:
        lines[0] = header
    lines.append(format_row())
    filepath.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def update_margin_balance(margin_date: str, margin_balance: float, filepath: Path):
    """
    将融资余额回填到对应交易日的行

    Args:
        margin_date: 融资余额对应交易日 YYYYMMDD
        margin_balance: 全市场融资余额（亿元）
        filepath: market_emotion.txt 路径
    """
    if not filepath.exists():
        return

    # YYYYMMDD → YYYY-MM-DD
    target = f'{margin_date[:4]}-{margin_date[4:6]}-{margin_date[6:]}'

    lines = filepath.read_text(encoding='utf-8').splitlines()
    if not lines:
        return

    header = lines[0]
    # 表头如果没有 margin_balance 列，先补上
    if 'margin_balance' not in header:
        header = header.rstrip('\n') + ',margin_balance'
        lines[0] = header

    col_index = header.split(',').index('margin_balance')

    for i, line in enumerate(lines[1:], 1):
        if line.startswith(target):
            parts = line.split(',')
            # 补齐到所需列数
            while len(parts) <= col_index:
                parts.append('')
            parts[col_index] = str(margin_balance)
            lines[i] = ','.join(parts)
            filepath.write_text('\n'.join(lines) + '\n', encoding='utf-8')
            print(f"  💰 融资余额 {margin_balance:.2f}亿 → 回填到 {target}")
            return

    # 找不到对应日期的行，提示但不新增（避免缺数据的半行）
    print(f"  ⚠ 未找到 {target} 的数据行，融资余额未写入")


def main():
    print("=" * 50)
    print("  📡 同花顺市场情绪数据爬取")
    print(f"  ⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    print("\n  🚀 正在启动浏览器爬取数据...")
    try:
        data = asyncio.run(fetch_emotion_data())
    except Exception as e:
        print(f"\n  ❌ 同花顺爬取失败: {e}")
        sys.exit(1)

    print(f"\n  ✅ 同花顺数据获取成功:")
    print(f"     📈 上涨: {data['up']}只  📉 下跌: {data['down']}只")
    print(f"     🟢 涨停: {data['limit_up']}只  🔴 跌停: {data['limit_down']}只")
    print(f"     💰 昨涨停今收益: {data['zt_percent']:+.2f}%")
    if data['score']:
        print(f"     ⭐ 大盘评级: {data['score']}分")
    if data['suggestion']:
        print(f"     💡 投资建议: {data['suggestion']}")

    # ── 获取沪深港通数据 ──
    print("\n  🌏 正在获取沪深港通数据...")
    try:
        hsgt = fetch_hsgt_data()
        if hsgt.get('north_total'):
            print(f"     🏦 北向资金成交总额: {hsgt['north_total']:.2f}亿元")
            data['north_total'] = hsgt['north_total']
        else:
            print(f"     ⚠ 北向资金成交总额: 暂未更新（收盘后刷新）")
        if 'south_net' in hsgt:
            print(f"     💳 南向资金净买额: {hsgt['south_net']:+.2f}亿元")
            data['south_net'] = hsgt['south_net']
    except Exception as e:
        print(f"     ⚠ 沪深港通获取失败: {e}")

    # ── 获取融资余额数据（回填到对应交易日） ──
    print("\n  💰 正在获取融资余额数据...")
    margin = {}
    try:
        margin = fetch_margin_balance()
        if margin.get('margin_balance') is not None:
            md = margin['margin_date']
            print(f"     📅 融资余额对应交易日: {md[:4]}-{md[4:6]}-{md[6:]}")
            print(f"     💰 全市场融资余额: {margin['margin_balance']:.2f}亿元")
        else:
            print(f"     ⚠ 融资余额未获取到")
    except Exception as e:
        print(f"     ⚠ 融资余额获取异常: {e}")

    # 追加到文件（今日行不含融资余额）
    emotion_file = DATA_DIR / "market_emotion.txt"
    append_to_file(data, emotion_file)

    # 融资余额回填到对应交易日
    if margin.get('margin_balance') is not None:
        update_margin_balance(margin['margin_date'], margin['margin_balance'], emotion_file)

    print(f"\n  📝 已追加到: {emotion_file}")
    print(f"  ✅ 完成\n")


if __name__ == "__main__":
    main()
