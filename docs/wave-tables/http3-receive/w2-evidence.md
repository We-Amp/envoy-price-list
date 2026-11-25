
## s-1: 36 current legs, 18 replaced

- replaced: r01-s-h3-off (round 1, arm h3-off): valid False; Envoy load uneven: busiest worker did 50.1% of worker CPU, limit 50.0% (4 workers)
- replaced: r01-s-h3-both-on (round 1, arm h3-both-on): valid True; its round was replaced because of another leg
- replaced: r01-s-h3-official (round 1, arm h3-official): valid True; its round was replaced because of another leg
- replaced: r01-s-h3-stop-on (round 1, arm h3-stop-on): valid True; its round was replaced because of another leg
- replaced: r01-s-h3-official-A2 (round 1, arm h3-official-A2): valid True; its round was replaced because of another leg
- replaced: r01-s-h2tls (round 1, arm h2tls): valid True; its round was replaced because of another leg
- replaced: r05-s-h3-official-A2 (round 5, arm h3-official-A2): valid True; its round was replaced because of another leg
- replaced: r05-s-h3-official (round 5, arm h3-official): valid False; Envoy load uneven: busiest worker did 56.5% of worker CPU, limit 50.0% (4 workers)
- replaced: r05-s-h2tls (round 5, arm h2tls): valid True; its round was replaced because of another leg
- replaced: r05-s-h3-off (round 5, arm h3-off): valid True; its round was replaced because of another leg
- replaced: r05-s-h3-stop-on (round 5, arm h3-stop-on): valid True; its round was replaced because of another leg
- replaced: r05-s-h3-both-on (round 5, arm h3-both-on): valid True; its round was replaced because of another leg
- replaced: r06-s-h3-official (round 6, arm h3-official): valid True; its round was replaced because of another leg
- replaced: r06-s-h3-off (round 6, arm h3-off): valid True; its round was replaced because of another leg
- replaced: r06-s-h3-official-A2 (round 6, arm h3-official-A2): valid False; Envoy load uneven: busiest worker did 51.0% of worker CPU, limit 50.0% (4 workers)
- replaced: r06-s-h3-both-on (round 6, arm h3-both-on): valid True; its round was replaced because of another leg
- replaced: r06-s-h2tls (round 6, arm h2tls): valid True; its round was replaced because of another leg
- replaced: r06-s-h3-stop-on (round 6, arm h3-stop-on): valid True; its round was replaced because of another leg

| arm | legs valid | evidence passing (items per leg) | sha256 equals the pin | guards at start / at end (ch, st, ru) | responses in the window | client 2xx/s over target | bytes/req Envoy to origin | origin to Envoy | Envoy to client | UDP datagrams/req | new or destroyed connections in the window (client side / origin side) | error counters above zero (window sum; end-of-leg sum) | Envoy exit codes | client headroom | busiest worker share | latency max µs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| h2tls | 6/6 | 6/6 (58) | 6/6 | [-1, -1, -1] / [-1, -1, -1] (expected [-1, -1, -1]) | 40090 to 40121 | 1.00000 to 1.00000 | 159.000 | 4350.891 to 4351.108 | 4151.080 to 4151.287 | 0.0000 to 0.0000 | 0 / 1 | none; none | [0] | 0.78 to 0.78 | 0.255 to 0.274 | 1041 to 1338 |
| h3-official | 6/6 | 6/6 (55) | 6/6 | [-1, -1, -1] / [-1, -1, -1] (expected [-1, -1, -1]) | 40084 to 40104 | 1.00000 to 1.00000 | 159.000 to 159.004 | 4350.891 to 4351.109 | 4293.596 to 4293.780 | 7.0163 to 7.0167 | 0 / 2 | none; none | [0] | 0.75 to 0.76 | 0.307 to 0.400 | 3080 to 4701 |
| h3-official-A2 | 6/6 | 6/6 (55) | 6/6 | [-1, -1, -1] / [-1, -1, -1] (expected [-1, -1, -1]) | 40086 to 40119 | 1.00000 to 1.00000 | 159.000 | 4350.892 to 4351.109 | 4293.627 to 4293.674 | 7.0164 to 7.0167 | 0 / 0 | none; none | [0] | 0.75 to 0.76 | 0.346 to 0.461 | 3201 to 14590 |
| h3-off | 6/6 | 6/6 (57) | 6/6 | [1, 0, 0] / [1, 0, 0] (expected [1, 0, 0]) | 40087 to 40107 | 1.00000 to 1.00000 | 158.996 to 159.000 | 4350.891 to 4351.000 | 4293.566 to 4293.676 | 7.0163 to 7.0166 | 0 / 0 | none; none | [0] | 0.74 to 0.76 | 0.304 to 0.457 | 2327 to 23177 |
| h3-stop-on | 6/6 | 6/6 (57) | 6/6 | [1, 1, 0] / [1, 1, 0] (expected [1, 1, 0]) | 40087 to 40105 | 1.00000 to 1.00000 | 159.000 to 159.004 | 4351.000 to 4351.109 | 4293.669 to 4293.778 | 7.0164 to 7.0166 | 0 / 0 | none; none | [0] | 0.75 to 0.76 | 0.307 to 0.416 | 2281 to 18323 |
| h3-both-on | 6/6 | 6/6 (57) | 6/6 | [1, 1, 1] / [1, 1, 1] (expected [1, 1, 1]) | 40084 to 40106 | 1.00000 to 1.00000 | 158.996 to 159.004 | 4350.891 to 4351.109 | 4293.565 to 4293.777 | 7.0163 to 7.0167 | 0 / 0 | none; none | [0] | 0.75 to 0.76 | 0.304 to 0.472 | 2577 to 26452 |

