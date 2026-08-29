//go:build linux

package gatewayv2

import (
	"os"
	"syscall"
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
	data, err := syscall.Mmap(int(file.Fd()), 0, size, syscall.PROT_READ|syscall.PROT_WRITE, syscall.MAP_SHARED)
	if err != nil {
		file.Close()
		return mappedRegion{}, err
	}
	return mappedRegion{data: data, file: file, close: func() error {
		err1 := syscall.Munmap(data)
		err2 := file.Close()
		if err1 != nil {
			return err1
		}
		return err2
	}}, nil
}
