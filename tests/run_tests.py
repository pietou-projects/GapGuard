"""Offline tests only. No connection to a printer."""
from pathlib import Path
import sys, unittest
sys.dont_write_bytecode=True
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root.parent/'src'))
sys.path.insert(0,str(root))
suite=unittest.defaultTestLoader.discover(str(root),pattern='test_*.py')
result=unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(not result.wasSuccessful())
