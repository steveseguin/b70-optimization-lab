"""Import only authenticated immutable parent target streams, never draft results."""
import hashlib,json,shutil
from pathlib import Path
from storage import admit,digest
P=Path(__file__).resolve().parent;B=P/'build';SOURCE=P.parent/'packet38-integrated'
def main():
 rows=[]
 for name in ('incident-retrospective','code-review','customer-email','benchmark-analysis'):
  receipt=SOURCE/f'capture-input-{name}.json';row=json.loads(receipt.read_text())
  src=SOURCE/'build'/('captured-'+name);dest=B/('captured-'+name)
  table=SOURCE/'build'/('capture-'+name+'.tsv')
  assert digest(table)==row['table_sha256']
  assert digest(src/'target-rows.json')==row['target_rows_sha256']
  for leaf,expected in row['streams'].items():assert digest(src/leaf)==expected
  admit(sum(f.stat().st_size for f in src.iterdir() if f.is_file())+1_000_000)
  dest.mkdir(exist_ok=True)
  for f in src.iterdir():
   if f.is_file():
    if (dest/f.name).exists():assert digest(dest/f.name)==digest(f)
    else:shutil.copyfile(f,dest/f.name)
  lines=[]
  for line in table.read_text().splitlines():
   position,token,emit,path=line.split();leaf=Path(path).name
   assert leaf in row['streams']
   lines.append(f'{position} {token} {emit} {(dest/leaf).resolve()}')
  output=B/('capture-'+name+'.tsv');output.write_text('\n'.join(lines)+'\n')
  updated=dict(row,source=str(src),parent_receipt_sha256=digest(receipt),table_sha256=digest(output),imported_immutable_target_streams=True)
  (P/f'capture-input-{name}.json').write_text(json.dumps(updated,indent=2)+'\n')
  rows.append(dict(prompt=name,parent_receipt_sha256=digest(receipt),stream_count=len(row['streams']),table_sha256=digest(output)))
 (P/'capture-import.json').write_text(json.dumps(dict(passed=True,device_executed=False,rows=rows),indent=2)+'\n')
if __name__=='__main__':main()
