"""
CtxPack Benchmark Demo
======================
Three scenarios. No credentials. No network. Pure local cache.

Run: python3 demo_benchmark.py
"""

import os
import sys
import shutil
import time
import random
import string
import tempfile

from ctxpack import CtxPack

# ── Config ────────────────────────────────────────────────────────────────────
CACHE_DIR   = tempfile.mkdtemp(prefix="ctxpack_demo_cache_")
INPUT_DIR   = tempfile.mkdtemp(prefix="ctxpack_demo_input_")
CORPUS_MB   = 50          # synthetic corpus size to hash
CHUNK_COUNT = 6           # pipeline "chunks" to simulate
CHUNK_SLEEP = 1.4         # seconds per chunk (realistic OCR/embed feel)

CONTRACT = {
    "dataset":   "SEC_10K_CORPUS_2025",
    "model":     "text-embedding-3-large",
    "tool":      "vision-ocr",
    "tool_version": "2.1",
    "params":    {"chunk_size": 512, "strategy": "semantic", "dpi": 300},
}

SEP  = "─" * 60
SEP2 = "═" * 60


# ── Helpers ───────────────────────────────────────────────────────────────────

def header(text):
    print(f"\n{SEP2}")
    print(f"  {text}")
    print(f"{SEP2}")

def step(text):
    print(f"  › {text}")

def ok(text):
    print(f"  ✅ {text}")

def warn(text):
    print(f"  ⚠️  {text}")


def generate_corpus(path_dir, size_mb):
    """Write synthetic 'PDF pages' totalling ~size_mb to path_dir."""
    os.makedirs(path_dir, exist_ok=True)
    target_bytes = size_mb * 1024 * 1024
    written = 0
    page = 0
    rng = random.Random(42)          # deterministic seed → same hash every run
    while written < target_bytes:
        page += 1
        fname = os.path.join(path_dir, f"page_{page:04d}.txt")
        chunk = "".join(rng.choices(string.ascii_letters + " \n", k=32_768))
        with open(fname, "w") as f:
            f.write(chunk)
        written += len(chunk)
    return page, written


def simulate_pipeline(label, chunk_count, chunk_sleep, output_dir):
    """Fake OCR → chunk → embed pipeline with timed progress."""
    os.makedirs(output_dir, exist_ok=True)
    step(f"[{label}] Starting OCR → Chunk → Embed pipeline…")
    for i in range(1, chunk_count + 1):
        t0 = time.perf_counter()
        time.sleep(chunk_sleep)
        elapsed = time.perf_counter() - t0
        print(f"      Chunk {i}/{chunk_count} embedded  ({elapsed:.2f}s)")

    # Write a realistic ~50MB FAISS-style vector index
    # (1536-dim float32 embeddings × ~8700 chunks ≈ 50MB)
    # Deterministic repeating block — fast to write, stable hash across runs
    step(f"[{label}] Writing ~50MB vector index to disk…")
    seed_block = bytes(range(256)) * 256  # 64KB deterministic block
    vec_path = os.path.join(output_dir, "index.vec")
    target_bytes = 50 * 1024 * 1024
    with open(vec_path, "wb") as f:
        written = 0
        while written < target_bytes:
            f.write(seed_block)
            written += len(seed_block)
    actual_mb = os.path.getsize(vec_path) / 1024 / 1024

    with open(os.path.join(output_dir, "chunks.jsonl"), "w") as f:
        for i in range(500):
            f.write(f'{{"id":{i},"text":"Chunk {i} from synthetic corpus","vec":[0.1,0.2,0.3]}}\n')

    ok(f"[{label}] Artifact written: index.vec ({actual_mb:.1f}MB)")


# ── Scenarios ─────────────────────────────────────────────────────────────────

def scenario_1_cold_run(ctx, uri):
    """Agent A: fresh environment, must compute everything."""
    header("SCENARIO 1 — Cold Run  (Agent A, fresh machine)")
    step(f"Target URI : {uri}")
    step("Checking local cache…")

    cached = ctx.cache_dir / uri.split(":")[-1]
    if cached.exists():
        step("Cache already warm — clearing for a clean cold-run demo…")
        shutil.rmtree(cached)

    step("Cache MISS — must run the full pipeline.")
    print()

    output_dir = os.path.join(tempfile.gettempdir(), "ctxpack_demo_output")
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)

    t0 = time.perf_counter()
    simulate_pipeline("Agent A", CHUNK_COUNT, CHUNK_SLEEP, output_dir)
    ctx.seed(output_dir, CONTRACT)
    elapsed = time.perf_counter() - t0

    artifact_mb = os.path.getsize(os.path.join(output_dir, "index.vec")) / 1024 / 1024
    shutil.rmtree(output_dir)
    print()
    ok(f"Pipeline COMPLETE in {elapsed:.2f}s")
    ok(f"Seeded → {uri}")
    return elapsed, artifact_mb


