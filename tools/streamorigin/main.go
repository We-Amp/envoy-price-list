// epl-streamorigin: an origin that sends bodies in a chosen write pattern (Go standard library only).
//
// Two loopback listeners:
//
//	-h1 127.0.0.1:8098   HTTP/1.1, served by a small loop of its own over the TCP connection, so
//	                     that every write the response plan names is exactly one Write on the
//	                     socket (net/http's buffered writer would split a chunk's size line and
//	                     data over several writes)
//	-h2 127.0.0.1:8099   HTTP/2 cleartext with prior knowledge (net/http, Protocols)
//
// Endpoints (GET):
//
//	/cl?bytes=N                    Content-Length, head and body in one write
//	/cl?bytes=N&chunk=C            Content-Length, the body in writes of C bytes (the head goes with
//	                               the first): the write pattern of /chunked without chunk framing
//	/chunked?bytes=N&chunk=C       Transfer-Encoding: chunked, one chunk of C bytes per write (size
//	                               line, data and CRLF in the same write; the head goes with the
//	                               first chunk, the last-chunk marker with the last)
//	/sse?events=N&bytes=B&gap_us=G text/event-stream, chunked, one event of B bytes per write, event
//	                               i due at start + i*G microseconds
//	/epl.bench.Bench/Stream?events=N&bytes=B&gap_us=G   (HTTP/2 port) the same as length-prefixed
//	                               gRPC messages of B bytes, trailer grpc-status: 0
//	/epl-stats                     the counters as JSON (not counted itself); the harness reads it
//	                               outside the measurement window
//
// Unknown query parameters are ignored (the harness pads request lines to one length with `pad`).
// On the HTTP/2 port /cl writes the body in one Write (or per chunk with a Flush each); the
// HTTP/2 framer decides the DATA frames.
//
// Timed events sleep on a locked OS thread with nanosleep and a 1 us timer slack (the Go timer wakes
// through the network poller with millisecond rounding). An event written more than 500 microseconds after
// its due time counts as late.
package main

import (
	"bufio"
	"encoding/binary"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"net/url"
	"os"
	"runtime"
	"strconv"
	"sync"
	"sync/atomic"
	"syscall"
	"time"
)

const (
	maxBytes   = 64 << 20
	maxWrites  = 1 << 17
	maxEvents  = 1 << 17
	maxGapUs   = 1000000
	lateUs     = 500
	grpcStream = "/epl.bench.Bench/Stream"
	headCL     = "HTTP/1.1 200 OK\r\nContent-Type: application/octet-stream\r\nContent-Length: %d\r\n\r\n"
	headCh     = "HTTP/1.1 200 OK\r\nContent-Type: application/octet-stream\r\nTransfer-Encoding: chunked\r\n\r\n"
	headSSE    = "HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nTransfer-Encoding: chunked\r\n\r\n"
	lastChunk  = "0\r\n\r\n"
)

// Stats are cumulative since start.
type Stats struct {
	Responses   atomic.Int64 // responses completed, every endpoint but /epl-stats
	BodyBytes   atomic.Int64 // body bytes (without head and chunk framing)
	WireBytes   atomic.Int64 // HTTP/1.1 port: every byte written, head and framing included
	WriteCalls  atomic.Int64 // HTTP/1.1 port: Write calls on the socket; HTTP/2 port: Write calls on the response
	Chunks      atomic.Int64 // chunked-framed chunks with data (/chunked, /sse)
	Events      atomic.Int64 // timed events and gRPC messages
	LateEvents  atomic.Int64 // events written more than 500 us after their due time
	MaxLateUs   atomic.Int64
	H1Responses atomic.Int64
	H2Responses atomic.Int64
	BadRequests atomic.Int64
	WriteErrors atomic.Int64
	Connections atomic.Int64 // HTTP/1.1 port: connections accepted
}

func (s *Stats) JSON() []byte {
	b, _ := json.Marshal(map[string]int64{
		"responses": s.Responses.Load(), "body_bytes": s.BodyBytes.Load(), "wire_bytes": s.WireBytes.Load(),
		"write_calls": s.WriteCalls.Load(), "chunks": s.Chunks.Load(), "events": s.Events.Load(),
		"late_events": s.LateEvents.Load(), "max_late_us": s.MaxLateUs.Load(),
		"h1_responses": s.H1Responses.Load(), "h2_responses": s.H2Responses.Load(),
		"bad_requests": s.BadRequests.Load(), "write_errors": s.WriteErrors.Load(),
		"connections": s.Connections.Load(),
	})
	return b
}

