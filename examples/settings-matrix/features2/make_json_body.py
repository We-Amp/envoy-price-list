#!/usr/bin/env python3
"""Write the synthetic JSON bodies of row 14 (compression):

    python3 examples/settings-matrix/features2/make_json_body.py

  bodies/j4.json    4,096 bytes
  bodies/j16.json  16,384 bytes

An API-style response: a compact JSON object with a list of records, each with field
names, an ISO 8601 timestamp, a UUID, short strings and numbers, written by a seeded
generator (the same bytes on every machine and Python 3 version). Text with repeated keys
and high-entropy values, so a compressor's ratio is neither the best nor the worst case.
Only reserved names are used (example.com, .test). The last record carries a filler
string so the document is exactly the target size. bodies/SHA256SUMS holds the digests
that the configs carry and the harness checks.
"""

import hashlib
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "bodies")
SEED = 20261117
SIZES = {"j4.json": 4096, "j16.json": 16384}
WORDS = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel", "india", "juliet",
         "kilo", "lima", "mike", "november", "oscar", "papa", "quebec", "romeo", "sierra", "tango"]
STATUS = ["active", "pending", "suspended", "closed"]
REGIONS = ["eu-west", "eu-north", "us-east", "us-west", "ap-south"]


def uuid4(r):
    b = bytearray(r.getrandbits(8) for _ in range(16))
    b[6] = (b[6] & 0x0F) | 0x40
    b[8] = (b[8] & 0x3F) | 0x80
    h = b.hex()
    return "%s-%s-%s-%s-%s" % (h[:8], h[8:12], h[12:16], h[16:20], h[20:])


def timestamp(r):
    return "2026-%02d-%02dT%02d:%02d:%02d.%03dZ" % (r.randint(1, 12), r.randint(1, 28), r.randint(0, 23),
                                                   r.randint(0, 59), r.randint(0, 59), r.randint(0, 999))


def record(r, i):
    user = "%s.%s%d" % (r.choice(WORDS), r.choice(WORDS), r.randint(1, 999))
    return {
        "id": uuid4(r),
        "seq": i,
        "created_at": timestamp(r),
        "updated_at": timestamp(r),
        "user": {"name": user, "email": user + "@example.com", "verified": r.random() < 0.7},
        "status": r.choice(STATUS),
        "region": r.choice(REGIONS),
        "host": "api-%d.%s.example.test" % (r.randint(1, 9), r.choice(REGIONS)),
        "amount": round(r.uniform(0, 5000), 2),
        "currency": "EUR",
        "items": r.randint(1, 40),
        "score": round(r.random(), 4),
        "tags": sorted(r.sample(WORDS, 3)),
    }


def dump(doc):
    return json.dumps(doc, separators=(",", ":"), sort_keys=False, ensure_ascii=True).encode()


def body(size, seed=SEED):
    """A JSON document of exactly `size` bytes."""
    r = random.Random("%d:%d" % (seed, size))
    doc = {"page": 1, "per_page": 0, "total": 0, "next": None, "data": []}
    while True:
        rec = record(r, len(doc["data"]) + 1)
        trial = dict(doc, data=doc["data"] + [rec])
        trial["per_page"] = trial["total"] = len(trial["data"])
        # leave room for the filler field on the last record
        if len(dump(trial)) + len(',"note":""') > size:
            break
        doc = trial
    if not doc["data"]:
        raise ValueError("size %d too small for one record" % size)
    doc["data"][-1]["note"] = ""
    need = size - len(dump(doc))
    doc["data"][-1]["note"] = "".join(r.choice("abcdefghijklmnopqrstuvwxyz ") for _ in range(need))
    out = dump(doc)
    assert len(out) == size, (len(out), size)
    json.loads(out)
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    sums = []
    for name, size in SIZES.items():
        b = body(size)
        with open(os.path.join(OUT, name), "wb") as f:
            f.write(b)
        sums.append("%s  %s" % (hashlib.sha256(b).hexdigest(), name))
        print(sums[-1])
    with open(os.path.join(OUT, "SHA256SUMS"), "w") as f:
        f.write("\n".join(sums) + "\n")


if __name__ == "__main__":
    main()
