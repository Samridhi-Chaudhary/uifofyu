"""Beginner-friendly data sanity check:  python check_data.py"""
from app import data

d = data.load()
a, f = d["actuals"], d["forecasts"]
print("ACTUALS   rows:", len(a), "| from", a.startTime.min(), "to", a.startTime.max())
print("          missing:", int(a.actual.isna().sum()), "| min/max MW:", a.actual.min(), a.actual.max())
print("FORECASTS rows:", len(f), "| publish", f.publishTime.min(), "to", f.publishTime.max())
print("          target", f.startTime.min(), "to", f.startTime.max())
print("          distinct publish times:", f.publishTime.nunique())
lead = (f.startTime - f.publishTime).dt.total_seconds() / 3600
print("          lead time h  min/median/max:", lead.min(), lead.median(), lead.max())
bad = f[lead < 0]
print("          published AFTER target time:", len(bad), f"({len(bad) / len(f) * 100:.1f}%)  <- excluded from analysis")
if len(bad):
    print("          sample of those rows:\n", bad.head(3).to_string(index=False))
print("\nSample actuals:\n", a.head(3).to_string(index=False))
print("\nSample forecasts:\n", f.head(3).to_string(index=False))
