# e-plain (e-plain): 6 rounds with valid legs
| Row | n | cycles/conn (total) | user | kernel | cx/req of the arm | arm cycles/req |
|---|---|---|---|---|---|---|
| plaintext connection (c1 - ka) | 6 | +238.7k +/- 7.0k | +85.9k +/- 4.5k | +152.8k +/- 2.7k | 1.000 | 870.2k |
| A/A (ka-A2 - ka) | 6 | +1.1k +/- 6.1k | -0.3k +/- 4.5k | +1.4k +/- 2.0k | 0.000 | 632.6k |
# e-tls (e-tls): 6 rounds with valid legs
| Row | n | cycles/conn (total) | user | kernel | cx/req of the arm | arm cycles/req |
|---|---|---|---|---|---|---|
| TLS connection, full handshake, ECDSA P-256 | 6 | +1145.1k +/- 7.9k | +840.1k +/- 4.8k | +305.0k +/- 3.4k | 1.000 | 1857.7k |
| TLS connection, full handshake, RSA-2048 | 6 | +3053.5k +/- 7.1k | +2752.5k +/- 4.7k | +301.1k +/- 3.6k | 1.000 | 3766.2k |
| TLS connection, resumed, ECDSA P-256 | 6 | +1158.3k +/- 9.4k | +850.0k +/- 5.3k | +308.3k +/- 5.1k | 1.000 | 1870.9k |
| TLS connection, full handshake, ECDSA, X25519 only | 6 | +996.6k +/- 7.5k | +691.3k +/- 4.6k | +305.2k +/- 3.5k | 1.000 | 1709.2k |
| certificate: RSA-2048 - ECDSA P-256 (per full handshake) | 6 | +1908.5k +/- 8.3k | +1912.4k +/- 3.7k | -3.9k +/- 5.3k | 1.000 | 3766.2k |
| resumption: resumed - full (ECDSA) | 6 | +13.3k +/- 12.1k | +10.0k +/- 7.5k | +3.3k +/- 5.8k | 1.000 | 1870.9k |
| group: X25519 - X25519MLKEM768 (per full handshake) | 6 | -148.5k +/- 9.2k | -148.7k +/- 5.6k | +0.3k +/- 4.5k | 1.000 | 1709.2k |
| A/A (ecdsa-full-A2 - ecdsa-full) | 6 | +5.2k +/- 9.9k | +2.3k +/- 7.1k | +2.9k +/- 2.9k | 1.000 | 1862.9k |
