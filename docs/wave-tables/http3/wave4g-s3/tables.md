# g2-resume (wave4g-s3/g2s-resume): 8 rounds with valid legs
| Row | n | effect % [quoted interval] | t hw | widened hw | up | delta total | user | kernel | ins:u | cx/req | UDP out/req | arm cyc/req | busiest worker share |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A/A (h3r-A2 vs h3r) | 8 | +0.16 [-0.77, +1.08] | 0.77 | 0.92 | 5/8 | +25.6k +/- 124.3k/cx | +2.6k +/- 76.7k | +23.0k +/- 50.8k | -12.5k +/- 24.0k | 0.100 | 10.03 | 1608.6k | 0.253-0.263 |
| QUIC connection, v1.40.2 defaults (per connection) | 8 | +23.85 [+22.48, +25.23] | 1.37 | 1.32 | 8/8 | +3406.9k +/- 175.1k/cx | +3221.0k +/- 134.5k | +185.9k +/- 57.9k | +4468.3k +/- 33.0k | 0.100 | 10.02 | 1606.0k | 0.254-0.264 |
| QUIC connection, ticket guard on + shared key (per connection) | 8 | +23.19 [+21.86, +24.53] | 1.34 | 1.29 | 8/8 | +3301.1k +/- 169.4k/cx | +3134.0k +/- 136.7k | +167.1k +/- 42.6k | +4435.1k +/- 53.0k | 0.100 | 9.86 | 1595.4k | 0.252-0.263 |
| guard on + shared key vs default (per connection) | 8 | -0.66 [-1.39, +0.07] | 0.37 | 0.73 | 1/8 | -105.8k +/- 58.8k/cx | -87.1k +/- 45.2k | -18.8k +/- 24.6k | -33.2k +/- 31.9k | 0.100 | 9.86 | 1595.4k | 0.252-0.263 |
