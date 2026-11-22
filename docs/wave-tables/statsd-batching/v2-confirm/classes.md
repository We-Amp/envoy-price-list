# Datagram split (v2 confirmation run)

In window, from the receiver's 5 s marks (marks 3 to 7, 20 s, every statsd leg; requests = SUT 2xx rate x the
marks' span). This replaces an earlier whole-leg class-share table that understated the split.

| Arm | sample (ms) datagrams/req | flush (c+g) datagrams/req |
|---|---|---|
| ctl-statsd | 3.012 | 1.201 |
| ctl-statsd-A2 | 3.012 | 1.201 |
| v2-statsd-512 | 1.002 | 0.201 |
