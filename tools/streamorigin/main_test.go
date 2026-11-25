package main

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"strings"
	"testing"
	"time"
)

// countConn counts the Write calls and keeps what was written.
type countConn struct {
	writes [][]byte
}

func (c *countConn) Write(b []byte) (int, error) {
	c.writes = append(c.writes, append([]byte(nil), b...))
	return len(b), nil
}

func TestPlanCL(t *testing.T) {
	p, err := PlanCL(65536, 0)
	if err != nil || len(p.Writes) != 1 || p.Chunks != 0 {
		t.Fatalf("one write expected: %v %d", err, len(p.Writes))
	}
	head := fmt.Sprintf(headCL, 65536)
	if len(p.Writes[0]) != len(head)+65536 || !bytes.HasPrefix(p.Writes[0], []byte(head)) {
		t.Fatal("head + body in the one write")
	}
	p, _ = PlanCL(65536, 8192)
	if len(p.Writes) != 8 || len(p.Writes[0]) != len(head)+8192 || len(p.Writes[7]) != 8192 {
		t.Fatalf("8 writes of 8192 (head with the first): %d", len(p.Writes))
	}
	tot := 0
	for _, w := range p.Writes {
		tot += len(w)
	}
	if tot != len(head)+65536 {
		t.Fatal("cl8k wire size = head + body, no framing")
	}
	if p, _ = PlanCL(0, 0); len(p.Writes) != 1 {
		t.Fatal("empty body")
	}
	if _, err := PlanCL(-1, 0); err == nil {
		t.Fatal("negative bytes")
	}
}

func TestPlanChunked(t *testing.T) {
	for _, c := range []struct{ n, chunk, writes int }{{65536, 8192, 8}, {65536, 4096, 16}, {1 << 20, 8192, 128}, {10000, 4096, 3}} {
		p, err := PlanChunked(c.n, c.chunk)
		if err != nil || len(p.Writes) != c.writes || p.Chunks != c.writes {
			t.Fatalf("%v: %v writes %d chunks %d", c, err, len(p.Writes), p.Chunks)
		}
		var all []byte
		for i, w := range p.Writes {
			all = append(all, w...)
			// every write is exactly one chunk: size line, data, CRLF (the head before the first,
			// the last-chunk marker after the last)
			b := w
			if i == 0 {
				if !bytes.HasPrefix(b, []byte(headCh)) {
					t.Fatal("head with the first chunk")
				}
				b = b[len(headCh):]
			}
			size := min(c.chunk, c.n-i*c.chunk)
			want := fmt.Sprintf("%x\r\n", size)
			if !bytes.HasPrefix(b, []byte(want)) {
				t.Fatalf("write %d does not start with its size line", i)
			}
			rest := len(b) - len(want) - size - 2
			if i == len(p.Writes)-1 {
				rest -= len(lastChunk)
			}
			if rest != 0 {
				t.Fatalf("write %d carries %d stray bytes", i, rest)
			}
		}
		resp, err := http.ReadResponse(bufio.NewReader(bytes.NewReader(all)), nil)
		if err != nil {
			t.Fatal(err)
		}
		body, err := io.ReadAll(resp.Body)
		if err != nil || len(body) != c.n || resp.TransferEncoding[0] != "chunked" {
			t.Fatalf("%v: parsed body %d %v", c, len(body), err)
		}
	}
	if _, err := PlanChunked(100, 0); err == nil {
		t.Fatal("chunk 0")
	}
}

func TestPlanSSE(t *testing.T) {
	p, err := PlanSSE(20, 200, 1000)
	if err != nil || len(p.Writes) != 20 || p.Events != 20 || p.Body != 4000 {
		t.Fatalf("%v %d", err, len(p.Writes))
	}
	var all []byte
	for _, w := range p.Writes {
		all = append(all, w...)
	}
	resp, err := http.ReadResponse(bufio.NewReader(bytes.NewReader(all)), nil)
	if err != nil {
		t.Fatal(err)
	}
	body, _ := io.ReadAll(resp.Body)
	if len(body) != 4000 || strings.Count(string(body), "data: ") != 20 || !bytes.HasSuffix(body, []byte("\n\n")) {
		t.Fatalf("sse body %d", len(body))
	}
	if len(GrpcMessage(200)) != 200 || GrpcMessage(200)[4] != 195 {
		t.Fatal("grpc message")
	}
}

func mustURL(p string) *url.URL {
	req, _ := http.NewRequest("GET", p, nil)
	return req.URL
}

func TestRunCountsOneWritePerChunk(t *testing.T) {
	s := &Server{}
	for _, c := range []struct {
		path   string
		writes int64
		chunks int64
	}{{"/cl?bytes=65536", 1, 0}, {"/cl?bytes=65536&chunk=8192&pad=xx", 8, 0}, {"/chunked?bytes=65536&chunk=8192", 8, 8},
		{"/chunked?bytes=65536&chunk=4096", 16, 16}} {
		p, err := s.plan(mustURL(c.path))
		if err != nil {
			t.Fatal(err)
		}
		w0, c0 := s.St.WriteCalls.Load(), s.St.Chunks.Load()
		cc := &countConn{}
		if !s.run(cc, p) {
			t.Fatal("run failed")
		}
		if got := s.St.WriteCalls.Load() - w0; got != c.writes || int64(len(cc.writes)) != c.writes {
			t.Fatalf("%s: %d write calls, want %d", c.path, got, c.writes)
		}
		if got := s.St.Chunks.Load() - c0; got != c.chunks {
			t.Fatalf("%s: %d chunks, want %d", c.path, got, c.chunks)
		}
	}
	if _, err := s.plan(mustURL("/nope")); err == nil {
		t.Fatal("unknown path")
	}
}

