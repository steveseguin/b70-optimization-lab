#!/usr/bin/env python3
"""Submission preparation for packet196-onecard-diet-chain: read-only on the chain, never posts, never touches a key.

  prepare_submission.py --chain <packet>/evidence/card0-diet-a --output <packet>/submission/prepared-a
      replays the finished chain through the packet's sealed validator (packet58_submission.py: 7 windows, oracle exactness,
      fresh processes, whole-host admission, the max23 capacity argv, full_cache_bytes 23,049,601,024, WS128 above the pinned
      ledger 36.60251162011413 / cmvkcqznb002lng01fsrhjn7t) and writes evidence.json.gz, result.json, promotion-attestation.json,
      result-packet.md (128-token capped scope and the exact expert gateup instruction diet with unchanged 23.05 GB capacity disclosed) and payload-queue.json LAST.
  prepare_submission.py --update-record <prepared-a>/result.json --submission-id <ID>
      after an APPROVED submission only: appends the record to scripts/packet58_onecard_record_threshold.json (improvement only;
      the validator refuses a non-improving value). Never run before the receipt shows HTTP 201 with an id.
Both forms run the packet's own module from its final location under a 4 GiB address-space limit on the helper cores.
"""
import os, resource, sys
from pathlib import Path

ROOT = Path('/home/steve/llm-optimizations')
P = ROOT / 'experiments/own-xpu-runtime/stage2/packet196-onecard-diet-chain'
CHAIN = P / 'evidence/card0-diet-a'


def main():
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024 ** 3, 4 * 1024 ** 3))
    argv = sys.argv[1:]
    if '--update-record' not in argv:
        if '--chain' in argv:
            given = Path(argv[argv.index('--chain') + 1]).resolve()
            if given != CHAIN.resolve():
                print(f'REFUSED: only the registered chain output {CHAIN} is admitted', file=sys.stderr)
                return 2
        else:
            argv = ['--chain', str(CHAIN), *argv]
        if '--output' in argv:
            out = Path(argv[argv.index('--output') + 1]).resolve()
            if not out.is_relative_to((P / 'submission').resolve()):
                print(f'REFUSED: --output must sit under {P / "submission"}', file=sys.stderr)
                return 2
    os.chdir(ROOT)
    sys.path.insert(0, str(P))
    import packet58_submission as S
    try:
        return S.main(argv)
    except (ValueError, OSError, KeyError, TypeError, EOFError) as error:
        print('REFUSED: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
