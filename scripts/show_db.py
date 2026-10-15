"""Summary of what the collector has gathered so far.

Usage:  python scripts/show_db.py
"""
import _setup_path  # noqa: F401
from newsbot.storage import Store

store = Store()
s = store.stats()

print("=== Database ===")
print(f"Headlines stored:   {s['headlines']}  ({s['tagged']} matched to an asset)")
print(f"Price checks:       {s['checks_done']} done, {s['checks_pending']} pending, "
      f"{s['checks_missed']} missed")

print("\n=== Most mentioned assets ===")
for symbol, n in store.ticker_counts():
    print(f"  {symbol:<10} {n}")

print("\n=== Latest tagged headlines ===")
for row in store.recent_tagged(15):
    print(f"  {row['published_at'][5:16].replace('T', ' ')}  [{row['symbols']}]  {row['title'][:80]}")

moves = store.moves(30)
print("\n=== Price moves after news ===")
print("  'market' = SPY for US stocks, Bitcoin for other crypto.")
print("  'abnormal' = asset move minus market move: the part the news might explain.\n")
if not moves:
    print("  None yet. Leave `python scripts/collect.py --loop` running for an hour or so.")
else:
    print(f"  {'asset':<8} {'after':>6}  {'move':>8}  {'market':>8}  {'abnormal':>8}   headline")
for m in moves:
    fmt = lambda v: "     n/a" if v is None else f"{v:+8.3f}"  # noqa: E731
    print(f"  {m['symbol']:<8} {'+' + str(m['horizon_min']) + 'min':>6}  {fmt(m['pct'])}  "
          f"{fmt(m['bench_pct'])}  {fmt(m['abnormal_pct'])}   {m['title'][:55]}")

avg = store.average_moves()
if avg:
    print("\n=== Average size of moves (all tracked news) ===")
    for a in avg:
        print(f"  +{a['horizon_min']:>2}min  n={a['n']:<4} raw {a['avg_raw']:.3f}%   "
              f"abnormal {a['avg_abnormal']:.3f}%")
    print("  If 'abnormal' is much smaller than 'raw', most of the movement was the whole market.")
