from census_contract import P,read,require
from build_engine import sha
def verify():
    seal=read(P/'seal.json')
    for name,digest in seal['files_sha256'].items():
        f=P/name;require(f.resolve().is_relative_to(P),'private seal escapes packet')
        require(sha(f)==digest,'private seal changed: '+name)
    return seal