// Plan is one response on the HTTP/1.1 port: the socket writes in order, and what they carry.
type Plan struct {
	Writes [][]byte
	Body   int // body bytes
	Chunks int // chunked-framed data chunks
	Events int // timed events (GapUs between them)
	GapUs  int
}

func fill(n int, c byte) []byte {
	b := make([]byte, n)
	for i := range b {
		b[i] = c
	}
	return b
}

// Event is one SSE event of exactly n bytes (n >= 8): "data: xxx...\n\n".
func Event(n int) []byte {
	b := fill(n, 'x')
	copy(b, "data: ")
	b[n-2], b[n-1] = '\n', '\n'
	return b
}

// GrpcMessage is one length-prefixed gRPC message of n bytes in all (n >= 5).
func GrpcMessage(n int) []byte {
	b := fill(n, 'x')
	b[0] = 0
	binary.BigEndian.PutUint32(b[1:5], uint32(n-5))
	return b
}

func chunkFrame(data []byte, first string, last bool) []byte {
	b := make([]byte, 0, len(first)+len(data)+32)
	b = append(b, first...)
	b = strconv.AppendInt(b, int64(len(data)), 16)
	b = append(b, '\r', '\n')
	b = append(b, data...)
	b = append(b, '\r', '\n')
	if last {
		b = append(b, lastChunk...)
	}
	return b
}

// PlanCL: Content-Length; chunk 0 = one write, else the body in writes of chunk bytes.
func PlanCL(n, chunk int) (*Plan, error) {
	if n < 0 || n > maxBytes || chunk < 0 || (chunk > 0 && (n+chunk-1)/chunk > maxWrites) {
		return nil, errors.New("bytes or chunk out of range")
	}
	head := fmt.Sprintf(headCL, n)
	body := fill(n, 'a')
	p := &Plan{Body: n}
	if chunk == 0 || n <= chunk {
		p.Writes = [][]byte{append([]byte(head), body...)}
		return p, nil
	}
	for off := 0; off < n; off += chunk {
		end := min(off+chunk, n)
		if off == 0 {
			p.Writes = append(p.Writes, append([]byte(head), body[:end]...))
		} else {
			p.Writes = append(p.Writes, body[off:end])
		}
	}
	return p, nil
}

// PlanChunked: one chunk of chunk bytes per write.
func PlanChunked(n, chunk int) (*Plan, error) {
	if n < 1 || n > maxBytes || chunk < 1 || (n+chunk-1)/chunk > maxWrites {
		return nil, errors.New("bytes or chunk out of range")
	}
	body := fill(n, 'a')
	p := &Plan{Body: n}
	for off := 0; off < n; off += chunk {
		end := min(off+chunk, n)
		first := ""
		if off == 0 {
			first = headCh
		}
		p.Writes = append(p.Writes, chunkFrame(body[off:end], first, end == n))
		p.Chunks++
	}
	return p, nil
}

// PlanSSE: events timed events of size bytes each, one chunk and one write per event.
func PlanSSE(events, size, gapUs int) (*Plan, error) {
	if events < 1 || events > maxEvents || size < 8 || size > 1<<20 || gapUs < 0 || gapUs > maxGapUs {
		return nil, errors.New("events, bytes or gap_us out of range")
	}
	ev := Event(size)
	p := &Plan{Body: events * size, Chunks: events, Events: events, GapUs: gapUs}
	mid := chunkFrame(ev, "", false)
	for i := 0; i < events; i++ {
		switch {
		case i == 0:
			p.Writes = append(p.Writes, chunkFrame(ev, headSSE, events == 1))
		case i == events-1:
			p.Writes = append(p.Writes, chunkFrame(ev, "", true))
		default:
			p.Writes = append(p.Writes, mid)
		}
	}
	return p, nil
}

func qint(q url.Values, k string, def int) (int, error) {
	v := q.Get(k)
	if v == "" {
		return def, nil
	}
	return strconv.Atoi(v)
}

type Server struct {
	St    Stats
	plans sync.Map // request path and the parameters that matter -> *Plan
}

var errNotFound = errors.New("not found")

