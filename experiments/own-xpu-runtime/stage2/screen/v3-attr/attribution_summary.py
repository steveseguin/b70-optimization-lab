"""Packet-local CPU analysis; no device imports."""
import sys
from common import HERE
sys.path.insert(0, str(HERE.parent.parent / 'packet64-attribution'))
from summarize import summarize, markdown
