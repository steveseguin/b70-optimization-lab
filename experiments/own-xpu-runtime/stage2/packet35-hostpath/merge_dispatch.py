#!/usr/bin/env python3
"""Merge packet26/27/28 dispatch maps against this binary's closed registry.
Later files override class choices. If a later choice supersedes an earlier
fusion, disable that fusion; a later fusion removes incompatible earlier members.
Conflicts already present inside one input are errors, never silently resolved.
"""
import argparse
import json
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
REGISTRY=json.loads((HERE/'kernel-registry.json').read_text())
SECTIONS=('classes','gemv','fusions')
SCHEMA='packet26.dispatch.v1'

def unique(pairs):
 result={}
 for key,value in pairs:
  if key in result:raise ValueError('duplicate JSON key: '+key)
  result[key]=value
 return result

def read(path):
 return json.loads(Path(path).read_text(),object_pairs_hook=unique)

def incompatible(section,key,value,fusion):
 if section=='gemv':return value!='r5'
 expected='round2' if key=='route' and fusion=='round2' else 'specialised'
 return value!=expected

def conflicts(row):
 for fusion,choice in row.get('fusions',{}).items():
  if choice=='packet18':continue
  for section,keys in REGISTRY['fusion_members'][fusion].items():
   for key in keys:
    if key in row.get(section,{}) and incompatible(section,key,row[section][key],choice):
     yield fusion,section,key

def validate(row,check_conflicts=True):
 if not isinstance(row,dict) or row.get('schema')!=SCHEMA or set(row)-set(SECTIONS)-{'schema'}:
  raise ValueError('unknown dispatch schema/fields')
 for section in SECTIONS:
  table=row.get(section,{})
  if not isinstance(table,dict):raise ValueError('dispatch section is not a map: '+section)
  for key,value in table.items():
   if not isinstance(value,str) or value not in REGISTRY[section].get(key,[]):
    raise ValueError('kernel absent from binary registry: '+section+'/'+key+'/'+str(value))
 if check_conflicts:
  found=list(conflicts(row))
  if found:raise ValueError('fusion conflicts with per-class entries: '+str(found))
 return row

def merge(rows):
 out=dict(schema=SCHEMA,classes={},gemv={},fusions={});resolutions=[]
 for index,row in enumerate(rows):
  validate(row)
  # Resolve only choices from an earlier file. New input itself must be valid.
  for fusion,choice in row.get('fusions',{}).items():
   if choice=='packet18':continue
   for section,keys in REGISTRY['fusion_members'][fusion].items():
    for key in keys:
     if key in out[section] and key not in row.get(section,{}) and incompatible(section,key,out[section][key],choice):
      del out[section][key];resolutions.append(f'input {index+1}: {fusion} supersedes earlier {section}/{key}')
  for section in ('classes','gemv'):
   for key,value in row.get(section,{}).items():
    for fusion,choice in list(out['fusions'].items()):
     if choice!='packet18' and fusion not in row.get('fusions',{}) and key in REGISTRY['fusion_members'][fusion].get(section,[]) and incompatible(section,key,value,choice):
      out['fusions'][fusion]='packet18';resolutions.append(f'input {index+1}: {section}/{key} disables earlier fusion {fusion}')
  for section in SECTIONS:out[section].update(row.get(section,{}))
  validate(out)
 return out,resolutions

def covered_by_k1(row,covered):
 validate(row)
 for section in SECTIONS:
  for key,value in row.get(section,{}).items():
   if value not in covered.get(section,{}).get(key,[]):
    raise ValueError('dispatch entry not covered by K1: '+section+'/'+key+'/'+value)
 return True

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('inputs',type=Path,nargs='+');parser.add_argument('-o','--output',type=Path,required=True)
 args=parser.parse_args();out,resolutions=merge([read(p) for p in args.inputs])
 for message in resolutions:print(message,file=sys.stderr)
 args.output.write_text(json.dumps(out,indent=2)+'\n')
if __name__=='__main__':
 try:main()
 except (OSError,ValueError,TypeError) as error:raise SystemExit(str(error))
