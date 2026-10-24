#!/usr/bin/env python3
"""Explicit four remaining closed batches; smaller temporary quota, same floor."""
import hashlib,importlib.util,sys
from pathlib import Path
P=Path(__file__).resolve().parent
SOURCE=P/'closed_attention_bins.py'
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()=='b652f0b40c55346b10a4044c2c44eef4cadc209128676e9609a5eb77572a3933'
s=importlib.util.spec_from_file_location('fixed_attention_archive',SOURCE);A=importlib.util.module_from_spec(s);s.loader.exec_module(A)
original_authority=A.authority
CAP=256*1024**2
def authority(profile,batch):
 A.require(profile=='completion' and type(batch)is int and batch in (9,10,11,12),'only four remaining completion groups')
 j=original_authority(profile,batch)
 A.require(len(j.rows)==2113 and sum(x['bytes'] for x in j.rows.values())==231442500,'unchanged fixed group')
 # Conservative tar/gzip/stat overhead allowance exceeds observed headers.
 A.require(sum(x['bytes'] for x in j.rows.values())+len(j.rows)*8192+1024**2<CAP,'raw payload plus conservative container overhead fits quota')
 j.cap=CAP
 j.authority.update(quota_policy_sha256=A.B.sha(__file__),archive_quota=CAP,unchanged_floor=j.floor)
 return j
A.authority=authority
if __name__=='__main__':
 A.require('--plan' not in sys.argv,'use original plan plus quota-policy record')
 A.main()