func (s *Server) plan(u *url.URL) (*Plan, error) {
	q := u.Query()
	var key string
	var mk func() (*Plan, error)
	switch u.Path {
	case "/cl", "/chunked":
		n, e1 := qint(q, "bytes", -1)
		c, e2 := qint(q, "chunk", 0)
		if e1 != nil || e2 != nil {
			return nil, errors.New("bad number")
		}
		key = fmt.Sprintf("%s %d %d", u.Path, n, c)
		if u.Path == "/cl" {
			mk = func() (*Plan, error) { return PlanCL(n, c) }
		} else {
			mk = func() (*Plan, error) { return PlanChunked(n, c) }
		}
	case "/sse":
		n, e1 := qint(q, "events", -1)
		b, e2 := qint(q, "bytes", -1)
		g, e3 := qint(q, "gap_us", 0)
		if e1 != nil || e2 != nil || e3 != nil {
			return nil, errors.New("bad number")
		}
		key = fmt.Sprintf("/sse %d %d %d", n, b, g)
		mk = func() (*Plan, error) { return PlanSSE(n, b, g) }
	default:
		return nil, errNotFound
	}
	if p, ok := s.plans.Load(key); ok {
		return p.(*Plan), nil
	}
	p, err := mk()
	if err != nil {
		return nil, err
	}
	s.plans.Store(key, p)
	return p, nil
}

// pacedThread locks the goroutine to its OS thread and sets that thread's timer slack to 1 us (the
// default 50 us lets the kernel delay a nanosleep wake-up by that much). A per-thread attribute of this
// process only (prctl PR_SET_TIMERSLACK); no system setting changes.
func pacedThread() {
	runtime.LockOSThread()
	syscall.RawSyscall(syscall.SYS_PRCTL, 29 /* PR_SET_TIMERSLACK */, 1000, 0)
}

// sleepUntil blocks the calling OS thread until t (nanosleep; the caller holds LockOSThread).
func sleepUntil(t time.Time) {
	for {
		d := time.Until(t)
		if d <= 0 {
			return
		}
		ts := syscall.NsecToTimespec(int64(d))
		syscall.Nanosleep(&ts, nil)
	}
}

func (s *Server) late(due time.Time) {
	if us := time.Since(due).Microseconds(); us > lateUs {
		s.St.LateEvents.Add(1)
		for {
			m := s.St.MaxLateUs.Load()
			if us <= m || s.St.MaxLateUs.CompareAndSwap(m, us) {
				break
			}
		}
	}
}

// run writes one plan to w, one Write per entry; false when a write failed.
func (s *Server) run(w io.Writer, p *Plan) bool {
	timed := p.Events > 0 && p.GapUs > 0
	var start time.Time
	if timed {
		pacedThread()
		defer runtime.UnlockOSThread()
		start = time.Now()
	}
	// write calls and wire bytes are added when the response ends, with the response count, so that a
	// counter read in the middle of a response never sees a part of it
	var wire int64
	for i, b := range p.Writes {
		if timed && i > 0 {
			due := start.Add(time.Duration(i*p.GapUs) * time.Microsecond)
			sleepUntil(due)
			s.late(due)
		}
		n, err := w.Write(b)
		wire += int64(n)
		if err != nil {
			s.St.WriteErrors.Add(1)
			s.St.WriteCalls.Add(int64(i + 1))
			s.St.WireBytes.Add(wire)
			return false
		}
	}
	s.St.WriteCalls.Add(int64(len(p.Writes)))
	s.St.WireBytes.Add(wire)
	s.St.BodyBytes.Add(int64(p.Body))
	s.St.Chunks.Add(int64(p.Chunks))
	s.St.Events.Add(int64(p.Events))
	s.St.Responses.Add(1)
	s.St.H1Responses.Add(1)
	return true
}

func plain(status int, body []byte) []byte {
	return append([]byte(fmt.Sprintf("HTTP/1.1 %d %s\r\nContent-Type: application/json\r\nContent-Length: %d\r\n\r\n",
		status, http.StatusText(status), len(body))), body...)
}

// ServeConn answers HTTP/1.1 requests on one connection until the peer closes it.
func (s *Server) ServeConn(c net.Conn) {
	defer c.Close()
	br := bufio.NewReaderSize(c, 8192)
	for {
		req, err := http.ReadRequest(br)
		if err != nil {
			return
		}
		io.Copy(io.Discard, req.Body)
		req.Body.Close()
		if req.URL.Path == "/epl-stats" {
			if _, err := c.Write(plain(200, s.St.JSON())); err != nil {
				return
			}
		} else if p, err := s.plan(req.URL); err != nil {
			s.St.BadRequests.Add(1)
			st := 400
			if err == errNotFound {
				st = 404
			}
			if _, err := c.Write(plain(st, []byte("{}"))); err != nil {
				return
			}
		} else if !s.run(c, p) {
			return
		}
		if req.Close {
			return
		}
	}
}

func (s *Server) ServeH1(l net.Listener) error {
	for {
		c, err := l.Accept()
		if err != nil {
			return err
		}
		s.St.Connections.Add(1)
		go s.ServeConn(c)
	}
}

