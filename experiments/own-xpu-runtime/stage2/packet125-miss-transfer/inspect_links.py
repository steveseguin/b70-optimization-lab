"""Read-only PCIe path snapshot; no device library or config writes."""
import json,subprocess,datetime
from pathlib import Path
from build_engine import P,limits
def main():
 limits();cards=[]
 for card,bdf in enumerate(('0000:23:00.0','0000:27:00.0','0000:43:00.0','0000:47:00.0')):
  dev=Path('/sys/bus/pci/devices')/bdf;parts=[]
  for node in (dev.resolve(),*dev.resolve().parents):
   if not (node/'vendor').is_file():continue
   values={}
   for name in ('vendor','device','current_link_speed','current_link_width','max_link_speed','max_link_width','numa_node'):
    try:values[name]=(node/name).read_text().strip()
    except OSError:values[name]=None
   parts.append(dict(bdf=node.name,sysfs=str(node),**values))
  result=subprocess.run(['lspci','-D','-s',bdf,'-vv'],capture_output=True,text=True,stdin=subprocess.DEVNULL,check=True)
  cards.append(dict(physical_card=card,bdf=bdf,path_to_root=parts,lspci=result.stdout))
 (P/'evidence/pcie-links.json').write_text(json.dumps(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),read_only=True,cards=cards),indent=2)+'\n')
if __name__=='__main__':main()
