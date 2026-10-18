"""Derive selected-view checks from packet114 without changing frozen files."""
from pathlib import Path
from build_engine import P,STAGE,save,sha,ROOT,limits
def main():
 limits();source=STAGE/'packet114-draft-prefix';pins={}
 for name in ('startup114.py','kd_reference114.py','limit_gate.py'):
  path=source/name;text=path.read_text().replace('packet103','packet111').replace('packet114','packet116').replace('startup114','startup116').replace('kd_reference114','kd_reference116')
  if name=='startup114.py':
   start=text.index("  if (dest/'draft-prefix.json').exists():")
   end=text.index("  if (dest/'draft-kernel-choices.json').exists():",start)
   text=text[:start]+text[end:]
   text=text.replace("--startup116","--startup109").replace("evidence/startup116.json","evidence/startup.json")
  if name=='limit_gate.py':text=text.replace('ROOT=P.parents[3]','ROOT=P.parents[4]')
  target=P/name.replace('114','116');target.write_text(text);pins[str(path.relative_to(ROOT))]=sha(path)
 save(P/'check-copy-provenance.json',pins)
if __name__=='__main__':main()