func start(t *testing.T) (*Server, string, string) {
	s := &Server{}
	l1, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	l2, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	go s.ServeH1(l1)
	hs := H2Server(s)
	go hs.Serve(l2)
	t.Cleanup(func() { l1.Close(); hs.Close() })
	return s, l1.Addr().String(), l2.Addr().String()
}

func TestH1KeepAliveAndStats(t *testing.T) {
	_, a1, _ := start(t)
	c, err := net.Dial("tcp", a1)
	if err != nil {
		t.Fatal(err)
	}
	defer c.Close()
	br := bufio.NewReader(c)
	get := func(path string) (*http.Response, []byte) {
		fmt.Fprintf(c, "GET %s HTTP/1.1\r\nHost: x\r\n\r\n", path)
		r, err := http.ReadResponse(br, nil)
		if err != nil {
			t.Fatal(err)
		}
		b, err := io.ReadAll(r.Body)
		if err != nil {
			t.Fatal(err)
		}
		return r, b
	}
	// requests on one connection, the three write patterns and a timed stream
	r, b := get("/cl?bytes=65536&chunk=0")
	if r.StatusCode != 200 || len(b) != 65536 || r.ContentLength != 65536 {
		t.Fatalf("cl: %d %d", r.StatusCode, len(b))
	}
	r, b = get("/chunked?bytes=65536&chunk=8192")
	if len(b) != 65536 || len(r.TransferEncoding) != 1 || r.ContentLength != -1 {
		t.Fatalf("chunked: %d %v", len(b), r.TransferEncoding)
	}
	r, b = get("/cl?bytes=65536&chunk=8192")
	if len(b) != 65536 || r.ContentLength != 65536 {
		t.Fatal("cl8k")
	}
	t0 := time.Now()
	r, b = get("/sse?events=20&bytes=200&gap_us=1000")
	if d := time.Since(t0); len(b) != 4000 || d < 19*time.Millisecond || r.Header.Get("Content-Type") != "text/event-stream" {
		t.Fatalf("sse: %d bytes in %v", len(b), d)
	}
	if r, _ = get("/nope"); r.StatusCode != 404 {
		t.Fatal("404")
	}
	if r, _ = get("/cl?bytes=x"); r.StatusCode != 400 {
		t.Fatal("400")
	}
	_, b = get("/epl-stats")
	var st map[string]int64
	if err := json.Unmarshal(b, &st); err != nil {
		t.Fatal(err)
	}
	if st["responses"] != 4 || st["write_calls"] != 1+8+8+20 || st["chunks"] != 8+20 || st["events"] != 20 ||
		st["body_bytes"] != 3*65536+4000 || st["bad_requests"] != 2 || st["connections"] != 1 {
		t.Fatalf("stats %v", st)
	}
	wire := int64(len(fmt.Sprintf(headCL, 65536))*2 + 2*65536 + len(headCh) + 65536 + 8*8 + 5 + len(headSSE) + 20*(200+6) + 5)
	if st["wire_bytes"] != wire {
		t.Fatalf("wire bytes %d, want %d", st["wire_bytes"], wire)
	}
}

func TestH2(t *testing.T) {
	s, _, a2 := start(t)
	pr := new(http.Protocols)
	pr.SetUnencryptedHTTP2(true)
	cl := &http.Client{Transport: &http.Transport{Protocols: pr}}
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	get := func(path string) (*http.Response, []byte) {
		req, _ := http.NewRequestWithContext(ctx, "GET", "http://"+a2+path, nil)
		r, err := cl.Do(req)
		if err != nil {
			t.Fatal(err)
		}
		b, _ := io.ReadAll(r.Body)
		r.Body.Close()
		return r, b
	}
	r, b := get("/cl?bytes=1048576")
	if r.ProtoMajor != 2 || len(b) != 1<<20 {
		t.Fatalf("h2 cl: proto %d, %d bytes", r.ProtoMajor, len(b))
	}
	t0 := time.Now()
	r, b = get(grpcStream + "?events=20&bytes=200&gap_us=1000")
	if len(b) != 4000 || r.Trailer.Get("Grpc-Status") != "0" || time.Since(t0) < 19*time.Millisecond ||
		r.Header.Get("Content-Type") != "application/grpc" {
		t.Fatalf("grpc stream: %d bytes, trailer %q", len(b), r.Trailer.Get("Grpc-Status"))
	}
	if s.St.H2Responses.Load() != 2 || s.St.Events.Load() != 20 {
		t.Fatal("h2 counters")
	}
	if r, _ = get("/nope"); r.StatusCode != 404 {
		t.Fatal("404")
	}
}

func TestLoopbackOnly(t *testing.T) {
	if loopback("127.0.0.1:8098") != nil || loopback("0.0.0.0:8098") == nil || loopback("10.0.0.1:1") == nil {
		t.Fatal("loopback check")
	}
}
