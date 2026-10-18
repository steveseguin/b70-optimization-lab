"""Packet143 CPU gates; no inherited startup receipt is relabeled as a new run."""
def verify():
 from cpu_prepare143 import verify as cpu
 return cpu()
