import os
import time

print("Child process started.")
print("PID:", os.getpid(), flush=True)

while True:
    print("Child is still running...", flush=True)
    time.sleep(2)
