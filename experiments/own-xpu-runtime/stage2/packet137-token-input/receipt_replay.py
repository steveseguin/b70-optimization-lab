"""Portable replay from the frozen packet70 submission verifier.
Live lane admission stays on the unchanged shared v4 wrapper. The older
submission-specific adapter additionally accepts hash-bound collected bytes.
"""
import hashlib,importlib.util
from pathlib import Path
SOURCE=Path(__file__).resolve().parent.parent/'packet70-record-bundle/window_adapter.py'
EXPECTED='9e666237ca98b550093e9b7b118df4a7e8ae5778c7a57beaf4e66d20954e4845'
def verify_receipt(row,*,data):
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest()!=EXPECTED:raise ValueError('frozen receipt replay changed')
    spec=importlib.util.spec_from_file_location('packet75_frozen_receipt_replay',SOURCE)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.verify_receipt(row,data=data)