## s-2: 36 current legs, 6 replaced

- replaced: r01-s-h2tls (round 1, arm h2tls): valid True; its round was replaced because of another leg
- replaced: r01-s-h3-both-on (round 1, arm h3-both-on): valid False; Envoy load uneven: busiest worker did 50.4% of worker CPU, limit 50.0% (4 workers)
- replaced: r01-s-h3-official (round 1, arm h3-official): valid True; its round was replaced because of another leg
- replaced: r01-s-h3-stop-on (round 1, arm h3-stop-on): valid True; its round was replaced because of another leg
- replaced: r01-s-h3-off (round 1, arm h3-off): valid True; its round was replaced because of another leg
- replaced: r01-s-h3-official-A2 (round 1, arm h3-official-A2): valid True; its round was replaced because of another leg

| arm | legs valid | evidence passing (items per leg) | sha256 equals the pin | guards at start / at end (ch, st, ru) | responses in the window | client 2xx/s over target | bytes/req Envoy to origin | origin to Envoy | Envoy to client | UDP datagrams/req | new or destroyed connections in the window (client side / origin side) | error counters above zero (window sum; end-of-leg sum) | Envoy exit codes | client headroom | busiest worker share | latency max µs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| h2tls | 6/6 | 6/6 (58) | 6/6 | [-1, -1, -1] / [-1, -1, -1] (expected [-1, -1, -1]) | 40087 to 40104 | 1.00000 to 1.00000 | 159.000 | 4350.892 to 4351.000 | 4151.080 to 4151.199 | 0.0000 | 0 / 0 | none; none | [0] | 0.78 to 0.78 | 0.254 to 0.279 | 1234 to 1370 |
| h3-official | 6/6 | 6/6 (55) | 6/6 | [-1, -1, -1] / [-1, -1, -1] (expected [-1, -1, -1]) | 40087 to 40098 | 1.00000 to 1.00000 | 159.000 | 4350.891 to 4351.109 | 4293.568 to 4293.675 | 7.0163 to 7.0166 | 0 / 0 | none; none | [0] | 0.75 to 0.76 | 0.299 to 0.416 | 2979 to 8172 |
| h3-official-A2 | 6/6 | 6/6 (55) | 6/6 | [-1, -1, -1] / [-1, -1, -1] (expected [-1, -1, -1]) | 40085 to 40103 | 1.00000 to 1.00000 | 159.000 | 4351.000 to 4351.108 | 4293.670 to 4293.675 | 7.0163 to 7.0166 | 0 / 0 | none; none | [0] | 0.75 to 0.75 | 0.307 to 0.406 | 2549 to 9574 |
| h3-off | 6/6 | 6/6 (57) | 6/6 | [1, 0, 0] / [1, 0, 0] (expected [1, 0, 0]) | 40085 to 40099 | 1.00000 to 1.00000 | 158.996 to 159.004 | 4350.891 to 4351.109 | 4293.565 to 4293.776 | 7.0164 to 7.0166 | 0 / 0 | none; none | [0] | 0.75 to 0.75 | 0.307 to 0.463 | 2847 to 18060 |
| h3-stop-on | 6/6 | 6/6 (57) | 6/6 | [1, 1, 0] / [1, 1, 0] (expected [1, 1, 0]) | 40092 to 40108 | 1.00000 to 1.00000 | 159.000 to 159.004 | 4350.891 to 4351.000 | 4293.565 to 4293.675 | 7.0164 to 7.0166 | 0 / 0 | none; none | [0] | 0.74 to 0.76 | 0.307 to 0.416 | 3666 to 11651 |
| h3-both-on | 6/6 | 6/6 (57) | 6/6 | [1, 1, 1] / [1, 1, 1] (expected [1, 1, 1]) | 40089 to 40103 | 1.00000 to 1.00000 | 158.996 to 159.000 | 4350.891 to 4351.109 | 4293.566 to 4293.778 | 7.0165 to 7.0166 | 0 / 0 | none; none | [0] | 0.75 to 0.75 | 0.302 to 0.420 | 2746 to 19618 |
