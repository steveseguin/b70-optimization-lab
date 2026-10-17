"""Five registered small-kernel views; fixed packet70 record configuration."""
VIEWS=('production','route-fast','norm-fused','small-combined','small+hc-wide')
def views():return {n:(n,) for n in VIEWS}
def choices(name):
    if name not in VIEWS:raise ValueError('unregistered packet78 view')
    return dict(route='route-fast' if name in ('route-fast','small-combined','small+hc-wide') else 'route-exp32-rank4',
                recurrence='rows4-shared',hc='production',miss='batch',experts='wide64',packed_dense='production',
                hc_gate='wide' if name=='small+hc-wide' else 'production',
                hc_norm='subgroup' if name in ('norm-fused','small-combined','small+hc-wide') else 'production')
