package main

import (
	"bytes"
	"context"
	"encoding/binary"
	"encoding/json"
	"io"
	"net"
	"net/http"
	"testing"
	"time"
)

// a ProcessingRequest with HttpHeaders in field f (one header :path=/s, end_of_stream=false)
// and protocol_config (field 11) in front, as Envoy sends the first message
func request(f int, withProtocolConfig bool) []byte {
	hv := append([]byte{0x0a, 5}, []byte(":path")...)            // HeaderValue.key = 1
	hv = append(hv, append([]byte{0x1a, 2}, []byte("/s")...)...) // raw_value = 3
	hm := append([]byte{0x0a, byte(len(hv))}, hv...)             // HeaderMap.headers = 1
	hh := append([]byte{0x0a, byte(len(hm))}, hm...)             // HttpHeaders.headers = 1
	var b []byte
	if withProtocolConfig {
		b = append(b, 0x5a, 2, 0x08, 1) // field 11, ProtocolConfiguration{request_body_mode: 1}
	}
	b = append(b, byte(f<<3|2), byte(len(hh)))
	return append(b, hh...)
}

func TestPhase(t *testing.T) {
	for f := 2; f <= 7; f++ {
		if got := Phase(request(f, true)); got != f {
			t.Fatalf("field %d: got %d", f, got)
		}
		if got := Phase(request(f, false)); got != f {
			t.Fatalf("field %d without protocol_config: got %d", f, got)
		}
	}
	if got := Phase([]byte{0x68, 1}); got != 0 { // observability_mode = true only
		t.Fatalf("no phase: got %d", got)
	}
	if got := Phase([]byte{0x12, 9, 1}); got != -1 { // length past the end
		t.Fatalf("truncated: got %d", got)
	}
	if got := Phase(nil); got != 0 {
		t.Fatalf("empty: got %d", got)
	}
}

func TestResponses(t *testing.T) {
	// request_headers (2) -> ProcessingResponse.request_headers (1): tag 0x0a, length 0
	want := []byte{0, 0, 0, 0, 2, 0x0a, 0}
	if !bytes.Equal(responses[2], want) {
		t.Fatalf("got % x", responses[2])
	}
	// response_headers (3) -> field 2: tag 0x12
	if responses[3][5] != 0x12 || responses[7][5] != 6<<3|2 {
		t.Fatalf("got % x / % x", responses[3], responses[7])
	}
}

func readFrame(t *testing.T, r io.Reader) []byte {
	var pre [5]byte
	if _, err := io.ReadFull(r, pre[:]); err != nil {
		t.Fatalf("read prefix: %v", err)
	}
	b := make([]byte, binary.BigEndian.Uint32(pre[1:]))
	if _, err := io.ReadFull(r, b); err != nil {
		t.Fatalf("read message: %v", err)
	}
	return b
}

// One bidirectional stream over h2c: request headers, then response headers, each answered
// before the next is sent (as Envoy does), then the client half-closes; grpc-status 0.
func TestStreamH2C(t *testing.T) {
	st := &Stats{}
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	srv := NewServer(ln.Addr().String(), st)
	go srv.Serve(ln)
	defer srv.Shutdown(context.Background())

	var p http.Protocols
	p.SetUnencryptedHTTP2(true)
	cl := &http.Client{Transport: &http.Transport{Protocols: &p}, Timeout: 10 * time.Second}
	pr, pw := io.Pipe()
	req, _ := http.NewRequest(http.MethodPost, "http://"+ln.Addr().String()+processPath, pr)
	req.Header.Set("Content-Type", "application/grpc")
	req.Header.Set("TE", "trailers")
	go pw.Write(Frame(request(2, true)))
	resp, err := cl.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	if resp.ProtoMajor != 2 || resp.Header.Get("Content-Type") != "application/grpc" {
		t.Fatalf("proto %d, content-type %q", resp.ProtoMajor, resp.Header.Get("Content-Type"))
	}
	if m := readFrame(t, resp.Body); !bytes.Equal(m, []byte{0x0a, 0}) {
		t.Fatalf("first response % x", m)
	}
	go func() {
		pw.Write(Frame(request(3, false)))
	}()
	if m := readFrame(t, resp.Body); !bytes.Equal(m, []byte{0x12, 0}) {
		t.Fatalf("second response % x", m)
	}
	pw.Close()
	if rest, _ := io.ReadAll(resp.Body); len(rest) != 0 {
		t.Fatalf("trailing bytes % x", rest)
	}
	if g := resp.Trailer.Get("Grpc-Status"); g != "0" {
		t.Fatalf("grpc-status %q", g)
	}
	r2, err := http.Get("http://" + ln.Addr().String() + "/epl-stats")
	if err != nil {
		t.Fatal(err)
	}
	var s map[string]int64
	if err := json.NewDecoder(r2.Body).Decode(&s); err != nil {
		t.Fatal(err)
	}
	if s["streams"] != 1 || s["request_headers"] != 1 || s["response_headers"] != 1 || s["responses"] != 2 ||
		s["errors"] != 0 {
		t.Fatalf("stats %v", s)
	}
}
