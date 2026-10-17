"""Three exact-order recurrence views on the packet75 bundle."""
VIEWS=('production','rec-gates','rec-parallel')
def views():return {n:(n,) for n in VIEWS}
def choices(name):
 if name not in VIEWS:raise ValueError('unknown packet82 choice')
 return dict(route='route-exp32-rank4',recurrence='rows4-shared' if name=='production' else name,hc='production',miss='batch',experts='wide64',packed_dense='production',hc_gate='production')
