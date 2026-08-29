# Relay Security Definition — V8

## Observer and secret

The Relay sees the Relay endpoint, Gateway endpoint, connection policy, request/response transport timing, final encapsulated body sizes, public transcript, and public OHTTP choices. The protected values are inner Agent/Tool metadata, route handle, operation data, and result data.

## Intended mechanism

RFC 9458 OHTTP protects the inner RFC 9292 message. Fixed final encapsulated sizes and a public transcript profile remove only the declared size/count/order variation. The following are allowed public leakage: profile ID, key ID, KEM/KDF/AEAD, config epoch, endpoints, connection policy, round count/order, public lifetime, and timing.

## V8 status

The definition is specified, but the implementation is OPEN because no permitted local RFC implementation was available. The fresh-request Relay minimizes metadata independently but is not an OHTTP substitute.

