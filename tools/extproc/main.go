// epl-extproc: a minimal ext_proc service for the price list (Go standard library only).
//
// It serves envoy.service.ext_proc.v3.ExternalProcessor/Process over h2c (prior knowledge, the
// way Envoy's envoy_grpc and google_grpc clients connect) and answers every ProcessingRequest
// with the empty response of the same phase: request headers -> HeadersResponse{} in field 1,
// response headers -> field 2, and so on. An empty HeadersResponse carries no CommonResponse,
// which Envoy reads as CONTINUE without a mutation. The service does no work of its own, so the
// row prices Envoy's side of the protocol, not the server's logic.
//
// It parses only the outer field number of each ProcessingRequest (the oneof `request`, fields
// 2 to 7); nothing else of the message is decoded. Messages that carry none of those fields
// (protocol_config alone, flow-control updates) get no answer. When Envoy closes or resets the
// stream, the handler returns with grpc-status 0 as a trailer.
//
// GET /epl-stats (HTTP/1.1 or h2c, same port) returns the counters as JSON, for the smoke; the
// harness never reads it inside a measurement window.
//
//	epl-extproc -addr 127.0.0.1:8095
package main

import (
	"encoding/binary"
	"encoding/json"
	"errors"
	"flag"
	"io"
	"log"
	"net/http"
	"os"
	"sync/atomic"
)

const processPath = "/envoy.service.ext_proc.v3.ExternalProcessor/Process"

// maxMessage bounds one request message (bodies are not sent in these rows; 4 MiB is gRPC's
// default receive limit).
const maxMessage = 4 << 20

// phaseNames by ProcessingRequest field number.
var phaseNames = map[int]string{
	2: "request_headers", 3: "response_headers", 4: "request_body",
	5: "response_body", 6: "request_trailers", 7: "response_trailers",
}

// responses[f] is the gRPC frame of the empty ProcessingResponse for request field f: the
// response oneof field is f-1 (request_headers 2 -> 1, ..., response_trailers 7 -> 6), wire
// type 2, length 0.
var responses = func() map[int][]byte {
	out := map[int][]byte{}
	for f := 2; f <= 7; f++ {
		out[f] = Frame([]byte{byte((f-1)<<3 | 2), 0})
	}
	return out
}()

// Frame wraps one protobuf message in a gRPC length-prefixed frame (uncompressed).
func Frame(msg []byte) []byte {
	b := make([]byte, 5+len(msg))
	binary.BigEndian.PutUint32(b[1:5], uint32(len(msg)))
	copy(b[5:], msg)
	return b
}

func uvarint(b []byte) (uint64, int) {
	v, n := binary.Uvarint(b)
	if n <= 0 {
		return 0, -1
	}
	return v, n
}

// Phase returns the field number (2..7) of the request oneof set in a ProcessingRequest, 0 when
// none is set, and -1 when the message does not parse.
func Phase(b []byte) int {
	for i := 0; i < len(b); {
		tag, n := uvarint(b[i:])
		if n < 0 {
			return -1
		}
		i += n
		field, wt := int(tag>>3), tag&7
		switch wt {
		case 0:
			_, n = uvarint(b[i:])
			if n < 0 {
				return -1
			}
			i += n
		case 1:
			i += 8
		case 5:
			i += 4
		case 2:
			l, n := uvarint(b[i:])
			if n < 0 || uint64(len(b)-i-n) < l {
				return -1
			}
			i += n
			if field >= 2 && field <= 7 {
				return field
			}
			i += int(l)
		default:
			return -1
		}
		if i > len(b) {
			return -1
		}
	}
	return 0
}

// Stats are the service's own counters.
type Stats struct {
	Streams   atomic.Int64
	Messages  [8]atomic.Int64 // by request field number; [0] = no phase field
	Responses atomic.Int64
	Errors    atomic.Int64
}

func (s *Stats) snapshot() map[string]int64 {
	out := map[string]int64{"streams": s.Streams.Load(), "responses": s.Responses.Load(),
		"errors": s.Errors.Load(), "messages_without_phase": s.Messages[0].Load()}
	for f, name := range phaseNames {
		out[name] = s.Messages[f].Load()
	}
	return out
}

// Handler serves Process and /epl-stats.
func Handler(st *Stats) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/epl-stats", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(st.snapshot())
	})
	mux.HandleFunc(processPath, func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost || r.ProtoMajor != 2 {
			http.Error(w, "gRPC over HTTP/2 only", http.StatusBadRequest)
			return
		}
		st.Streams.Add(1)
		h := w.Header()
		h.Set("Content-Type", "application/grpc")
		h.Set("Trailer", "Grpc-Status")
		w.WriteHeader(http.StatusOK)
		rc := http.NewResponseController(w)
		var pre [5]byte
		buf := make([]byte, 0, 4096)
		for {
			if _, err := io.ReadFull(r.Body, pre[:]); err != nil {
				break // end of stream or reset: done
			}
			n := binary.BigEndian.Uint32(pre[1:5])
			if pre[0] != 0 || n > maxMessage {
				st.Errors.Add(1)
				break
			}
			if cap(buf) < int(n) {
				buf = make([]byte, n)
			}
			buf = buf[:n]
			if _, err := io.ReadFull(r.Body, buf); err != nil {
				break
			}
			f := Phase(buf)
			if f < 0 {
				st.Errors.Add(1)
				break
			}
			st.Messages[f].Add(1)
			if f == 0 {
				continue
			}
			if _, err := w.Write(responses[f]); err != nil {
				break
			}
			if err := rc.Flush(); err != nil {
				break
			}
			st.Responses.Add(1)
		}
		h.Set("Grpc-Status", "0")
	})
	return mux
}

// NewServer returns an HTTP/1.1 + h2c (prior knowledge) server for addr.
func NewServer(addr string, st *Stats) *http.Server {
	var p http.Protocols
	p.SetHTTP1(true)
	p.SetUnencryptedHTTP2(true)
	return &http.Server{Addr: addr, Handler: Handler(st), Protocols: &p,
		HTTP2:    &http.HTTP2Config{MaxConcurrentStreams: 1 << 16},
		ErrorLog: log.New(io.Discard, "", 0)}
}

func main() {
	addr := flag.String("addr", "127.0.0.1:8095", "listen address")
	flag.Parse()
	st := &Stats{}
	srv := NewServer(*addr, st)
	log.SetOutput(os.Stderr)
	log.Printf("epl-extproc listening on %s", *addr)
	if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		log.Fatal(err)
	}
}
