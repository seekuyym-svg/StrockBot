# -*- coding: utf-8 -*-
"""
指数成分股数据管理模块

功能:
    1. 从 csindex.com.cn（中证指数）拉取指定指数的成分股列表
    2. 本地缓存为 CSV 文件（增量/重刷）
    3. 按配置加载成分股代码集合，支持并集/交集

数据源:
    使用 AKShare 的 index_stock_cons_csindex()，数据来源于中证指数官网

使用示例:
    from backtest.fetch_constituents import load_constituents
    codes = load_constituents(["000300", "000852"], data_dir="data", mode="union")
    # 返回 {"000001", "000002", ...} 沪深300 + 中证1000 的并集
"""

import os
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Set


# ==================== 常量 ====================

# 中证指数代码 → 显示名称 映射
INDEX_NAMES = {
    "000300": "沪深300",
    "000852": "中证1000",
    "932000": "中证2000",
    "000688": "科创50",
    "000016": "上证50",
    "000905": "中证500",
    "000906": "中证800",
}

# 默认数据目录（项目根 data/）
DEFAULT_DATA_DIR = Path(__file__).parent.parent / "data"


# ==================== 公开接口 ====================

def fetch_constituents(index_code: str) -> list[dict]:
    """
    从 csindex.com.cn 拉取指定指数的成分股列表。

    Args:
        index_code: 中证指数代码，如 "000300"（沪深300）、"000852"（中证1000）

    Returns:
        list[dict]: [{"code": "000001", "name": "平安银行"}, ...]

    Raises:
        ValueError: 指数代码无效或AKShare返回空数据
        Exception: 网络或AKShare错误
    """
    import akshare as ak

    df = ak.index_stock_cons_csindex(symbol=index_code)

    if df is None or df.empty:
        raise ValueError(f"未获取到指数 {index_code} 的成分股数据")

    # 重命名列，提取需要的字段
    stocks = []
    for _, row in df.iterrows():
        stocks.append({
            "code": str(row["成分券代码"]).zfill(6),
            "name": row["成分券名称"],
        })

    return stocks


def update_constituents(
    indices_config: list[dict],
    data_dir: str = None,
    freq_days: int = 7,
) -> bool:
    """
    按配置更新所有启用的指数成分股缓存。

    缓存规则:
        - 如果本地缓存文件在 freq_days 天内更新过，跳过
        - 否则重新拉取并覆盖写入

    Args:
        indices_config: 配置中 indices 列表，每项含 code / name / enabled
        data_dir: 缓存目录，默认 data/
        freq_days: 缓存刷新周期（天），默认 7

    Returns:
        bool: 是否全部更新成功
    """
    if data_dir is None:
        data_dir = DEFAULT_DATA_DIR
    else:
        data_dir = Path(data_dir)

    data_dir.mkdir(parents=True, exist_ok=True)

    all_success = True
    today = datetime.now()

    for idx_conf in indices_config:
        if not idx_conf.get("enabled", False):
            continue

        index_code = idx_conf["code"]
        index_name = idx_conf.get("name", INDEX_NAMES.get(index_code, index_code))

        cache_file = data_dir / f"constituents_{index_code}.csv"

        # 检查缓存是否在有效期内
        if cache_file.exists():
            try:
                cached_df = pd.read_csv(cache_file, dtype={"code": str})
                if not cached_df.empty and "update_date" in cached_df.columns:
                    last_update = pd.to_datetime(cached_df["update_date"].iloc[0])
                    days_since = (today - last_update).days
                    if days_since < freq_days:
                        print(f"[SKIP] {index_name} ({index_code}): "
                              f"上次更新 {last_update.strftime('%Y-%m-%d')}，"
                              f"距今天 {days_since} 天 < {freq_days} 天，跳过")
                        continue
            except Exception as e:
                print(f"[WARN] {index_name} 缓存读取失败 ({e})，将重新拉取")

        # 拉取新数据
        print(f"[FETCH] 正在拉取 {index_name} ({index_code}) 成分股...")
        try:
            stocks = fetch_constituents(index_code)
        except Exception as e:
            print(f"[ERROR] 拉取 {index_name} 失败: {e}")
            all_success = False
            continue

        # 保存为 CSV（确保 code 以零填充字符串格式存储，避免 pandas 转为整数）
        records = []
        for s in stocks:
            records.append({
                "code": s["code"],  # 已是6位零填充字符串
                "name": s["name"],
                "update_date": today.strftime("%Y-%m-%d"),
            })

        df = pd.DataFrame(records)
        df["code"] = df["code"].astype(str).str.zfill(6)  # 强制字符串类型
        df.to_csv(cache_file, index=False, encoding="utf-8-sig")
        print(f"[SAVE] {index_name}: {len(stocks)} 只 → {cache_file.name}")

    return all_success


