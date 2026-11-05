# -*- coding: utf-8 -*-
"""
市场情绪数据爬虫

数据来源与写入规则（全部追加到 data/market_emotion.txt）：

1. 同花顺 https://q.10jqka.com.cn/ → 涨跌家数、涨跌停、大盘评级(score)、投资建议
   写入**当日**行。
2. 东方财富 API → 北向成交总额、南向净买额，写入当日行。
3. 上交所/深交所（akshare）→ 全市场融资余额，**滞后一个交易日公布**，
   因此回填到「数值所属交易日」的行，当日行留空。
4. 雪球「银行螺丝钉」→ 当日大盘星级(xq_star)，约 21:15-22:03 才发布，
   因此同样回填到「数值所属交易日」的行（16:00 运行时即前一交易日），当日行留空。

使用方法：
    python backtest/fetch_market_emotion.py              # 完整抓取
    python backtest/fetch_market_emotion.py --star-only  # 只补星级（跳过同花顺/融资余额）

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

# 大盘星级列名（2026-10-29 由 star 改名为 xq_star；旧名仍兼容读取与迁移）
STAR_COL = 'xq_star'
STAR_COL_ALIASES = (STAR_COL, 'star')

# market_emotion.txt 当前表头（新增列一律追加在尾部，保证历史行按列位置仍可读）
HEADER = ('date,up,down,limit_up,limit_down,zt_percent,score,suggestion,'
          'north_total,south_net,margin_balance,' + STAR_COL)

# ── 雪球「银行螺丝钉」大盘星级 ──
XQ_USER_ID = '3079173340'          # 银行螺丝钉
XQ_BOOT_URL = 'https://xueqiu.com/hq'   # 访问即下发游客 xq_a_token
XQ_TIMELINE_URL = 'https://www.xueqiu.com/statuses/original/timeline.json'
XQ_STATUS_URL = 'https://www.xueqiu.com/statuses/show.json'
XQ_UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
         '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

_XQ_SENT_SPLIT = re.compile(r'[。！？\n]')
_XQ_STAR = re.compile(r'(\d(?:\.\d)?)\s*星')
# 「距离5星」「只差2-3%就到5星」「接近4.9星」都是目标/盘中值，不是收盘星级
_XQ_SKIP_CTX = re.compile(r'(距离|只差|差.{0,3}到|接近|不到)')
_XQ_TITLE_DATE = re.compile(r'［(\d+)月(\d+)日]')


def _clean_html(text: str) -> str:
    """去掉雪球正文里的 HTML 标签"""
    return re.sub(r'<[^>]+>', '', text or '')


def extract_star(text: str) -> tuple:
    """
    从估值帖正文中提取收盘星级

    优先级：含「收盘」的句子(2) > 句尾为「回到/还在」的句子(1) > 其它(0)，
    同级取**最后一个**。这是为了避开两类陷阱：
      - 盘中值：「中午收盘，一度回到了4.5星……不过下午深V反弹，截止到收盘还在4.4星」
        → 首个星 4.5 是错的，收盘是 4.4；
      - 目标值：「距离5星已经不远了」「只差2-3%，就到5星了」→ 不是当前星级。

    Returns:
        (star, confidence, evidence)
        - star: float 或 None（正文未给出收盘星级）
        - confidence: 'high' / 'mid' / 'low' / 'none'
        - evidence: 命中的原句，供人工核对
    """
    cands = []
    for idx, sent in enumerate(_XQ_SENT_SPLIT.split(text)):
        for m in _XQ_STAR.finditer(sent):
            if _XQ_SKIP_CTX.search(sent[:m.start()][-12:]):
                continue
            if '收盘' in sent:
                prio = 2
            elif re.search(r'(回到|还在)了?$', sent[:m.start()].strip('，, ')):
                prio = 1
            else:
                prio = 0
            cands.append((prio, idx, float(m.group(1)), sent.strip()))

    if not cands:
        return None, 'none', ''

    best = max(cands, key=lambda c: (c[0], c[1]))
    return best[2], {2: 'high', 1: 'mid', 0: 'low'}[best[0]], best[3]


def _xq_session():
    """建雪球会话并取游客 token（无需登录、无需浏览器）"""
    import requests

    sess = requests.Session()
    sess.headers.update({
        'User-Agent': XQ_UA,
        'Referer': 'https://xueqiu.com/',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    })
    sess.get(XQ_BOOT_URL, timeout=20)
    if not sess.cookies.get_dict().get('xq_a_token'):
        raise RuntimeError('未取得 xq_a_token（雪球接口可能已变动）')
    return sess


def _xq_full_text(sess, status_id) -> str:
    """取正文全文（时间线的 description 常被截断到首段）"""
    try:
        resp = sess.get(XQ_STATUS_URL, params={'id': status_id}, timeout=20)
        if resp.status_code != 200:
            return ''
        return _clean_html(resp.json().get('text', ''))
    except Exception:
        return ''


def fetch_xq_star(before_date: str = '') -> dict:
    """
    取雪球「银行螺丝钉」在 before_date 之前**最新一日**的收盘星级

    数据来源：https://www.xueqiu.com/u/3079173340 的每日《[M月D日]第N期指数估值》帖。
    帖子约 21:15-22:03 发布，故 16:00 运行时能取到的总是**前一交易日**的值，
    与融资余额同样是「滞后一日、回填到数值所属交易日」。

    Args:
        before_date: 'YYYY-MM-DD'，只取该日**之前**的帖子；缺省为今天

    Returns:
        dict: { star_date, star, confidence, evidence, status_id }
        - star 为 None 表示该帖未给出收盘星级（约 4% 的交易日如此）
        取不到时返回 {}
    """
    today = before_date or datetime.now().strftime('%Y-%m-%d')
    t_year, t_month, t_day = (int(x) for x in today.split('-'))

    try:
        sess = _xq_session()
    except Exception as e:
        print(f"     ⚠ 雪球会话建立失败: {e}")
        return {}

    picks = {}   # {'YYYY-MM-DD': item}
    for page in (1, 2):
        try:
            resp = sess.get(XQ_TIMELINE_URL,
                            params={'user_id': XQ_USER_ID, 'page': page, 'count': 10},
                            timeout=20)
            resp.raise_for_status()
            items = resp.json().get('list', [])
        except Exception as e:
            print(f"     ⚠ 雪球时间线第{page}页拉取失败: {e}")
            break

        for it in items:
            desc = _clean_html(it.get('description', ''))
            if '估值' not in desc[:220]:
                continue                      # 只认每日估值帖
            m = _XQ_TITLE_DATE.search(desc)
            if not m:
                continue
            month, day = int(m.group(1)), int(m.group(2))
            year = t_year if (month, day) <= (t_month, t_day) else t_year - 1
            date_str = f'{year:04d}-{month:02d}-{day:02d}'
            if date_str >= today:
                continue                      # 只要 today 之前的
            picks.setdefault(date_str, it)

        # 已经覆盖到足够早的日期就不必翻页
        if picks and min(picks) < today and len(picks) >= 5:
            break

    if not picks:
        print(f"     ⚠ 未在雪球时间线找到 {today} 之前的估值帖")
        return {}

    star_date = max(picks)                     # 最新一日 = 前一交易日
    item = picks[star_date]
    star, conf, evidence = extract_star(_clean_html(item.get('description', ''))[:220])

    # 首段提取不到高置信值时，用全文再试一次（能救回部分被摘要截断的帖子）
    if conf != 'high':
        full = _xq_full_text(sess, item.get('id'))
        if full:
            f_star, f_conf, f_ev = extract_star(full)
            rank = {'none': 0, 'low': 1, 'mid': 2, 'high': 3}
            if rank[f_conf] > rank[conf]:
                star, conf, evidence = f_star, f_conf, f_ev

    return {
        'star_date': star_date,
        'star': star,
        'confidence': conf,
        'evidence': evidence,
        'status_id': item.get('id'),
    }


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


def _norm_cols(cols: list) -> list:
    """把表头列名归一化到当前命名（star → xq_star）"""
    return [STAR_COL if c.strip() in STAR_COL_ALIASES else c.strip() for c in cols]


def _star_index(cols: list) -> int:
    """取星级列下标；新旧列名都认，找不到返回 -1"""
    names = [c.strip() for c in cols]
    for alias in STAR_COL_ALIASES:
        if alias in names:
            return names.index(alias)
    return -1


def _migrate_header(lines: list) -> bool:
    """
    旧表头缺少尾部新增列、或星级列仍是旧名时，升级为当前 HEADER

    只允许「在尾部追加列」和「星级列改名」两种升级（列顺序不变，历史行仍可按下标读取）；
    其它结构对不上时不动表头，只告警。
    """
    old_cols = [c.strip() for c in lines[0].split(',')]
    new_cols = HEADER.split(',')
    if old_cols == new_cols:
        return False
    # 归一化列名后按「前缀」比较：既允许尾部追加列，也允许星级列改名
    n_old, n_new = _norm_cols(old_cols), _norm_cols(new_cols)
    if len(n_old) <= len(n_new) and n_new[:len(n_old)] == n_old:
        lines[0] = HEADER
        return True
    print(f"  ⚠ 表头列结构与预期不符，未自动改写: {lines[0]}")
    return False


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
    # 注意：融资余额与星级都不写入今日行，
    # 分别由 update_margin_balance / update_star_value 回填到数值所属交易日

    # 格式化一行数据（今日行的融资余额、星级留空，等待后续回填）
    def format_row():
        n = str(north_total) if north_total != '' else ''
        s = str(south_net) if south_net != '' else ''
        return (f'{today},{up},{down},{limit_up},{limit_down},{zt_pct},{score},{suggestion},'
                f'{n},{s},,')

    # 文件不存在时写入表头
    if not filepath.exists():
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(HEADER + '\n')
            f.write(format_row() + '\n')
        return

    # 检查是否已有今日数据
    lines = filepath.read_text(encoding='utf-8').splitlines()
    if not lines:
        lines = [HEADER]

    for i, line in enumerate(lines[1:], 1):
        if line.startswith(today):
            print(f"  ⚠ 今日({today})数据已存在，覆盖更新")
            lines[i] = format_row()
            _migrate_header(lines)
            filepath.write_text('\n'.join(lines) + '\n', encoding='utf-8')
            return

    # 追加新行
    _migrate_header(lines)
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


def _remind_manual_check(info: dict, reason: str, written: bool = False):
    """星级置信度不足时的醒目提醒（由用户人工确认）"""
    url = (f'https://xueqiu.com/{XQ_USER_ID}/{info["status_id"]}'
           if info.get('status_id') else f'https://www.xueqiu.com/u/{XQ_USER_ID}')
    star = info.get('star')
    print(f"\n  {'!' * 46}")
    print(f"  ⚠ 星级需人工确认：{reason}")
    print(f"     日期: {info.get('star_date')}   自动取值: {star if star is not None else '（未取到）'}")
    print(f"     状态: {'已写入，请核对' if written else '未写入，需手工补'}")
    if info.get('evidence'):
        print(f"     依据: {info['evidence'][:60]}")
    print(f"     原文: {url}")
    print(f"  {'!' * 46}")


def update_star_value(star_info: dict, filepath: Path) -> bool:
    """
    将雪球大盘星级回填到「数值所属交易日」的行

    与融资余额同一机制：星级在收盘后约 21:15-22:03 才发布，16:00 运行时
    能取到的总是前一交易日的值，因此写回前一交易日的行，当日行留空。

    写入策略（避免把散文里的近似表述当数据）：
      - high：句子里出现「收盘」→ 直接写入
      - mid ：句尾是「回到/还在」但无「收盘」字样 → 写入并提醒核对
      - low / none：只在句中提到星级（如「5星低估，通常都是带血的筹码」）→
        **不写入**，只提醒人工补，宁可缺值也不写错值

    Args:
        star_info: fetch_xq_star() 的返回值
        filepath: market_emotion.txt 路径

    Returns:
        bool: 是否写入成功
    """
    if not star_info:
        return False
    if not filepath.exists():
        print(f"  ⚠ {filepath.name} 不存在，星级未写入")
        return False

    target = star_info.get('star_date')
    star = star_info.get('star')
    conf = star_info.get('confidence')

    if star is None or conf in ('none', 'low'):
        _remind_manual_check(star_info, '正文未给出明确的收盘星级，未自动写入')
        return False

    lines = filepath.read_text(encoding='utf-8').splitlines()
    if not lines:
        return False
    _migrate_header(lines)

    col_index = _star_index(lines[0].split(','))
    if col_index < 0:
        print(f"  ⚠ 表头没有星级列（{STAR_COL}），星级未写入")
        return False

    for i, line in enumerate(lines[1:], 1):
        if line.startswith(target):
            parts = line.split(',')
            while len(parts) <= col_index:
                parts.append('')
            parts[col_index] = str(star)
            lines[i] = ','.join(parts)
            filepath.write_text('\n'.join(lines) + '\n', encoding='utf-8')
            print(f"  ⭐ 大盘星级 {star}星 → 回填到 {target}")
            if conf != 'high':
                _remind_manual_check(star_info, f'置信度={conf}', written=True)
            return True

    # 找不到对应日期的行：不新增半行，交人工判断
    _remind_manual_check(star_info, f'文件里没有 {target} 这一行')
    return False


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

    # 追加到文件（今日行不含融资余额与星级）
    emotion_file = DATA_DIR / "market_emotion.txt"
    append_to_file(data, emotion_file)

    # 融资余额回填到对应交易日
    if margin.get('margin_balance') is not None:
        update_margin_balance(margin['margin_date'], margin['margin_balance'], emotion_file)

    # ── 获取雪球大盘星级（滞后一日，回填到对应交易日） ──
    print("\n  ⭐ 正在获取雪球大盘星级...")
    try:
        star_info = fetch_xq_star()
        if star_info:
            print(f"     📅 星级对应交易日: {star_info['star_date']}"
                  f"（置信度 {star_info['confidence']}）")
            update_star_value(star_info, emotion_file)
        else:
            print("     ⚠ 星级未获取到")
    except Exception as e:
        print(f"     ⚠ 星级获取异常: {e}")

    print(f"\n  📝 已追加到: {emotion_file}")
    print(f"  ✅ 完成\n")


def run_star_only():
    """只补星级：跳过同花顺与融资余额（用于 16:00 之外的回填/补数）"""
    emotion_file = DATA_DIR / "market_emotion.txt"
    print("  ⭐ 仅补雪球大盘星级（跳过同花顺/融资余额）")
    star_info = fetch_xq_star()
    if not star_info:
        print("  ⚠ 星级未获取到\n")
        return
    print(f"  📅 星级对应交易日: {star_info['star_date']}"
          f"（置信度 {star_info['confidence']}）")
    update_star_value(star_info, emotion_file)
    print()


if __name__ == "__main__":
    if '--star-only' in sys.argv:
        print("=" * 50)
        print("  ⭐ 雪球大盘星级回填")
        print(f"  ⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)
        run_star_only()
    else:
        main()
