# from fastapi import FastAPI

# app = FastAPI()

# @app.get("/")
# async def health_check():
#     return {"status": "ok"}

# index.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
from pathlib import Path
from statistics import mean

app = FastAPI()

# Enable CORS for any origin, POST allowed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request model
class MetricsRequest(BaseModel):
    regions: list[str]
    threshold_ms: int

# Load data once
DATA_FILE = Path(__file__).with_name("q-vercel-latency.json")
with DATA_FILE.open("r", encoding="utf-8") as f:
    DATA = json.load(f)

def p95(values: list[float]) -> float:
    if not values:
        return 0.0
    xs = sorted(values)
    rank = max(1, int(round(0.95 * len(xs))))
    return xs[rank - 1]

@app.middleware("http")
async def add_cors_header(request, call_next):
    response = await call_next(request)
    if "access-control-allow-origin" not in response.headers:
        response.headers["access-control-allow-origin"] = "*"
    return response

@app.get("/")
def root_info():
    return {
        "message": "Use POST /metrics with JSON {\"regions\": [...], \"threshold_ms\": 180}"
    }

@app.post("/metrics")
def compute_metrics(req: MetricsRequest):
    req_regions = {r.lower() for r in req.regions}
    rows = [r for r in DATA if r["region"].lower() in req_regions]

    if not rows:
        raise HTTPException(status_code=404, detail="No data for requested regions")

    results = {}
    for region in req_regions:
        region_rows = [r for r in rows if r["region"].lower() == region]
        if not region_rows:
            continue
        latencies = [r["latency_ms"] for r in region_rows]
        uptimes   = [r["uptime_pct"] for r in region_rows]
        breaches  = sum(1 for v in latencies if v > req.threshold_ms)

        results[region] = {
            "avg_latency": mean(latencies),
            "p95_latency": p95(latencies),
            "avg_uptime": mean(uptimes),
            "breaches": breaches
        }

    return {"threshold_ms": req.threshold_ms, "regions": results}
