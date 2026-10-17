"""Read-only validation of all independently sealed composition views."""
import json
from build_engine import P,ROOT,sha
from bundle_selection import views,choices
from chain_seal import check_map
def main():
 for name,v in views().items():
  root=P/'selections'/name;s=json.loads((root/'selection.json').read_text());assert s['choices']==choices(*v)
  row=json.loads((root/'screen-seal.json').read_text());check_map(ROOT,row['sources'])
  for key in ('artifacts','gates','fixture_files'):check_map(root,row[key])
 print('24 composed views verified')
if __name__=='__main__':main()
