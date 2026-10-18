"""Fail closed: Arm 2 attribution is not implemented by mixed-kernel events."""
import json
from pathlib import Path
P=Path(__file__).resolve().parent

def verify_ready():
    row=json.loads((P/'READY-FOR-DEVICE.json').read_text())
    if row.get('ready_for_device') is not True:raise ValueError('packet58ae device readiness incomplete')
    # Explicit code capability gate; flipping the saved boolean cannot enable it.
    raise ValueError('Arm 2 needs separate resident/miss slot timestamps; mixed events are insufficient')
