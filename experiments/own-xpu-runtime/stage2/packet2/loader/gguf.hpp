#pragma once
#include "math.hpp"
#include "owner.hpp"
#include <filesystem>
#include <array>
#include <map>
#include <memory>
#include <variant>
namespace iq3 {
struct Meta {
  uint32_t type=0;
  std::variant<uint64_t,int64_t,double,std::string,std::vector<Meta>> value;
  uint64_t integer() const;
};
struct Tensor {
  std::string name; std::vector<uint64_t> dimensions;
  Type type; uint64_t offset,bytes;
};
struct File;
class Slice {
  std::shared_ptr<File> file_; void* mapping_=nullptr; size_t length_=0,delta_=0,size_=0;
 public:
  Slice(std::shared_ptr<File>,uint64_t offset,size_t bytes);
  ~Slice(); Slice(Slice&&) noexcept; Slice& operator=(Slice&&) noexcept;
  Slice(const Slice&)=delete; Slice& operator=(const Slice&)=delete;
  const uint8_t* data() const {return static_cast<const uint8_t*>(mapping_)+delta_;}
  size_t size() const {return size_;}
};
struct Shard {
  std::shared_ptr<File> file;
  std::string basename;
  uint64_t file_bytes=0,header_bytes=0,data_start=0,read_bytes=0;
  std::map<std::string,Meta> metadata;
  std::map<std::string,Tensor> tensors;
  explicit Shard(const std::filesystem::path&);
  Slice slice(const Tensor&,uint64_t relative,size_t bytes) const;
};
void validate_splits(const std::vector<Shard>&);
struct Planned {
  std::string shard,name,component;
  Type type; std::vector<uint64_t> dimensions;
  uint64_t offset,bytes; int layer,mask; // mask0 host,1 card0,2 card1,3 both
};
std::vector<Planned> read_plan(const std::filesystem::path&);
class Model {
 public:
  std::vector<Shard> shards;
  std::vector<Planned> plan;
  Model(const std::vector<std::filesystem::path>&,std::vector<Planned>);
  std::array<uint64_t,3> census() const; // card0, card1, host file backing
  Slice slice(const std::string&,uint64_t relative,size_t bytes) const;
  // Reservation only, no automatic full-model launch/upload. All device
  // memory enters the existing typed Arena; host lookups cannot allocate here.
  ownrt::Allocation reserve(const std::string&,unsigned card,ownrt::Device&) const;
};
}
