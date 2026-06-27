"""worker.py — one process per CPU core.
Loads models once via preload.py, then serves inference requests
over a Unix domain socket using a simple 4-byte-length-prefix protocol.
"""
import os
import sys
import socket
import struct
import json
import traceback

import numpy as np
import pandas as pd

# preload.py loads all models into module globals — this is the slow part.
# We print READY only after this completes so Go knows we're warm.
from preload import predict_batch

SOCKET_PATH = os.environ["WORKER_SOCKET"]

# Signal to Go that we're ready
sys.stdout.write("READY\n")
sys.stdout.flush()

# ── socket server ─────────────────────────────────────────────────────────────

if os.path.exists(SOCKET_PATH):
    os.unlink(SOCKET_PATH)

server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
server.bind(SOCKET_PATH)
server.listen(1)

def recv_exact(conn, n):
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            raise ConnectionResetError("connection closed")
        buf += chunk
    return buf

def handle(conn):
    try:
        raw_len = recv_exact(conn, 4)
        length = struct.unpack("<I", raw_len)[0]
        body = recv_exact(conn, length)

        payload = json.loads(body)
        instances = payload["instances"]

        df = pd.DataFrame(instances)
        ids = df["ID"].tolist()

        scores = predict_batch(df)

        result = json.dumps({
            "predictions": [
                {"ID": id_, "prediction": float(s)}
                for id_, s in zip(ids, scores)
            ]
        }).encode()

        conn.sendall(struct.pack("<I", len(result)) + result)

    except Exception:
        traceback.print_exc(file=sys.stderr)
        # Send empty error response so Go doesn't hang
        error_resp = json.dumps({"predictions": [], "error": "inference failed"}).encode()
        try:
            conn.sendall(struct.pack("<I", len(error_resp)) + error_resp)
        except Exception:
            pass

while True:
    conn, _ = server.accept()
    with conn:
        handle(conn)
