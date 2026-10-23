#!/usr/bin/env python3
"""Private p198 invocation of the pinned p197 compile-only recipe; no parent writes.

Default only prints commands. --compile-only requires a separately authorized
quiet build turn; model/native execution is never performed by this helper.
"""
import importlib.util
import sys
from pathlib import Path

P = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('p198_inherited_compile_recipe',
                                             P.parent / 'packet197-warm-request-front/build_engine.py')
RECIPE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RECIPE
SPEC.loader.exec_module(RECIPE)
RECIPE.P = P  # Private Python module instance; original files/module processes are untouched.
limits = RECIPE.limits
plan = RECIPE.plan
expected_dependencies = RECIPE.expected_dependencies
verify_dependencies = RECIPE.verify_dependencies

if __name__ == '__main__': RECIPE.main()
