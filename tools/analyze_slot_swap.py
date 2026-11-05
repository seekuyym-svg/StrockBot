# -*- coding: utf-8 -*-
"""
科技位槽替换（月度固定验证点） —— 生产口径检验
  口径：两日持仓（买入日 B 开盘 → 次一交易日收盘），仅统计「买 ETF」的交易日
  样本：buy_decision_history.txt + .bak（2026-07-01 → 2026-11-03）
  对比：一直买 科创50 / 一直买 美国50 / 各候选替换规则
  决策只用 B-1 收盘已知信息（无未来函数）
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
import requests
import pandas as pd

H = {"User-Agent": "Mozilla/5.0"}
ROOT = Path(__file__).resolve().parent.parent   # tools/ → 项目根

def kl(mk, code, s="2026-06-01", e="2026-11-10"):
    r = requests.get("https://web.ifzq.gtimg.cn/appstock/app/fqkline/get",
                     params={"param": f"{mk}{code},day,{s},{e},200,qfq"}, headers=H, timeout=30)
    d = r.json()["data"][f"{mk}{code}"]
    k = d.get("qfqday") or d.get("day")
    return pd.DataFrame([(x[0], float(x[1]), float(x[2])) for x in k],
                        columns=["date", "open", "close"]).set_index("date")

K = kl("sh", "588080")   # 科创50
U = kl("sh", "513850")   # 美国50
CAL = sorted(set(K.index) & set(U.index))

def two_day(code_df, B):
    """买入日 B 开盘 → 次一交易日收盘"""
    if B not in CAL:
        return None
    i = CAL.index(B)
    if i + 1 >= len(CAL):
        return None
    S = CAL[i + 1]
    if B not in code_df.index or S not in code_df.index:
        return None
    o = code_df.loc[B, "open"]; c = code_df.loc[S, "close"]
    if o <= 0:
        return None
    return (c / o - 1) * 100

def prev_day(d):
    if d not in CAL:
        return None
    i = CAL.index(d)
    return CAL[i - 1] if i > 0 else None

# ── 读 history（两处）──
rows = []
for p in [ROOT / "data" / "buy_decision_history.txt.bak",
          ROOT / "data" / "buy_decision_history.txt"]:
    if not p.exists():
        continue
    for line in p.read_text(encoding="utf-8").splitlines()[1:]:
        q = line.split(",")
        if len(q) < 15:
            continue
        try:
            rows.append(dict(date=q[0], vol=float(q[2]), score=int(float(q[12])),
                             advice=q[13], act=float(q[14]) if q[14].strip() else None))
        except ValueError:
            continue
seen, uniq = set(), []
for r in sorted(rows, key=lambda x: x["date"]):
    if r["date"] not in seen:
        seen.add(r["date"]); uniq.append(r)

# ── 计算每笔的两日收益 ──
recs = []
for r in uniq:
    B = r["date"]
    rk = two_day(K, B); ru = two_day(U, B)
    if rk is None or ru is None:
        continue
    P = prev_day(B)
    dec_k = K.loc[P, "close"] if P and P in K.index else None
    recs.append(dict(date=B, score=r["score"], advice=r["advice"], act=r["act"],
                     rk=rk, ru=ru, dec_price=dec_k))
D = pd.DataFrame(recs).set_index("date")
D["diff"] = D["rk"] - D["ru"]
print(f"可用样本 {len(D)} 天（{D.index[0]} → {D.index[-1]}）")
print(f"  其中买 ETF 的 {int((D['advice']=='买ETF').sum())} 天，买股票 {int((D['advice']=='买股票').sum())} 天，空仓 {int((D['advice']=='空仓').sum())} 天")

ETF = D[D["advice"] == "买ETF"].copy()
print(f"\n买 ETF 日 {len(ETF)} 天：科创50 均值 {ETF['rk'].mean():+.2f}% / 美国50 均值 {ETF['ru'].mean():+.2f}% / 差 {ETF['diff'].mean():+.2f}pp")
print(f"  科创50 更好的天数 {int((ETF['diff']>0).sum())} / {len(ETF)}")

def cum(s):
    c = (1 + pd.Series(s) / 100).cumprod()
    return (c.iloc[-1] - 1) * 100

def mdd(s):
    c = (1 + pd.Series(s) / 100).cumprod()
    return ((c - c.cummax()) / c.cummax()).min() * 100

def evaluate(sub, mask, label):
    ret = sub["rk"].where(mask, sub["ru"])
    sw = int((mask != mask.shift(1).fillna(mask.iloc[0])).sum())
    print(f"  {label:<32}{cum(ret):>+8.2f}%{mdd(ret):>9.2f}%{int(mask.sum()):>7}{sw:>6}")
    return cum(ret)

print(f"\n{'':<32}{'累计':>9}{'MDD':>9}{'持科创':>7}{'切换':>6}")
print("  " + "-" * 62)
evaluate(ETF, pd.Series(False, index=ETF.index), "一直买 美国50（现状）")
evaluate(ETF, pd.Series(True, index=ETF.index), "一直买 科创50")

print("\n【A 绝对价格】前一日 588080 收盘 ≤ X → 买科创50")
print(f"{'':<32}{'累计':>9}{'MDD':>9}{'持科创':>7}{'切换':>6}")
for th in [1.15, 1.2, 1.25, 1.3, 1.35, 1.4]:
    evaluate(ETF, (ETF["dec_price"] <= th).fillna(False), f"价格 ≤ {th}")

print("\n【B 雪球星级】前一日 xq_star ≥ X → 买科创50")
lines = (ROOT / "data" / "market_emotion.txt").read_text(encoding="utf-8").splitlines()
hdr = lines[0].split(","); si = hdr.index("xq_star")
star = {}
for l in lines[1:]:
    q = l.split(",")
    if len(q) > si and q[si].strip():
        try: star[q[0]] = float(q[si])
        except ValueError: pass
sd = pd.Series(star).sort_index()
def star_prev(d):
    c = sd[sd.index < d]
    return c.iloc[-1] if len(c) else None
ETF["dec_star"] = [star_prev(d) for d in ETF.index]
n_star = int(ETF["dec_star"].notna().sum())
print(f"  （有前一日星级的 ETF 日 {n_star}/{len(ETF)}）")
if n_star >= 8:
    print(f"{'':<32}{'累计':>9}{'MDD':>9}{'持科创':>7}{'切换':>6}")
    sub = ETF.dropna(subset=["dec_star"])
    evaluate(sub, pd.Series(False, index=sub.index), "同区间 一直买 美国50")
    evaluate(sub, pd.Series(True, index=sub.index), "同区间 一直买 科创50")
    for th in [4.3, 4.5, 4.6]:
        evaluate(sub, sub["dec_star"] >= th, f"星级 ≥ {th}")

print("\n" + "=" * 78)
print("【逐日明细（买 ETF 日）】")
print("=" * 78)
print(f"  {'日期':<12}{'评分':>4}{'前日价':>8}{'科创':>9}{'美国50':>9}{'差':>9}  谁更好")
for d, r in ETF.iterrows():
    p = f"{r['dec_price']:.3f}" if r["dec_price"] is not None else "  -  "
    who = "科创" if r["diff"] > 0 else "美国50"
    print(f"  {d:<12}{r['score']:>4}{p:>8}{r['rk']:>+8.2f}%{r['ru']:>+8.2f}%{r['diff']:>+8.2f}pp  {who}")

print("\n" + "=" * 78)
print("【全部交易日（含买股票日）参考】样本更大，但只有 ETF 日才真正涉及替换")
print("=" * 78)
print(f"{'':<32}{'累计':>9}{'MDD':>9}{'持科创':>7}{'切换':>6}")
evaluate(D, pd.Series(False, index=D.index), "一直买 美国50")
evaluate(D, pd.Series(True, index=D.index), "一直买 科创50")
for th in [1.2, 1.3, 1.4]:
    evaluate(D, (D["dec_price"] <= th).fillna(False), f"价格 ≤ {th}")
