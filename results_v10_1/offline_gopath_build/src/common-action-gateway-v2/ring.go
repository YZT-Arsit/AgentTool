package gatewayv2

import (
	"encoding/binary"
	"errors"
	"fmt"
	"os"
	"sync/atomic"
	"unsafe"
)

const ringHeaderBytes = 64
const ringMagic uint64 = 0x434147563252494e // CAGV2RIN

type mappedRegion struct {
	data  []byte
	file  *os.File
	close func() error
}

type SPSCRing struct {
	region     mappedRegion
	capacity   uint64
	recordSize uint64
	writeSeq   *uint64
	readSeq    *uint64
}

func CreateRing(path string, capacity, recordSize int) (*SPSCRing, error) {
	if capacity < 2 || recordSize < 1 {
		return nil, errors.New("invalid ring dimensions")
	}
	size := ringHeaderBytes + capacity*recordSize
	region, err := mapRegion(path, size, true)
	if err != nil {
		return nil, err
	}
	clear(region.data)
	binary.LittleEndian.PutUint64(region.data[0:8], ringMagic)
	binary.LittleEndian.PutUint32(region.data[8:12], uint32(capacity))
	binary.LittleEndian.PutUint32(region.data[12:16], uint32(recordSize))
	ring := ringFromRegion(region)
	atomic.StoreUint64(ring.writeSeq, 0)
	atomic.StoreUint64(ring.readSeq, 0)
	return ring, nil
}

func OpenRing(path string) (*SPSCRing, error) {
	info, err := os.Stat(path)
	if err != nil {
		return nil, err
	}
	region, err := mapRegion(path, int(info.Size()), false)
	if err != nil {
		return nil, err
	}
	if binary.LittleEndian.Uint64(region.data[0:8]) != ringMagic {
		region.close()
		return nil, errors.New("ring magic mismatch")
	}
	return ringFromRegion(region), nil
}

func ringFromRegion(region mappedRegion) *SPSCRing {
	return &SPSCRing{
		region:     region,
		capacity:   uint64(binary.LittleEndian.Uint32(region.data[8:12])),
		recordSize: uint64(binary.LittleEndian.Uint32(region.data[12:16])),
		writeSeq:   (*uint64)(unsafe.Pointer(&region.data[16])),
		readSeq:    (*uint64)(unsafe.Pointer(&region.data[24])),
	}
}

func (r *SPSCRing) Close() error    { return r.region.close() }
func (r *SPSCRing) RecordSize() int { return int(r.recordSize) }
func (r *SPSCRing) Capacity() int   { return int(r.capacity) }

func (r *SPSCRing) TryPush(record []byte) bool {
	if uint64(len(record)) != r.recordSize {
		panic(fmt.Sprintf("record is %d bytes, expected %d", len(record), r.recordSize))
	}
	write := atomic.LoadUint64(r.writeSeq)
	read := atomic.LoadUint64(r.readSeq)
	if write-read >= r.capacity {
		return false
	}
	offset := ringHeaderBytes + int((write%r.capacity)*r.recordSize)
	copy(r.region.data[offset:offset+int(r.recordSize)], record)
	atomic.StoreUint64(r.writeSeq, write+1)
	return true
}

func (r *SPSCRing) TryPop(dst []byte) bool {
	if uint64(len(dst)) != r.recordSize {
		panic(fmt.Sprintf("destination is %d bytes, expected %d", len(dst), r.recordSize))
	}
	read := atomic.LoadUint64(r.readSeq)
	write := atomic.LoadUint64(r.writeSeq)
	if read >= write {
		return false
	}
	offset := ringHeaderBytes + int((read%r.capacity)*r.recordSize)
	copy(dst, r.region.data[offset:offset+int(r.recordSize)])
	atomic.StoreUint64(r.readSeq, read+1)
	return true
}

func (r *SPSCRing) Depth() uint64 {
	return atomic.LoadUint64(r.writeSeq) - atomic.LoadUint64(r.readSeq)
}
