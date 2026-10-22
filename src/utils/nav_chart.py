# -*- coding: utf-8 -*-
"""
累计净值 vs 沪深300 对比图生成器（本地落盘）

数据源：
  - data/cumulative_nav.json   （策略累计净值，每交易日一条）
  - data/index_hs300.csv       （沪深300 日线，date,open,close,high,low,volume）

设计要点：
  1. **归一化基准固定为策略首个净值日** —— 新增一个点不会改变历史点的 Y 值，
     所以"每天整图重绘"与"只追加一个点"在数值上完全等价（PNG 本身无法追加）。
  2. **粒度自适应**：条目数 ≤250 按日、≤1000 按周（取每周最后一个）、>1000 按月。
  3. **零第三方依赖之外的可移植性**：中文字体按候选路径探测，找不到就自动退回英文标签，
     避免 Linux 服务器上中文变豆腐块。

用法：
    python -m src.utils.nav_chart                 # 生成 data/nav_curve.png
    python -m src.utils.nav_chart --granularity weekly --out data/nav_week.png
"""
from __future__ import annotations

import argparse
import bisect
import csv
import json
import sys
from datetime import date as _date
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

NAV_FILE = "cumulative_nav.json"
HS300_FILE = "index_hs300.csv"
DEFAULT_OUT = "nav_curve.png"

# 中文字体候选（Windows / Linux 常见路径）
CJK_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhl.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/arphic/uming.ttc",
]


# ---------------------------------------------------------------- 数据读取
def load_nav() -> list[tuple[str, float]]:
    """读取策略累计净值 → [(YYYY-MM-DD, nav)]，按日期升序。"""
    path = project_root / "data" / NAV_FILE
    if not path.exists():
        raise FileNotFoundError(f"未找到净值文件: {path}")
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = []
    for e in data.get("entries", []):
        if isinstance(e, dict) and e.get("date") and e.get("nav") is not None:
            rows.append((str(e["date"]), float(e["nav"])))
    rows.sort(key=lambda x: x[0])
    return rows


