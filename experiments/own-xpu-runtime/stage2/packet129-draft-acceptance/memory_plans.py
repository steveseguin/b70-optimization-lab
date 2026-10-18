import json
from build_engine import P
def plan(v):return json.loads((P/"memory-plan.json").read_text())
