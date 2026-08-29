package gatewayv2

import "sync"

type EffectGate struct {
	mu   sync.Mutex
	seen map[[OperationIDBytes]byte]bool
}

func NewEffectGate() *EffectGate {
	return &EffectGate{seen: make(map[[OperationIDBytes]byte]bool)}
}

// Reserve returns true exactly once for an operation ID. The ID is private and
// the gate is owned by the trusted Worker. NOOP is rejected before this point.
func (g *EffectGate) Reserve(operationID [OperationIDBytes]byte) bool {
	g.mu.Lock()
	defer g.mu.Unlock()
	if g.seen[operationID] {
		return false
	}
	g.seen[operationID] = true
	return true
}
