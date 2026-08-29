package gatewayv2

import (
	"net"
	"time"
)

type FixedTransport interface {
	ReadFrame([]byte) error
	WriteFrame([]byte) error
	SetWriteDeadline(time.Time) error
	RemoteAddr() string
	Close() error
}

type TCPTransport struct{ conn net.Conn }

func NewTCPTransport(conn net.Conn) *TCPTransport {
	if tcp, ok := conn.(*net.TCPConn); ok {
		_ = tcp.SetNoDelay(true)
		_ = tcp.SetKeepAlive(true)
	}
	return &TCPTransport{conn: conn}
}

func (t *TCPTransport) ReadFrame(dst []byte) error  { return ReadFixedFrame(t.conn, dst) }
func (t *TCPTransport) WriteFrame(src []byte) error { return WriteFixedFrame(t.conn, src) }
func (t *TCPTransport) SetWriteDeadline(deadline time.Time) error {
	return t.conn.SetWriteDeadline(deadline)
}
func (t *TCPTransport) RemoteAddr() string { return t.conn.RemoteAddr().String() }
func (t *TCPTransport) Close() error       { return t.conn.Close() }

type TimedTransmitCapability struct {
	Backend     string `json:"backend"`
	Implemented bool   `json:"implemented"`
	PacketLevel bool   `json:"packet_level"`
	Reason      string `json:"reason"`
}

func TCPTransmitCapability() TimedTransmitCapability {
	return TimedTransmitCapability{
		Backend: "TCP_SOCKET_BOUNDARY", Implemented: true, PacketLevel: false,
		Reason: "TCP write timing does not provide SO_TXTIME/ETF packet-release guarantees",
	}
}

func FutureTimedDatagramCapability() TimedTransmitCapability {
	return TimedTransmitCapability{
		Backend: "SO_TXTIME_ETF_TIMED_DATAGRAM", Implemented: false, PacketLevel: false,
		Reason: "requires Linux qdisc/capability configuration and a datagram or QUIC framing design",
	}
}
