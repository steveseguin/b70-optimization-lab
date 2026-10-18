"""CPU-only current-space check for the registered packet49b build and chain."""
import json
from storage import precheck

if __name__ == '__main__':
    row = precheck()
    print(json.dumps(row, indent=2))
    raise SystemExit(0 if row['passed'] else 1)
