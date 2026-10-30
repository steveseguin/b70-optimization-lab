#!/usr/bin/env python3
"""Run a rank driver's `compare` with the exact-pattern ones checker (research/tp/prefill-draft-batch-2026-10-30/
inventory_check.py: k ones then zeros at the reset that ends a request after a reset) pre-loaded, so the driver's own
`import inventory_check` (prefill-speed-2026-10-29's all-ones form) resolves to it. Usage: compare_driver.py DRIVER.py compare A B"""
import importlib.util, runpy, sys
spec = importlib.util.spec_from_file_location('inventory_check', '/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/prefill-draft-batch-2026-10-30/inventory_check.py')
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); sys.modules['inventory_check'] = mod
driver = sys.argv[1]; sys.argv = [driver] + sys.argv[2:]
runpy.run_path(driver, run_name='__main__')
