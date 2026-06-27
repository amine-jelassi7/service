# Vitalseq Inference Service

Go HTTP frontend + Python worker pool for the HCT survival risk model.

## Architecture

```
[grader] → port 8080 → Go HTTP server (net/http)
                          ├── GET  /health  → {"status":"ok"}
                          └── POST /predict → Unix socket → Python worker
                                                              ↓
                                                     preload.py (models in RAM)
                                                     predict_batch(df) → scores
```

- **Go server**: thin, async, zero-copy HTTP. Dispatches each request to a
  Python worker via Unix domain socket (4-byte length prefix + JSON).
- **Python workers**: one per CPU core. Models are loaded once at startup into
  module globals. The hot path has zero disk I/O.
- **Worker pool**: Go channel acts as a semaphore — if all workers are busy,
  new requests queue rather than fail.

## VM layout expected

```
/opt/app/               (or wherever you clone to)
  repo/                 DS handover — must be present on VM
    src/
    models/
    data/
    predict.py
    requirements.txt
  service/              THIS directory
    main.go
    worker.go
    go.mod
    worker/
      preload.py
      worker.py
    smoke_test.py
  start.sh
```

## Deployment (run once on the VM)

```bash
# 1. Clone / copy files
git clone <your-repo> /opt/app
cd /opt/app

# 2. Install Python deps (uses DS team's exact versions)
pip install -r repo/requirements.txt

# 3. Build Go server
cd service
go build -o server .

# 4. Start (from project root so paths resolve correctly)
cd /opt/app
PYTHONPATH=/opt/app/repo bash start.sh
```

Or just:
```bash
cd /opt/app && bash start.sh
```

## Smoke test (run before submitting!)

With the service running in one terminal, in another:

```bash
# Full HTTP smoke test
python3 service/smoke_test.py

# Direct test of predict_batch() without HTTP (good for debugging preload)
python3 service/smoke_test.py --direct
```

## Troubleshooting

**Worker fails to start**: Check stderr — Python import errors will appear there.
The most common cause is PYTHONPATH not including `repo/`.

**Predictions differ from predict_frame()**: Run `smoke_test.py --direct` and
compare output with `python3 repo/predict.py`. If they differ, check preload.py's
monkey-patch section — features.py might use different internal variable names
for the OHE / data dict.

**Port 8080 already in use**: `kill $(lsof -ti:8080)` then restart.

**Workers timeout on startup**: Model loading takes ~10-20s per worker on cold start.
The Go server waits up to 120s for each READY signal.
