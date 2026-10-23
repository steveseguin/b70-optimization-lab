#!/usr/bin/env python3
"""LocalMaxxing submission CLI for packet196-onecard-diet-chain, with receipts (coordinator only for anything but --dry-run).

  submission.py --payloads <prepared-a>/payload-queue.json --dry-run          local preflight + the packet58aj scope validator; no key, no
                                                                               network; the projected queue is also saved as <prepared-a>/local-dry-run.json
  submission.py --payloads ... --server-dry-run                                authenticated no-write validation (LMX_API_KEY or ~/.config/localmaxxing/api_key)
  submission.py --payloads ...                                                 the real submit (HTTP 201 + id/status), once
Every --server-dry-run / real run appends a receipt to data/localmaxxing-responses/<utc date>-packet196-onecard-diet-chain-a-onecard-ws128.txt
with key material filtered: the key is never read here, and any output line that names the key variable, the key file, an Authorization
header or a bearer token is replaced by a marker before it reaches the receipt or the terminal.
The packet's sealed submission_cli.py (shared CLI + packet58_submission validator) does all checks; this wrapper only adds the refusal of a
foreign payload directory, the address-space limit and the receipt.
"""
import datetime, io, json, re, resource, sys
from pathlib import Path

ROOT = Path('/home/steve/llm-optimizations')
P = ROOT / 'experiments/own-xpu-runtime/stage2/packet196-onecard-diet-chain'
RECEIPTS = ROOT / 'data/localmaxxing-responses'
SECRET = re.compile(r'LMX_API_KEY|api_key|Authorization|Bearer\s+\S+|x-api-key', re.I)


class Tee(io.TextIOBase):
    def __init__(self, stream, lines):
        self.stream, self.lines = stream, lines

    def write(self, s):
        for line in s.splitlines(keepends=True):
            if SECRET.search(line):
                line = '[line withheld: key material]\n'
            self.stream.write(line)
            self.lines.append(line)
        return len(s)

    def flush(self):
        self.stream.flush()


def main():
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024 ** 3, 4 * 1024 ** 3))
    argv = sys.argv[1:]
    if '--payloads' not in argv:
        print('usage: submission.py --payloads <prepared>/payload-queue.json [--dry-run | --server-dry-run] [--label L]', file=sys.stderr)
        return 64
    payloads = Path(argv[argv.index('--payloads') + 1]).resolve()
    if not payloads.is_relative_to((P / 'submission').resolve()):
        print(f'REFUSED: payloads must sit under {P / "submission"}', file=sys.stderr)
        return 2
    mode = 'local-dry-run' if '--dry-run' in argv else 'server-dry-run' if '--server-dry-run' in argv else 'submit'
    sys.path.insert(0, str(P))
    import submission_cli
    cli = submission_cli.load_submitter()
    assert cli.REPO_ROOT == ROOT, cli.REPO_ROOT
    lines = []
    out, err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = Tee(out, lines), Tee(err, lines)
    sys.argv = ['submission_cli.py', *argv]
    try:
        rc = cli.main()
    finally:
        sys.stdout, sys.stderr = out, err
    text = ''.join(lines)
    if mode == 'local-dry-run':
        if rc == 0:
            try:
                (payloads.parent / 'local-dry-run.json').write_text(json.dumps(json.loads(text), indent=2) + '\n')
            except ValueError:
                pass
        return rc
    RECEIPTS.mkdir(exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc)
    receipt = RECEIPTS / f'{stamp:%Y-%m-%d}-packet196-onecard-diet-chain-a-onecard-ws128.txt'
    with receipt.open('a') as f:
        f.write(f'# {stamp.isoformat()} mode={mode} payloads={payloads.relative_to(ROOT)} rc={rc} (key lines filtered)\n{text}\n')
    print(f'receipt appended: {receipt.relative_to(ROOT)}')
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
