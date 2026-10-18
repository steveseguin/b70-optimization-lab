"""Checked capacity overlay applied only to the new generated native entry."""
from native_source import once


def transform(text):
    text=once(text,'uint64_t cache_bytes=18000000000ull;',
        'uint64_t cache_bytes=21552729600ull;std::string cache_cap="18GB";')
    text=once(text,'    if(k=="--cache-maintenance")',
        '    if(k=="--cache-cap")a.cache_cap=value();\n    else if(k=="--cache-maintenance")')
    text=once(text,'a.cache_bytes<=18000000000ull',
        'a.cache_bytes<=21552729600ull')
    text=once(text,'  require(a.cache_maintenance=="serial"',
        '  require(a.cache_cap=="18GB"||a.cache_cap=="max","cache capacity mode");\n'
        '  require(a.mini||a.cache_bytes==21552729600ull,"single admitted maximum allocation required");\n'
        '  require(a.cache_maintenance=="serial"')
    text=once(text,'  void cache_boundary() {',r'''  void cache_capacity(const std::string& cap) {
    require(cap=="18GB"||cap=="max","cache capacity dimension");
    drain();cache_quiesce();
    require(!maintenance.running&&maintenance.state==p58v::Protocol::State::idle,"capacity boundary has unfinished work");
    a.cache_cap=cap;
    if(!expert_cache){require(a.mini,"full model requires cache");return;}
    const auto& arena=dev(0).arena.row(cache_arena);
    require(arena.live&&arena.bytes==21552729600ull,"maximum arena must remain allocated");
    expert_cache->reset_capacity(cap=="18GB"?18000000000ull:21552729600ull);
    previous_routes.clear();publish_cache_table(expert_cache->table());drain();
    require(expert_cache->resident_bytes()==0,"view must start empty");
  }
  void cache_boundary() {''')
    text=once(text,'peak_bytes<=26409219600ull,"planned card exceeds26,409,219,600 bytes"',
        'peak_bytes<=29963128848ull,"planned card exceeds admitted packet58x device bound"')
    text=once(text,'owned_bytes.at(c) + bytes <= 26409219600ull',
        'owned_bytes.at(c) + bytes <= 29963128848ull')
    text=once(text,'26,409,219,600-byte admitted device shadow budget',
        '29,963,128,848-byte admitted device allocation bound')
    text=once(text,'    e->initialize();\n    e->dev(0).before_compute=',
        '    e->initialize();e->cache_capacity(a.cache_cap);\n    e->dev(0).before_compute=')
    text=once(text,'resident[0]+=a.cache_bytes;',
        'resident[0]+=a.cache_bytes+1179648;')
    # All allocations are live at after_load. Later native work allocates no
    # additional weight arena; the supervisor also watches DRM throughout.
    text=once(text,'    record_host_memory(output,"after_load");',r'''    record_host_memory(output,"after_load");
#ifndef OWN_RT_HOST_ONLY
    {std::ifstream f(output/"drm-memory-after_load.txt");std::string line;uint64_t peak=0;bool seen=false;
      while(std::getline(f,line))if(line.starts_with("drm-total-vram0:")){
        std::istringstream row(line);std::string key,unit;uint64_t kb;row>>key>>kb>>unit;
        require(bool(row)&&unit=="KiB","DRM occupancy parse");peak=std::max(peak,kb*1024);seen=true;
      }
      require(seen&&peak<=30500000000ull,"device reserve violated before compute");
    }
#endif''')
    return text
