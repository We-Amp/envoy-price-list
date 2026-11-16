#!/usr/bin/env python3
"""Make the test key, the local JWKS and the signed token of the JWT row (filters.py).

    python3 examples/settings-matrix/jwt_token.py > examples/settings-matrix/filters/jwt.json

Generates a fresh RSA-2048 key with openssl in a temporary directory, writes the public
half as a one-key JWKS (kid "epl-rs256"), signs one RS256 token with it and prints
{"jwks": ..., "token": ...}. The private key is deleted with the directory: the
experiment only needs the public JWKS (the proxy verifies) and the token (the client
sends it on every request). Claims: issuer https://epl.example, audience epl, no
not-before, expiry 2100-01-01.
"""

import base64
import json
import os
import subprocess
import sys
import tempfile

ISSUER = "https://epl.example"
AUDIENCE = "epl"
KID = "epl-rs256"


def b64u(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def b64u_int(n):
    return b64u(n.to_bytes((n.bit_length() + 7) // 8, "big"))


def main():
    with tempfile.TemporaryDirectory() as d:
        key = os.path.join(d, "k.pem")
        subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048",
                        "-out", key], check=True, capture_output=True)
        mod = subprocess.run(["openssl", "rsa", "-in", key, "-noout", "-modulus"], check=True,
                             capture_output=True, text=True).stdout.strip()
        n = int(mod.split("=", 1)[1], 16)
        jwks = {"keys": [{"kty": "RSA", "alg": "RS256", "use": "sig", "kid": KID, "n": b64u_int(n),
                          "e": b64u_int(65537)}]}
        header = {"alg": "RS256", "typ": "JWT", "kid": KID}
        claims = {"iss": ISSUER, "sub": "epl-client", "aud": AUDIENCE, "iat": 1763164800, "exp": 4102444800}
        signing_input = (b64u(json.dumps(header, separators=(",", ":")).encode()) + "." +
                         b64u(json.dumps(claims, separators=(",", ":")).encode()))
        sig = subprocess.run(["openssl", "dgst", "-sha256", "-sign", key], input=signing_input.encode(),
                             check=True, capture_output=True).stdout
    json.dump({"issuer": ISSUER, "audience": AUDIENCE, "jwks": json.dumps(jwks, separators=(",", ":")),
               "token": signing_input + "." + b64u(sig)}, sys.stdout, indent=1)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
