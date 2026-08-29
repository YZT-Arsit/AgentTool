//go:build windows

package gatewayv2

import (
	"os"
	"syscall"
	"unsafe"
)

func mapRegion(path string, size int, create bool) (mappedRegion, error) {
	flag := os.O_RDWR
	if create {
		flag |= os.O_CREATE | os.O_TRUNC
	}
	file, err := os.OpenFile(path, flag, 0o600)
	if err != nil {
		return mappedRegion{}, err
	}
	if create {
		if err := file.Truncate(int64(size)); err != nil {
			file.Close()
			return mappedRegion{}, err
		}
	}
	handle, err := syscall.CreateFileMapping(syscall.Handle(file.Fd()), nil, syscall.PAGE_READWRITE, 0, uint32(size), nil)
	if err != nil {
		file.Close()
		return mappedRegion{}, err
	}
	addr, err := syscall.MapViewOfFile(handle, syscall.FILE_MAP_WRITE|syscall.FILE_MAP_READ, 0, 0, uintptr(size))
	syscall.CloseHandle(handle)
	if err != nil {
		file.Close()
		return mappedRegion{}, err
	}
	data := unsafe.Slice((*byte)(unsafe.Pointer(addr)), size)
	return mappedRegion{data: data, file: file, close: func() error {
		err1 := syscall.UnmapViewOfFile(addr)
		err2 := file.Close()
		if err1 != nil {
			return err1
		}
		return err2
	}}, nil
}
