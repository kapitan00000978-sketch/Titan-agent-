"""Run demo1's server-auth tests. Self-contained; chdirs itself, injects root.

Written to demo1 root. Invoke WITHOUT cd and without quotes:
    python C:/Users/user/Videos/demo1/run_auth_tests.py
"""
import os
import sys

ROOT = r"C:\Users\user\Videos\demo1"
os.chdir(ROOT)
sys.path.insert(0, ROOT)

import pytest

args = ["tests/test_server_auth.py", "-q", "--rootdir", ROOT]
if "--" in sys.argv:
    tail = sys.argv[sys.argv.index("--") + 1 :]
    args.extend(tail)
raise SystemExit(pytest.main(args))
