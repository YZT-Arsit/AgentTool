package gatewayv2

import "testing"

func TestOpaqueClientFramesRequireNoWorkloadOrKey(t *testing.T) {
	profile := PublicProfile{Name: "test", FrameBytes: 1024, Slots: 2, Sessions: 1,
		RequestDeltaNS: 1000000, ResponseDeltaNS: 1000000, MaskNS: 100000,
		StartDelayNS: 10000000, InterSessionGapNS: 1000000}
	frames := [][]byte{make([]byte, 1024), make([]byte, 1024)}
	config := ClientConfig{Profile: profile, Frames: frames}
	if len(config.Workload.Sessions) != 0 || config.KeyHex != "" {
		t.Fatal("opaque client path unexpectedly requires private workload/key")
	}
}
