package main

import "crypto/rand"

func platformRandom(p []byte) (int, error) { return rand.Read(p) }
