"""CPU-only final marker writer; not imported by device admission."""
import json,shutil
from verify_ready import evaluate,O,P
if __name__=='__main__':
 assert shutil.disk_usage('/').free>=27_000_000_000,'CPU stop floor'
 row=evaluate()
 for path in (O/'ready.json',O/'READY-FOR-DEVICE.json',P/'READY-FOR-DEVICE.json'):path.write_text(json.dumps(row,indent=2)+'\n')
 print('READY files written last; no device work launched')
