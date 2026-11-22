# g1-proto (wave4g/g1-proto): 8 rounds with valid legs
| Row | n | effect % [quoted interval] | t hw | widened hw | up | delta total | user | kernel | ins:u | cx/req | UDP out/req | arm cyc/req | busiest worker share |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A/A (h3-A2 vs h3) | 8 | +0.33 [-2.37, +3.02] | 2.70 | 2.33 | 4/8 | +4.2k +/- 34.2k/req | +0.3k +/- 24.9k | +3.9k +/- 10.7k | +0.5k +/- 9.6k | 0.000 | 7.02 | 1274.1k | 0.298-0.456 |
| HTTP/3 vs HTTP/2 over TLS | 8 | +55.83 [+54.33, +57.33] | 1.50 | 1.41 | 8/8 | +543.4k +/- 20.5k/req | +432.3k +/- 14.6k | +111.0k +/- 6.7k | +310.7k +/- 7.3k | 0.000 | 7.02 | 1269.8k | 0.254-0.411 |
| HTTP/3 without the GSO writer vs with it | 8 | +6.16 [+3.95, +8.37] | 2.21 | 1.95 | 8/8 | +80.5k +/- 28.4k/req | +47.9k +/- 19.4k | +32.6k +/- 10.0k | +43.2k +/- 8.4k | 0.000 | 9.02 | 1350.4k | 0.299-0.449 |
| HTTP/3 without GSO vs HTTP/2 over TLS | 8 | +61.99 [+60.82, +63.17] | 1.17 | 1.18 | 8/8 | +623.9k +/- 13.7k/req | +480.2k +/- 8.7k | +143.7k +/- 6.5k | +353.9k +/- 4.0k | 0.000 | 9.02 | 1350.4k | 0.299-0.449 |
