// tokhelper: the Inkling-2 tokenizer from llama.cpp (Unsloth release b12588-mix; vocabulary only, no weights), for the LAN server.
// stdin lines -> stdout lines:
//   T <hex of UTF-8 text>   -> I <id> <id> ...     (special tokens in the text are parsed; no BOS added)
//   V                       -> N <count>, then one line per token id: <hex of the token's bytes>
// usage: tokhelper <model.gguf (first shard)>
#include "llama.h"
#include <cstdio>
#include <iostream>
#include <string>
#include <vector>

static std::string unhex(const std::string &h) {
    std::string s;
    s.reserve(h.size() / 2);
    for (size_t i = 0; i + 1 < h.size(); i += 2) s.push_back((char)std::stoi(h.substr(i, 2), nullptr, 16));
    return s;
}
static std::string hex(const std::string &s) {
    static const char *d = "0123456789abcdef";
    std::string h;
    h.reserve(s.size() * 2);
    for (unsigned char c : s) h.push_back(d[c >> 4]), h.push_back(d[c & 15]);
    return h;
}
int main(int argc, char **argv) {
    if (argc < 2) { std::fprintf(stderr, "usage: tokhelper model.gguf\n"); return 2; }
    llama_log_set([](ggml_log_level, const char *, void *) {}, nullptr);
    llama_backend_init();
    llama_model_params mp = llama_model_default_params();
    mp.vocab_only = true;
    llama_model *m = llama_model_load_from_file(argv[1], mp);
    if (!m) { std::fprintf(stderr, "tokhelper: cannot load %s\n", argv[1]); return 1; }
    const llama_vocab *v = llama_model_get_vocab(m);
    std::ios::sync_with_stdio(false);
    std::string line;
    std::vector<llama_token> ids;
    while (std::getline(std::cin, line)) {
        if (line.size() >= 2 && line[0] == 'T' && line[1] == ' ') {
            const std::string text = unhex(line.substr(2));
            ids.resize(text.size() + 16);
            int n = llama_tokenize(v, text.data(), (int32_t)text.size(), ids.data(), (int32_t)ids.size(), false, true);
            if (n < 0) { ids.resize(-n); n = llama_tokenize(v, text.data(), (int32_t)text.size(), ids.data(), (int32_t)ids.size(), false, true); }
            std::string o = "I";
            for (int i = 0; i < n; ++i) o += " " + std::to_string(ids[i]);
            std::cout << o << "\n" << std::flush;
        } else if (line == "V") {
            const int nv = llama_vocab_n_tokens(v);
            std::cout << "N " << nv << "\n";
            char buf[512];
            for (int t = 0; t < nv; ++t) {
                int n = llama_token_to_piece(v, t, buf, sizeof buf, 0, true);
                std::string piece = n > 0 ? std::string(buf, (size_t)n) : std::string();
                std::cout << hex(piece) << "\n";
            }
            std::cout << std::flush;
        } else {
            std::cout << "E unknown\n" << std::flush;
        }
    }
    llama_model_free(m);
    return 0;
}
