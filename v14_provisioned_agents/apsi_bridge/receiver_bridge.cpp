#include <apsi/item.h>
#include <apsi/network/zmq/zmq_channel.h>
#include <apsi/receiver.h>
#include <apsi/requests.h>
#include <apsi/responses.h>
#include <apsi/thread_pool_mgr.h>
#include <array>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace {
constexpr std::size_t item_bytes = 16;
constexpr std::size_t label_bytes = 32;
void read_exact(std::istream &in, unsigned char *out, std::size_t size) {
    in.read(reinterpret_cast<char *>(out), static_cast<std::streamsize>(size));
    if (!in) {
        if (in.eof() && in.gcount() == 0) throw std::ios_base::failure("clean EOF");
        throw std::runtime_error("truncated receiver request");
    }
}
std::uint16_t u16(const unsigned char *p) { return std::uint16_t((p[0] << 8) | p[1]); }
std::uint64_t u64(const unsigned char *p) {
    std::uint64_t value = 0;
    for (std::size_t i = 0; i < 8; ++i) value = (value << 8) | p[i];
    return value;
}
void put_u16(std::ostream &out, std::uint16_t value) {
    unsigned char b[2]{static_cast<unsigned char>(value >> 8), static_cast<unsigned char>(value)};
    out.write(reinterpret_cast<char *>(b), 2);
}
void put_u64(std::ostream &out, std::uint64_t value) {
    unsigned char b[8]{};
    for (int i = 7; i >= 0; --i) { b[i] = static_cast<unsigned char>(value); value >>= 8; }
    out.write(reinterpret_cast<char *>(b), 8);
}
std::uint64_t elapsed(std::chrono::steady_clock::time_point start) {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now() - start).count();
}
}

int main(int argc, char **argv) {
    try {
        std::string endpoint;
        std::size_t threads = 1;
        for (int i = 1; i < argc; ++i) {
            std::string arg(argv[i]);
            if (arg == "--endpoint" && i + 1 < argc) endpoint = argv[++i];
            else if (arg == "--threads" && i + 1 < argc) threads = std::stoul(argv[++i]);
            else throw std::invalid_argument("invalid receiver bridge arguments");
        }
        if (endpoint.rfind("tcp://", 0) != 0 || !threads) throw std::invalid_argument("invalid endpoint");
        apsi::ThreadPoolMgr::SetThreadCount(threads);
        apsi::network::ZMQReceiverChannel channel;
        channel.connect(endpoint);
        auto params = apsi::receiver::Receiver::RequestParams(channel);
        apsi::receiver::Receiver receiver(params);
        for (;;) {
            std::array<unsigned char, 32> frame{};
            try { read_exact(std::cin, frame.data(), frame.size()); }
            catch (const std::ios_base::failure &) { return 0; }
            if (std::memcmp(frame.data(), "OAQ4", 4) || u16(frame.data()+4) != 1 || u16(frame.data()+6) != 1)
                throw std::runtime_error("invalid V14 receiver request");
            auto request_id = u64(frame.data()+8);
            apsi::Item::value_type item{};
            std::memcpy(item.data(), frame.data()+16, item_bytes);
            std::vector<apsi::Item> items{apsi::Item(item)};
            std::uint64_t m[8]{};
            auto sent = channel.bytes_sent(); auto received = channel.bytes_received();
            auto started = std::chrono::steady_clock::now();
            auto [oprf_items, label_keys] = apsi::receiver::Receiver::RequestOPRF(items, channel);
            m[4] = elapsed(started); m[0] = channel.bytes_sent()-sent; m[1] = channel.bytes_received()-received;
            started = std::chrono::steady_clock::now();
            auto [request, itt] = receiver.create_query(oprf_items);
            auto query = apsi::to_query_request(std::move(request));
            query->compr_mode = seal::compr_mode_type::none;
            request = apsi::to_request(std::move(query));
            m[5] = elapsed(started);
            sent = channel.bytes_sent(); received = channel.bytes_received(); started = std::chrono::steady_clock::now();
            channel.send(std::move(request));
            apsi::QueryResponse response;
            while (!(response = apsi::to_query_response(channel.receive_response())))
                std::this_thread::sleep_for(std::chrono::milliseconds(1));
            std::vector<apsi::ResultPart> parts;
            for (std::uint32_t i = 0; i < response->package_count; ++i) {
                auto part = channel.receive_result(receiver.get_seal_context());
                if (!part) throw std::runtime_error("invalid APSI result package");
                parts.emplace_back(std::move(part));
            }
            m[6] = elapsed(started); m[2] = channel.bytes_sent()-sent; m[3] = channel.bytes_received()-received;
            started = std::chrono::steady_clock::now();
            auto matches = receiver.process_result(label_keys, itt, parts);
            m[7] = elapsed(started);
            if (matches.size() != 1) throw std::runtime_error("APSI returned wrong result count");
            std::cout.write("OAR4", 4); put_u16(std::cout, 1); put_u16(std::cout, 1);
            put_u64(std::cout, request_id); put_u16(std::cout, 0); put_u16(std::cout, 0);
            bool found = matches[0].found;
            std::cout.put(found ? '\1' : '\0');
            std::cout.write("\0\0\0", 3);
            std::array<unsigned char, label_bytes> label{};
            if (found) {
                auto &value = matches[0].label.value();
                if (value.size() != label_bytes) throw std::runtime_error("APSI label width changed");
                std::memcpy(label.data(), value.data(), value.size());
            }
            std::cout.write(reinterpret_cast<char *>(label.data()), label.size());
            for (auto value : m) put_u64(std::cout, value);
            std::cout.flush();
        }
    } catch (const std::exception &ex) {
        std::cerr << "oae_v14_apsi_receiver_bridge: " << ex.what() << '\n';
        return 1;
    }
}
