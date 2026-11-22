# e2b-plain (e2b/e2b-plain): 8 rounds with valid legs
| Row | n | cycles/conn (total) | user | kernel | cx/req of the arm | arm cycles/req |
|---|---|---|---|---|---|---|
| plaintext connection again (c1 - ka; E: 238.7k +/- 7.0k) | 8 | +240.1k +/- 4.5k | +86.4k +/- 2.7k | +153.6k +/- 2.1k | 1.000 | 873.1k |
| TCP_DEFER_ACCEPT 1 s (per connection) | 8 | -4.5k +/- 5.4k | -0.5k +/- 3.1k | -4.0k +/- 2.5k | 1.000 | 868.6k |
| A/A (c1-A2 - c1) | 8 | -0.5k +/- 6.3k | +0.6k +/- 3.2k | -1.2k +/- 3.3k | 1.000 | 872.6k |
