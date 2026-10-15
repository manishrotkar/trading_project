"""Persistence test harness.

Confirms the uploaded file survived the round-trip into the workspace
without me relying on the run_python tool (which is currently failing
with a harness-level 'signal only works in main thread' error).
"""
from pathlib import Path

target = Path("web_ui/data/uploads/hello (5).py")
print(f"exists: {target.exists()}")
print(f"size  : {target.stat().st_size} bytes")
print(f"sha256: {__import__('hashlib').sha256(target.read_bytes()).hexdigest()}")

# Re-import the module body in-process to prove the code is intact.
import importlib.util
spec = importlib.util.spec_from_file_location("hello5", str(target))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

print("module executed successfully -> print('Hello from the coding agent!') ran")
