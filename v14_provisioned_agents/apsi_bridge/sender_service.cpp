#include <apsi/network/zmq/zmq_channel.h>
#include <apsi/oprf/oprf_sender.h>
#include <apsi/query.h>
#include <apsi/requests.h>
#include <apsi/sender.h>
#include <apsi/sender_db.h>
#include <chrono>
#include <fstream>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <thread>
using namespace std::chrono_literals;

namespace {
std::uint64_t elapsed(std::chrono::steady_clock::time_point start) {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now() - start).count();
}
void metric(std::ofstream &out, const char *kind, std::uint64_t ordinal, std::uint64_t ns) {
    out << "{\"kind\":\"" << kind << "\",\"ordinal\":" << ordinal
        << ",\"duration_ns\":" << ns << "}\n"; out.flush();
}
}

int main(int argc, char **argv) {
    try {
        std::string db_path, metrics_path; int port = 1212;
        for (int i = 1; i < argc; ++i) {
            std::string arg(argv[i]);
            if (arg == "--db" && i+1 < argc) db_path = argv[++i];
            else if (arg == "--metrics" && i+1 < argc) metrics_path = argv[++i];
            else if (arg == "--port" && i+1 < argc) port = std::stoi(argv[++i]);
            else throw std::invalid_argument("invalid sender service arguments");
        }
        std::ifstream db_file(db_path, std::ios::binary);
        auto [loaded, ignored] = apsi::sender::SenderDB::Load(db_file); (void)ignored;
        apsi::oprf::OPRFKey key; key.load(db_file);
        auto db = std::make_shared<apsi::sender::SenderDB>(std::move(loaded));
        std::ofstream metrics(metrics_path, std::ios::app);
        apsi::network::ZMQSenderChannel channel; channel.bind("tcp://*:"+std::to_string(port));
        auto context = db->get_seal_context(); std::uint64_t p=0,o=0,q=0;
        for (;;) {
            auto op = channel.receive_network_operation(context);
            if (!op) { std::this_thread::sleep_for(1ms); continue; }
            auto started = std::chrono::steady_clock::now();
            if (op->sop->type() == apsi::network::SenderOperationType::sop_parms) {
                auto req = apsi::to_params_request(std::move(op->sop));
                apsi::sender::Sender::RunParams(req, db, channel, [&op](apsi::network::Channel &base, apsi::Response response){
                    auto w=std::make_unique<apsi::network::ZMQSenderOperationResponse>(); w->sop_response=std::move(response); w->client_id=std::move(op->client_id); static_cast<apsi::network::ZMQSenderChannel&>(base).send(std::move(w)); });
                metric(metrics,"PARAMS",++p,elapsed(started));
            } else if (op->sop->type() == apsi::network::SenderOperationType::sop_oprf) {
                auto req=apsi::to_oprf_request(std::move(op->sop));
                apsi::sender::Sender::RunOPRF(req,key,channel,[&op](apsi::network::Channel &base,apsi::Response response){ auto w=std::make_unique<apsi::network::ZMQSenderOperationResponse>(); w->sop_response=std::move(response); w->client_id=std::move(op->client_id); static_cast<apsi::network::ZMQSenderChannel&>(base).send(std::move(w)); });
                metric(metrics,"OPRF",++o,elapsed(started));
            } else if (op->sop->type() == apsi::network::SenderOperationType::sop_query) {
                apsi::sender::Query query(apsi::to_query_request(std::move(op->sop)),db);
                apsi::sender::Sender::RunQuery(query,channel,
                    [&op](apsi::network::Channel &base,apsi::Response response){ auto w=std::make_unique<apsi::network::ZMQSenderOperationResponse>(); w->sop_response=std::move(response); w->client_id=op->client_id; static_cast<apsi::network::ZMQSenderChannel&>(base).send(std::move(w)); },
                    [&op](apsi::network::Channel &base,apsi::ResultPart result){ auto w=std::make_unique<apsi::network::ZMQResultPackage>(); w->rp=std::move(result); w->client_id=op->client_id; static_cast<apsi::network::ZMQSenderChannel&>(base).send(std::move(w)); });
                metric(metrics,"QUERY",++q,elapsed(started));
            } else throw std::runtime_error("invalid APSI operation");
        }
    } catch (const std::exception &ex) {
        std::cerr << "oae_v14_apsi_sender_service: " << ex.what() << '\n'; return 1;
    }
}
