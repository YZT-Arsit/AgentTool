package gatewayv2

import (
	"crypto/sha256"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"os"
	"time"
)

type PublicProfile struct {
	Name              string `json:"name"`
	FrameBytes        int    `json:"frame_bytes"`
	Slots             int    `json:"slots"`
	Sessions          int    `json:"sessions"`
	RequestDeltaNS    int64  `json:"request_delta_ns"`
	ResponseDeltaNS   int64  `json:"response_delta_ns"`
	MaskNS            int64  `json:"mask_ns"`
	StartDelayNS      int64  `json:"start_delay_ns"`
	InterSessionGapNS int64  `json:"inter_session_gap_ns"`
}

func (p PublicProfile) ID() uint64 {
	material := fmt.Sprintf("%s|%d|%d|%d|%d|%d|%d|%d|%d", p.Name, p.FrameBytes,
		p.Slots, p.Sessions, p.RequestDeltaNS, p.ResponseDeltaNS, p.MaskNS,
		p.StartDelayNS, p.InterSessionGapNS)
	digest := sha256.Sum256([]byte(material))
	return binary.BigEndian.Uint64(digest[:8])
}

func LoadProfile(path string) (PublicProfile, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return PublicProfile{}, err
	}
	var profile PublicProfile
	if err := json.Unmarshal(raw, &profile); err != nil {
		return PublicProfile{}, err
	}
	if profile.FrameBytes < 256 || profile.Slots < 1 || profile.Sessions < 1 {
		return PublicProfile{}, fmt.Errorf("invalid public dimensions")
	}
	if profile.RequestDeltaNS <= 0 || profile.ResponseDeltaNS <= 0 {
		return PublicProfile{}, fmt.Errorf("cadences must be positive")
	}
	if profile.MaskNS <= 0 || profile.MaskNS >= profile.ResponseDeltaNS {
		return PublicProfile{}, fmt.Errorf("mask must be inside response cadence")
	}
	if profile.StartDelayNS < int64(10*time.Millisecond) {
		return PublicProfile{}, fmt.Errorf("start delay is too short")
	}
	return profile, nil
}

func (p PublicProfile) SessionSpanNS() int64 {
	req := int64(p.Slots) * p.RequestDeltaNS
	resp := int64(p.Slots) * p.ResponseDeltaNS
	if resp > req {
		req = resp
	}
	return req + p.InterSessionGapNS
}

func (p PublicProfile) SessionBaseNS(t0 int64, session int) int64 {
	return t0 + int64(session)*p.SessionSpanNS()
}
