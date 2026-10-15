"""One-off sanity check for the new nifty50_expiries.py logic."""
import calendar
import datetime

from nifty50_expiries import expiries_list, next_expiry

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
TUESDAY = calendar.TUESDAY  # 1

# Today (01-Oct-2026) is a Thursday: offset 0 must be the NEXT Tuesday,
# 06-Oct-2026 (per the corrected expiry calendar).
assert next_expiry(datetime.date(2026, 10, 1), 0) == "06-Oct-2026"
# A Tuesday rolls to itself: the contract expiring that day is the nearest.
assert next_expiry(datetime.date(2026, 10, 6), 0) == "06-Oct-2026"
# Wednesday 07-Oct-2026: the day after a Tuesday, next expiry is 13-Oct-2026.
assert next_expiry(datetime.date(2026, 10, 7), 0) == "13-Oct-2026"
# Monday 05-Oct-2026: the upcoming Tuesday 06-Oct-2026 is still ahead.
assert next_expiry(datetime.date(2026, 10, 5), 0) == "06-Oct-2026"
# Consecutive offsets are always exactly 7 days apart, all Tuesdays.
for d in (datetime.date(2026, 10, 1), datetime.date(2026, 10, 6),
          datetime.date(2026, 10, 7)):
    dates = [datetime.datetime.strptime(s, "%d-%b-%Y").date()
             for s in expiries_list(3)]
    assert all(x.weekday() == TUESDAY for x in dates)
    assert all(b - a == datetime.timedelta(days=7)
               for a, b in zip(dates, dates[1:]))
    assert dates == sorted(dates)

today = datetime.date.today()
print(f"today is {today} ({WEEKDAYS[today.weekday()]})")
for s in expiries_list(3):
    d = datetime.datetime.strptime(s, "%d-%b-%Y").date()
    print(f"  {s}  {WEEKDAYS[d.weekday()]}")
print("all sanity checks passed")
