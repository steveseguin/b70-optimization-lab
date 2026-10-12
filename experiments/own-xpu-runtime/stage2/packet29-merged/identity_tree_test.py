"""CPU symbolic check: exact ordered additions, including each odd-tail +0."""
import json
from pathlib import Path
ZERO=('positive-zero',)
def reference(values):
 values=list(values)
 while len(values)>1:
  if len(values)%2:values.append(ZERO)
  values=[(values[i],values[i+1]) for i in range(0,len(values),2)]
 return values[0]
def subtree(n,begin,tile):
 values=[('leaf',begin+i) if begin+i<n else ZERO for i in range(tile)]
 stride=1
 while stride<min(n,tile):
  for i in range(0,tile,2*stride):
   if begin+i<n:values[i]=(values[i],values[i+stride] if begin+i+stride<n else ZERO)
  stride*=2
 return values[0]
def main():
 rows=[]
 for tile in (16,32):
  for n in sorted(set(range(1,514))|{639,640,641,1023,1024,1025,2047,2048,2049,2051,2559,2560,2561,4095,4096}):
   want=reference([('leaf',i) for i in range(n)])
   got=reference([subtree(n,begin,tile) for begin in range(0,n,tile)])
   if got!=want:raise AssertionError((tile,n))
   rows.append(dict(tile=tile,leaves=n,identical_ordered_expression=True))
 output=dict(passed=True,device_executed=False,checks=len(rows),meaning='structural expression equality, not tolerance or numerical samples',rows=rows)
 (Path(__file__).parent/'identity-tree-tests.json').write_text(json.dumps(output,indent=2)+'\n')
 print(str(len(rows))+' exact symbolic reduction trees pass')
if __name__=='__main__':main()
