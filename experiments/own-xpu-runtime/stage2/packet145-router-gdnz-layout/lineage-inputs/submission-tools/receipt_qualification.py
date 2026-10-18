"""A diagnostic receipt can never become publication or submission evidence."""
import json
from pathlib import Path
def require_qualifying(value):
    if isinstance(value, dict):
        if value.get('diagnostic_unsealed') or value.get('qualifying') is False:
            raise ValueError('diagnostic/unqualified receipt cannot be submitted, published or promoted')
        for child in value.values():
            require_qualifying(child)
    elif isinstance(value, list):
        for child in value:
            require_qualifying(child)
def require_qualifying_file(path):
    path = Path(path)
    if path.suffix == '.json':
        require_qualifying(json.loads(path.read_text()))
