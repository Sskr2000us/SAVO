web: cd services/api && uvicorn app.main:app --host 0.0.0.0 --port $PORT

# Background worker for durable video scan processing
worker: cd services/api && python -m app.workers.video_scan_worker
