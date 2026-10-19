"""Fixed packet58ag full composition; all four dimensions must be explicit."""
DIMENSIONS = {'hc_geometry':'hc-wide','experts':'wide64+halfcache','other_fusion':'fused','retirement':'ordered-foreground'}
FLAGS = {'--lookups':'resident', '--hc':'p60fusion', **{'--'+key.replace('_','-'):value for key,value in DIMENSIONS.items()}}
ARGV = [item for pair in FLAGS.items() for item in pair]
def check(command):
    for flag, value in FLAGS.items():
        if command.count(flag)!=1 or command.index(flag)+1>=len(command) or command[command.index(flag)+1]!=value:
            raise ValueError('full composition differs: '+flag)
    if '--bracket-inputs' in command:
        raise ValueError('record chain cannot use a bracket')

def check_census(censuses):
    if not isinstance(censuses,list) or len(censuses)!=1:
        raise ValueError('one-card half-table census required')
    rows=[r for r in censuses[0]['allocations'] if r.get('live') is True and r.get('label')=='card0:exact-half-decode-table']
    if len(rows)!=1 or rows[0].get('bytes')!=262144 or rows[0].get('memory')!='device' or rows[0].get('category')!='weights':
        raise ValueError('exact half-decode-table census differs')
    return 262144

def check_lookups(receipt):
    import re
    row=receipt.get('lookup_residency',{})
    expected={'token_embd.weight':521472000,'per_layer_token_embd.weight':28800138240}
    if row.get('enabled') is not True or row.get('bytes')!=sum(expected.values()):
        raise ValueError('complete resident lookup copies required')
    tensors=row.get('tensors',[])
    if len(tensors)!=2 or {t.get('name'):t.get('bytes') for t in tensors}!=expected:
        raise ValueError('resident lookup production census differs')
    for tensor in tensors:
        h=tensor.get('source_sha256','')
        if not re.fullmatch('[0-9a-f]{64}',h) or tensor.get('resident_sha256')!=h:
            raise ValueError('resident lookup byte identity differs')
    return sum(expected.values())

# >>> onecard_chain_derive generated chain flags
FLAGS.update([('--wait-policy', 'spin')])
ARGV[:] = [item for pair in FLAGS.items() for item in pair]
