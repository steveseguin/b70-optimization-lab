#!/usr/bin/env python3
"""Coordinator entry; --plan is CPU-only. No launch before readiness passes."""
import argparse
import sys

def main():
    import screen
    import cpu_seal
    import readiness
    control=argparse.ArgumentParser(add_help=False)
    control.add_argument('--plan',action='store_true')
    mode,_=control.parse_known_args()
    if not mode.plan:
        cpu_seal.verify()
        readiness.verify_ready()
    return screen.main(sys.argv[1:])
if __name__=='__main__':raise SystemExit(main())
