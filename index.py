from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from pathlib import Path
from statistics import mean
import json

app = FastAPI()

# CORS: wildcard, no credentials so it emits '*' literally
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Make absolutely sure every response has the header
@app.middleware("http")
async def force_cors_header(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("Access-Control-Allow-Origin", "*")
    return resp

class MetricsRequest(BaseModel):
    regions: list[str]
    threshold_ms: int

DATA = json.loads(Path("q-vercel-latency.json").read_text())

def p95(vals: list[float]) -> float:
    if not vals: return 0.0
    xs = sorted(vals)
    idx = max(1, round(0.95 * len(xs))) - 1
    return float(xs[idx])

@app.options("/{path:path}")
def preflight_any(path: str):
    return Response(status_code=204, headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS,PUT,PATCH,DELETE",
        "Access-Control-Allow-Headers": "*",
        "Access-Control-Max-Age": "600"
    })

@app.get("/")
def root():
    return JSONResponse({"message":"POST /metrics with {\"regions\":[...],\"threshold_ms\":180}"},
                        headers={"Access-Control-Allow-Origin":"*"})

@app.get("/metrics")
def info():
    return JSONResponse({"message":"POST JSON to this path"},
                        headers={"Access-Control-Allow-Origin":"*"})

@app.post("/metrics")
def metrics(req: MetricsRequest):
    regions = {r.lower() for r in req.regions}
    rows = [r for r in DATA if r.get("region","").lower() in regions]
    if not rows:
        return JSONResponse({"detail":"No data for requested regions"}, status_code=404,
                            headers={"Access-Control-Allow-Origin":"*"})
    out = {}
    for region in regions:
        rrows = [r for r in rows if r["region"].lower() == region]
        if not rrows: continue
        lats = [float(r["latency_ms"]) for r in rrows]
        ups  = [float(r["uptime_pct"]) for r in rrows]
        breaches = sum(1 for v in lats if v > req.threshold_ms)
        out[region] = {
            "avg_latency": float(mean(lats)),
            "p95_latency": p95(lats),
            "avg_uptime": float(mean(ups)),
            "breaches": int(breaches)
        }
    return JSONResponse({"threshold_ms": int(req.threshold_ms), "regions": out},
                        headers={"Access-Control-Allow-Origin":"*"})
