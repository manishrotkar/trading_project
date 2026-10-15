"""One-off probe: what does 'today' look like in this environment?"""
import datetime
import time

print("local now   :", datetime.datetime.now().isoformat())
print("UTC now     :", datetime.datetime.utcnow().isoformat())
print("local date  :", datetime.date.today().isoformat())
print("weekday     :", datetime.date.today().strftime("%A"), "(0=Mon..6=Sun:", datetime.date.today().weekday(), ")")
print("epoch       :", time.time())
