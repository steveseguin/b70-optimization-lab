"""Source closure is vendored, never regenerated from mutable siblings."""
def once(text,old,new):
 if text.count(old)!=1:raise ValueError('native boundary: '+old[:120])
 return text.replace(old,new,1)