def load_hs300() -> list[tuple[str, float]]:
    """读取沪深300收盘价 → [(YYYY-MM-DD, close)]，按日期升序。"""
    path = project_root / "data" / HS300_FILE
    if not path.exists():
        raise FileNotFoundError(f"未找到沪深300数据: {path}")
    rows = []
    # 注意：index_hs300.csv 带 UTF-8 BOM，必须用 utf-8-sig，否则首列名会变成 "\ufeffdate"
    with open(path, "r", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            d = (r.get("date") or "").strip()
            c = (r.get("close") or "").strip()
            if not d or not c:
                continue
            try:
                rows.append((d, float(c)))
            except ValueError:
                continue
    rows.sort(key=lambda x: x[0])
    return rows


def _value_on_or_before(rows: list[tuple[str, float]], day: str) -> float | None:
    """取 rows 中 date <= day 的最后一条的值（沪深300 缺当日时用前收近似持有）。"""
    dates = [r[0] for r in rows]
    idx = bisect.bisect_right(dates, day) - 1
    return rows[idx][1] if idx >= 0 else None


# ---------------------------------------------------------------- 粒度
def auto_granularity(n: int) -> str:
    """按条目数选择粒度：少则按日，多则按周/月。"""
    if n <= 250:
        return "daily"
    if n <= 1000:
        return "weekly"
    return "monthly"


def downsample(rows: list[tuple[str, float]], granularity: str) -> list[tuple[str, float]]:
    """按粒度抽样；weekly/monthly 均取每组最后一个（= 周/月末那一条）。"""
    if granularity == "daily" or len(rows) <= 2:
        return rows
    buckets: dict = {}
    for d, v in rows:
        if granularity == "weekly":
            y, m, dd = (int(x) for x in d.split("-"))
            key = _date(y, m, dd).isocalendar()[:2]   # (ISO年, ISO周)
        else:  # monthly
            key = d[:7]
        buckets[key] = (d, v)                        # 后者覆盖前者
    return [buckets[k] for k in sorted(buckets)]


# ---------------------------------------------------------------- 画图
def _setup_cjk_font():
    """探测中文字体；返回字体名，找不到返回 None（调用方退回英文标签）。"""
    from matplotlib import font_manager
    for p in CJK_FONT_CANDIDATES:
        if not Path(p).exists():
            continue
        try:
            font_manager.fontManager.addfont(p)
            return font_manager.FontProperties(fname=p).get_name()
        except Exception:
            continue
    return None


def build_chart(out_path: str | None = None, granularity: str = "auto") -> str:
    """
    生成「策略累计净值 vs 沪深300」对比图并落盘，返回图片绝对路径。

    Args:
        out_path: 输出 PNG 路径（相对项目根或绝对）；None → data/nav_curve.png
        granularity: auto / daily / weekly / monthly
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as e:
        raise RuntimeError(
            "缺少 matplotlib，无法出图。请先安装： uv pip install matplotlib"
        ) from e

    nav_rows = load_nav()
    if not nav_rows:
        raise RuntimeError("净值序列为空，无法出图")
    hs_rows = load_hs300()
    if not hs_rows:
        raise RuntimeError("沪深300 数据为空，无法出图")

    gran = auto_granularity(len(nav_rows)) if granularity == "auto" else granularity
    nav_pts = downsample(nav_rows, gran)

    # 归一化基准 = 策略首个净值日
    base_day, base_nav = nav_pts[0]
    hs_base = _value_on_or_before(hs_rows, base_day)
    if not hs_base or base_nav <= 0:
        raise RuntimeError(f"基准日 {base_day} 数据缺失，无法归一化")

    xs, strat, hs = [], [], []
    for d, v in nav_pts:
        hv = _value_on_or_before(hs_rows, d)
        if hv is None:
            continue
        xs.append(d)
        strat.append(v / base_nav)      # 归一化净值（起点 = 1.0）
        hs.append(hv / hs_base)

    if len(xs) < 1:
        raise RuntimeError("对齐后无有效数据点")

    font_name = _setup_cjk_font()
    zh = font_name is not None
    if zh:
        plt.rcParams["font.sans-serif"] = [font_name, "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    fig, ax = plt.subplots(figsize=(10, 5.2), dpi=150)
    idx = list(range(len(xs)))
    ax.plot(idx, strat, color="#D62728", linewidth=2.0,
            label=("策略" if zh else "Strategy"), zorder=3)
    ax.plot(idx, hs, color="#8C8C8C", linewidth=1.6, linestyle="-",
            label=("沪深300" if zh else "HS300"), zorder=2)
    ax.axhline(1.0, color="#BBBBBB", linewidth=0.9, zorder=1)

    # 末端数值标注
    ax.scatter([idx[-1]], [strat[-1]], color="#D62728", s=22, zorder=4)
    ax.annotate(f"{strat[-1]:.4f}", (idx[-1], strat[-1]), textcoords="offset points",
                xytext=(-6, 8), ha="right", fontsize=9, color="#D62728")
    ax.annotate(f"{hs[-1]:.4f}", (idx[-1], hs[-1]), textcoords="offset points",
                xytext=(-6, -14), ha="right", fontsize=9, color="#8C8C8C")

    ax.set_title(
        (f"累计净值 vs 沪深300（{xs[0]} ~ {xs[-1]}，基准 {base_day}=1.0000）" if zh
         else f"NAV vs HS300 ({xs[0]} ~ {xs[-1]}, base {base_day}=1.0000)"),
        fontsize=12, pad=10)
    ax.set_ylabel("累计净值（起点 1.0）" if zh else "Net value (base 1.0)", fontsize=10)
    ax.grid(True, linestyle="--", alpha=0.35)
    ax.legend(loc="upper left", fontsize=9, framealpha=0.9)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)

    # X 轴刻度：最多 8 个，避免拥挤
    step = max(1, len(xs) // 8)
    ticks = list(range(0, len(xs), step))
    if ticks[-1] != len(xs) - 1:
        ticks.append(len(xs) - 1)
    ax.set_xticks(ticks)
    ax.set_xticklabels([xs[i][5:] for i in ticks], fontsize=8, rotation=0)

    excess = (strat[-1] - hs[-1]) * 100.0   # 净值之比差 → 收益率差（pp）
    ax.text(0.01, 0.02,
            (f"超额 {excess:+.2f}pp" if zh else f"Excess {excess:+.2f}pp"),
            transform=ax.transAxes, ha="left", va="bottom", fontsize=9,
            color="#1F77B4")

    fig.tight_layout()
    target = Path(out_path) if out_path else (project_root / "data" / DEFAULT_OUT)
    if not target.is_absolute():
        target = project_root / target
    target.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(target, format="png", bbox_inches="tight")
    plt.close(fig)
    return str(target)


def main():
    ap = argparse.ArgumentParser(description="生成策略累计净值 vs 沪深300 对比图")
    ap.add_argument("--out", default=None, help="输出 PNG 路径（默认 data/nav_curve.png）")
    ap.add_argument("--granularity", default="auto",
                    choices=["auto", "daily", "weekly", "monthly"], help="抽样粒度")
    args = ap.parse_args()
    path = build_chart(args.out, args.granularity)
    nav = load_nav()
    print(f"已生成: {path}")
    print(f"净值条目 {len(nav)} 条（{nav[0][0]} ~ {nav[-1][0]}），粒度={args.granularity}")


if __name__ == "__main__":
    main()
