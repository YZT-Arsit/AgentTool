#include <apsi/item.h>
#include <apsi/oprf/oprf_sender.h>
#include <apsi/psi_params.h>
#include <apsi/sender_db.h>
#include <array>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace {
constexpr std::size_t item_bytes = 16;
constexpr std::size_t label_bytes = 32;
constexpr std::size_t apsi_nonce_bytes = 16;

std::uint32_t read_u32_be(std::istream &in) {
    std::array<unsigned char, 4> b{};
    in.read(reinterpret_cast<char *>(b.data()), 4);
    if (!in) throw std::runtime_error("truncated sender input header");
    return (std::uint32_t(b[0]) << 24) | (std::uint32_t(b[1]) << 16) |
           (std::uint32_t(b[2]) << 8) | std::uint32_t(b[3]);
}
std::string read_text(const std::string &path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) throw std::runtime_error("cannot open APSI parameter file");
    return std::string(std::istreambuf_iterator<char>(in), {});
}
}

int main(int argc, char **argv) {
    try {
        if (argc != 5) {
            std::cerr << "usage: oae_v14_apsi_sender_db_builder PARAMS INPUT OUTPUT STATS\n";
            return 2;
        }
        auto params = apsi::PSIParams::Load(read_text(argv[1]));
        std::ifstream input(argv[2], std::ios::binary);
        std::array<char, 8> magic{};
        input.read(magic.data(), 8);
        if (!input || std::string(magic.data(), 8) != "OAEDB014")
            throw std::runtime_error("invalid V14 sender input magic");
        auto count = read_u32_be(input);
        auto item_width = read_u32_be(input);
        auto label_width = read_u32_be(input);
        if (count == 0 || count > 100000 || item_width != item_bytes || label_width != label_bytes)
            throw std::runtime_error("sender input violates V14 100K/16/32 profile");
        std::vector<std::pair<apsi::Item, apsi::Label>> records;
        records.reserve(count);
        for (std::uint32_t i = 0; i < count; ++i) {
            apsi::Item::value_type item{};
            input.read(reinterpret_cast<char *>(item.data()), item.size());
            apsi::Label label(label_bytes);
            input.read(reinterpret_cast<char *>(label.data()), label.size());
            if (!input) throw std::runtime_error("truncated V14 sender record");
            records.emplace_back(apsi::Item(item), std::move(label));
        }
        if (input.peek() != std::char_traits<char>::eof())
            throw std::runtime_error("trailing V14 sender input bytes");
        auto started = std::chrono::steady_clock::now();
        apsi::sender::SenderDB sender_db(params, label_bytes, apsi_nonce_bytes, true);
        sender_db.set_data(records);
        auto key = sender_db.strip();
        auto prepared = std::chrono::steady_clock::now();
        std::ofstream output(argv[3], std::ios::binary | std::ios::trunc);
        auto bytes = sender_db.save(output);
        key.save(output);
        bytes += apsi::oprf::oprf_key_size;
        output.flush();
        if (!output) throw std::runtime_error("failed writing APSI SenderDB");
        auto ns = std::chrono::duration_cast<std::chrono::nanoseconds>(prepared - started).count();
        std::ofstream stats(argv[4], std::ios::trunc);
        stats << "{\n  \"real_cryptographic_backend\": true,\n"
              << "  \"sender_records\": " << count << ",\n"
              << "  \"item_bytes\": 16,\n  \"label_bytes\": 32,\n"
              << "  \"apsi_label_nonce_bytes\": 16,\n"
              << "  \"preprocessing_ns\": " << ns << ",\n"
              << "  \"serialized_sender_db_bytes\": " << bytes << "\n}\n";
        return stats ? 0 : 1;
    } catch (const std::exception &ex) {
        std::cerr << "oae_v14_apsi_sender_db_builder: " << ex.what() << '\n';
        return 1;
    }
}
