"""Verify all materialized views against their immutable source and artifact maps."""
import json
from build_engine import P,ROOT,limits
from chain_seal import check_map
from prepare_packet import proof
def main():
 limits();proof()
 for path in (P/"selections").glob("*/screen-seal.json"):
  row=json.loads(path.read_text());check_map(ROOT,row["sources"])
  for key in ("artifacts","gates","fixture_files"):check_map(path.parent,row[key])
 print("All materialized selections and cached composition proof verified")
if __name__=="__main__":main()
