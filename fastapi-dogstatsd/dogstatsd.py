from fastapi import FastAPI
from datadog import initialize, statsd
import os

app = FastAPI()

options = {
    "statsd_host": os.getenv("DD_AGENT_HOST", "localhost"),
    "statsd_port": int(os.getenv("DD_DOGSTATSD_PORT", 8125)),
}
initialize(**options)

@app.get("/")
async def root():
    return {"message": "FastAPI with DogStatsD", "status": "healthy"}

@app.post("/test_increment_metric")
async def test_increment_metric():
    statsd.increment("test.metric", tags=["env:fargate", "key:value"])
    return {"message": "Metric incremented successfully."}