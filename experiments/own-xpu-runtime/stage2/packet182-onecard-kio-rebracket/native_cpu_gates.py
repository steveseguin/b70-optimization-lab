"""Inherited native gates are checked by seal.py; no full-shape execution here."""
from seal import sha
def main():
    raise SystemExit("REFUSED: packet58ah inherits hash-bound packet58ag CPU proofs; use seal.py --verify")
if __name__=="__main__":main()
