#pragma once

#include <string>
#include <zmq.h>
#include "json.hpp"
using json = nlohmann::json;

class ZmqContext
{
public:
    ZmqContext() {m_context = zmq_ctx_new();}
    void* operator() () {return m_context;};
    ~ZmqContext() {zmq_ctx_destroy(m_context);}
private:
    void* m_context;
};

class ZmqMessage
{
public:
    ZmqMessage() {zmq_msg_init(&msg);};
    ~ZmqMessage() {zmq_msg_close(&msg);}
    ZmqMessage(ZmqMessage&& m) {msg = m.msg; zmq_msg_init(&m.msg);}
    void* data() {return zmq_msg_data(&msg);}
    size_t size() {return zmq_msg_size(&msg);}
    ZmqMessage(const ZmqMessage&) = delete;
    void operator = (const ZmqMessage&) = delete;
private:
    zmq_msg_t msg;
    friend class ZmqSocket;
};

class ZmqSocket
{
public:
    ZmqSocket(ZmqContext* context, int type);
    ~ZmqSocket() {zmq_close(socket);}
    void connect(const std::string& host);
    void bind(const std::string& host);
    void setsockopt(int option, const void* optval, size_t optvallen);
    json recvJson();
    std::vector<ZmqMessage> recvMultipart();
    void send(const std::string& msg);
    int poll(short events, long timeout);
private:
    void* socket;
    ZmqContext* m_context;
};

std::string getNicIp();

class CollectionApp
{
public:
    CollectionApp(const std::string& managerHostname, int platform, const std::string& level);
    void run();
protected:
    virtual void handlePlat(const json& msg);
    virtual void handleAlloc(const json& msg);
    virtual void handleConnect(const json& msg) = 0;
    virtual void handleConfigure(const json& msg) {};
    virtual void handleEnable(const json& msg) {};
    virtual void handleDisable(const json& msg) {};
    virtual void handleReset(const json& msg) = 0;
    void reply(const json& msg);
    size_t getId() const {return m_id;}
    const std::string& getLevel() const {return m_level;}
private:
    std::string m_level;
    ZmqContext m_context;
    ZmqSocket m_pushSocket;
    ZmqSocket m_subSocket;
    size_t m_id;
    std::unordered_map<std::string, std::function<void(json&)> > m_handleMap;
};

json createMsg(const std::string& key, const std::string& msg_id, size_t sender_id, json& body);