def load_constituents(
    index_codes: List[str],
    data_dir: str = None,
    mode: str = "union",
) -> Set[str]:
    """
    从本地缓存加载成分股代码集合。

    Args:
        index_codes: 指数代码列表，如 ["000300", "000852"]
        data_dir: 缓存目录，默认 data/
        mode: "union"（并集）| "intersection"（交集）

    Returns:
        set[str]: 6位股票代码集合

    Raises:
        FileNotFoundError: 缓存文件不存在（需先运行 update_constituents）
    """
    if data_dir is None:
        data_dir = DEFAULT_DATA_DIR
    else:
        data_dir = Path(data_dir)

    sets = []
    for code in index_codes:
        cache_file = data_dir / f"constituents_{code}.csv"

        if not cache_file.exists():
            index_name = INDEX_NAMES.get(code, code)
            raise FileNotFoundError(
                f"[ERROR] 成分股缓存文件不存在: {cache_file.name}\n"
                f"       请先运行 update_constituents() 或 manage_stock_list.py --update"
            )

        df = pd.read_csv(cache_file, dtype={"code": str})
        code_set = set(df["code"].dropna().str.zfill(6).tolist())
        index_name = INDEX_NAMES.get(code, code)
        print(f"[LOAD] {index_name} ({code}): {len(code_set)} 只")
        sets.append(code_set)

    if not sets:
        return set()

    if mode == "intersection":
        result = sets[0].intersection(*sets[1:]) if len(sets) > 1 else sets[0]
        print(f"[MODE] 交集: {len(result)} 只")
    else:
        result = sets[0].union(*sets[1:]) if len(sets) > 1 else sets[0]
        print(f"[MODE] 并集: {len(result)} 只")

    return result


# ==================== 独立运行 ====================

def main():
    """独立运行入口：拉取指定指数的成分股并缓存"""
    import argparse

    parser = argparse.ArgumentParser(
        description="指数成分股数据拉取工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 拉取沪深300
  python backtest/fetch_constituents.py --index 000300

  # 拉取多个指数
  python backtest/fetch_constituents.py --index 000300 --index 000852 --index 932000

  # 强制刷新（无视缓存）
  python backtest/fetch_constituents.py --index 000300 --force

  # 显示已缓存的成分股
  python backtest/fetch_constituents.py --index 000300 --show
        """,
    )
    parser.add_argument("--index", type=str, action="append",
                        help="指数代码，可多次指定")
    parser.add_argument("--force", action="store_true",
                        help="强制刷新，忽略缓存有效期")
    parser.add_argument("--show", action="store_true",
                        help="显示已缓存的成分股")
    parser.add_argument("--freq", type=int, default=7,
                        help="缓存刷新周期（天），默认7天")

    args = parser.parse_args()

    if args.show and args.index:
        codes = load_constituents(args.index)
        print(f"\n共 {len(codes)} 只成分股:")
        for c in sorted(codes):
            print(f"  {c}")
        return

    if args.index:
        indices_config = [
            {"code": code, "name": INDEX_NAMES.get(code, code), "enabled": True}
            for code in args.index
        ]
        freq = 0 if args.force else args.freq
        update_constituents(indices_config, freq_days=freq)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
