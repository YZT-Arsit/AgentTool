//go:build linux

package canonicalv9

import "testing"

func TestV12AffinityIsolationUsesFrozenFrameworkCPUSet(t *testing.T) {
	if !affinityListExcludesCPU("0-206", 207) {
		t.Fatal("frozen framework CPU set was not recognized as excluding pacer CPU")
	}
	if affinityListExcludesCPU("0-207", 207) {
		t.Fatal("overlapping framework CPU set was incorrectly accepted")
	}
}
