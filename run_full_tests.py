"""Run the FULL demo1 test suite (chdir + sys.path like the auth runner)."""
import os
import sys

ROOT = r"C:\Users\user\Videos\demo1"
os.chdir(ROOT)
sys.path.insert(0, ROOT)

import pytest

args = ["tests", "-q", "--rootdir", ROOT]
if "--" in sys.argv:
    tail = sys.argv[sys.argv.index("--") + 1 :]
    args.extend(tail)
raise SystemExit(pytest.main(args))