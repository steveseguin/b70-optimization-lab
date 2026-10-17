"""Four exact-order packet81 choices; fixed packet70 configuration."""
VIEWS=('production','gate-input-packed','down-input-packed','input-packed')
def views():return {n:(n,) for n in VIEWS}
def choices(name):
 if name not in VIEWS:raise ValueError('unknown packet81 choice')
 return dict(route='route-exp32-rank4',recurrence='rows4-shared',hc='production',miss='batch',experts='wide64' if name=='production' else name,packed_dense='production',hc_gate='production')