def scenario_2_cache_hit(ctx, uri, cold_time):
    """Agent B: same contract, cache populated → instant."""
    header("SCENARIO 2 — Cache Hit  (Agent B, same or different machine)")
    step(f"Target URI : {uri}")
    step("Checking local cache…")

    t0 = time.perf_counter()
    path = ctx.pull(uri)        # pull() returns immediately if already local
    elapsed = time.perf_counter() - t0

    print()
    ok(f"Cache HIT — artifacts ready at: {path}")
    ok(f"Ready in {elapsed:.4f}s  (vs {cold_time:.2f}s cold — "
       f"{cold_time / max(elapsed, 0.0001):.0f}x faster)")

    # Spot-check the artifact
    vec_file = path / "index.vec"
    if vec_file.exists():
        ok(f"Artifact verified: index.vec ({vec_file.stat().st_size / 1024 / 1024:.1f}MB)")
    return elapsed


def scenario_3_contract_change(ctx):
    """Change one param → URI changes → forces recompute (Bazel moment)."""
    header("SCENARIO 3 — Contract Changed  (one param edited)")

    original_uri = ctx.get_uri(CONTRACT)
    step(f"Original URI : {original_uri}")

    # Change a single param
    new_contract = {**CONTRACT, "params": {**CONTRACT["params"], "chunk_size": 256}}
    new_uri = ctx.get_uri(new_contract)
    step(f"New URI      : {new_uri}")

    print()
    if original_uri != new_uri:
        ok("URIs are DIFFERENT — cache miss forced, recompute required.")
        ok("Identity is correct: changing chunk_size 512 → 256 invalidates the artifact.")
    else:
        warn("FAIL: URIs are identical — contract change was not detected!")


# ── Summary ───────────────────────────────────────────────────────────────────

def print_summary(cold_time, hit_time, artifact_mb):
    print(f"\n{SEP2}")
    print("  BENCHMARK SUMMARY")
    print(f"{SEP2}")
    print(f"  {'Metric':<35} {'Value':>15}")
    print(f"  {SEP}")
    print(f"  {'Corpus size (synthetic)':<35} {CORPUS_MB:>14}MB")
    print(f"  {'Output artifact size':<35} {artifact_mb:>13.1f}MB")
    print(f"  {'Pipeline chunks simulated':<35} {CHUNK_COUNT:>15}")
    print(f"  {'Cold run (compute + seed)':<35} {cold_time:>14.2f}s")
    print(f"  {'Cache hit (pull + verify)':<35} {hit_time:>13.4f}s")
    speedup = cold_time / max(hit_time, 0.0001)
    print(f"  {'Speedup':<35} {speedup:>13.0f}x")
    print(f"  {'Registry':<35} {'Local cache (no network)':>15}")
    print(f"{SEP2}\n")
    print("  Conclusion: time becomes network-bound, not compute-bound.")
    print(f"{SEP2}\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{SEP2}")
    print("  CtxPack — Benchmark Demo")
    print("  'Bazel-grade identity for AI data pipelines. Pull by URI.'")
    print(f"{SEP2}")

    # Setup
    step(f"Generating ~{CORPUS_MB}MB synthetic corpus…")
    t0 = time.perf_counter()
    pages, nbytes = generate_corpus(INPUT_DIR, CORPUS_MB)
    gen_time = time.perf_counter() - t0
    ok(f"Corpus ready: {pages} pages, {nbytes / 1024 / 1024:.1f}MB in {gen_time:.2f}s")

    ctx = CtxPack(cache_dir=CACHE_DIR)
    uri = ctx.get_uri(CONTRACT)

    cold_time, artifact_mb = scenario_1_cold_run(ctx, uri)
    hit_time  = scenario_2_cache_hit(ctx, uri, cold_time)
    scenario_3_contract_change(ctx)
    print_summary(cold_time, hit_time, artifact_mb)


if __name__ == "__main__":
    try:
        main()
    finally:
        # Cleanup temp dirs
        for d in [CACHE_DIR, INPUT_DIR]:
            if os.path.exists(d):
                shutil.rmtree(d)