// ServeHTTP is the HTTP/2 port (net/http): /cl, the gRPC stream, /epl-stats.
func (s *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	fl, _ := w.(http.Flusher)
	switch r.URL.Path {
	case "/epl-stats":
		w.Header().Set("Content-Type", "application/json")
		w.Write(s.St.JSON())
		return
	case "/cl":
		n, e1 := qint(q, "bytes", -1)
		c, e2 := qint(q, "chunk", 0)
		p, err := PlanCL(n, 0)
		if e1 != nil || e2 != nil || err != nil || c < 0 || (c > 0 && (n+c-1)/c > maxWrites) {
			s.St.BadRequests.Add(1)
			http.Error(w, "{}", 400)
			return
		}
		body := p.Writes[0][len(p.Writes[0])-n:]
		w.Header().Set("Content-Type", "application/octet-stream")
		w.Header().Set("Content-Length", strconv.Itoa(n))
		if c == 0 {
			c = max(n, 1)
		}
		var writes int64
		for off := 0; off < n; off += c {
			if _, err := w.Write(body[off:min(off+c, n)]); err != nil {
				s.St.WriteErrors.Add(1)
				return
			}
			writes++
			if n > c && fl != nil {
				fl.Flush()
			}
		}
		if n == 0 {
			writes = 1 // an empty body: the header write
		}
		s.St.WriteCalls.Add(writes)
		s.St.BodyBytes.Add(int64(n))
	case grpcStream:
		n, e1 := qint(q, "events", -1)
		b, e2 := qint(q, "bytes", -1)
		g, e3 := qint(q, "gap_us", 0)
		if e1 != nil || e2 != nil || e3 != nil || n < 1 || n > maxEvents || b < 5 || b > 1<<20 || g < 0 || g > maxGapUs || fl == nil {
			s.St.BadRequests.Add(1)
			http.Error(w, "{}", 400)
			return
		}
		msg := GrpcMessage(b)
		w.Header().Set("Content-Type", "application/grpc")
		w.Header().Set("Trailer", "Grpc-Status")
		if g > 0 {
			pacedThread()
			defer runtime.UnlockOSThread()
		}
		start := time.Now()
		for i := 0; i < n; i++ {
			if g > 0 && i > 0 {
				due := start.Add(time.Duration(i*g) * time.Microsecond)
				sleepUntil(due)
				s.late(due)
			}
			if _, err := w.Write(msg); err != nil {
				s.St.WriteErrors.Add(1)
				return
			}
			fl.Flush()
		}
		s.St.WriteCalls.Add(int64(n))
		w.Header().Set("Grpc-Status", "0")
		s.St.BodyBytes.Add(int64(n * b))
		s.St.Events.Add(int64(n))
	default:
		s.St.BadRequests.Add(1)
		http.NotFound(w, r)
		return
	}
	s.St.Responses.Add(1)
	s.St.H2Responses.Add(1)
}

// H2Server serves s over HTTP/2 cleartext (prior knowledge) and HTTP/1.1 on one listener.
func H2Server(s *Server) *http.Server {
	pr := new(http.Protocols)
	pr.SetHTTP1(true)
	pr.SetUnencryptedHTTP2(true)
	return &http.Server{Handler: s, Protocols: pr, ReadHeaderTimeout: 30 * time.Second}
}

func loopback(addr string) error {
	host, _, err := net.SplitHostPort(addr)
	if err != nil {
		return err
	}
	if ip := net.ParseIP(host); ip == nil || !ip.IsLoopback() {
		return fmt.Errorf("%s is not a loopback address", addr)
	}
	return nil
}

func main() {
	h1 := flag.String("h1", "127.0.0.1:8098", "HTTP/1.1 listen address (loopback only)")
	h2 := flag.String("h2", "127.0.0.1:8099", "HTTP/2 cleartext listen address (loopback only)")
	flag.Parse()
	log.SetOutput(os.Stderr)
	for _, a := range []string{*h1, *h2} {
		if err := loopback(a); err != nil {
			log.Fatal(err)
		}
	}
	s := &Server{}
	l1, err := net.Listen("tcp", *h1)
	if err != nil {
		log.Fatal(err)
	}
	l2, err := net.Listen("tcp", *h2)
	if err != nil {
		log.Fatal(err)
	}
	log.Printf("epl-streamorigin h1 %s h2 %s GOMAXPROCS %d", *h1, *h2, runtime.GOMAXPROCS(0))
	go func() { log.Fatal(H2Server(s).Serve(l2)) }()
	log.Fatal(s.ServeH1(l1))
}
