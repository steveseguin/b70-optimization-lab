"""CPU source generation only, without compiler or model payloads."""
if __name__=='__main__':
 from build_engine import limits
 limits()
 from full_shape import generate
 print(generate())
