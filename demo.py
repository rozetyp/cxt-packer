
import time
import os
import shutil
from ctxpack import CtxPack

def simulate_slow_work(name):
    print(f"[{name}] Starting slow OCR and Embedding process...")
    # Simulate processing 1000 pages
    for i in range(5):
        print(f"[{name}]   Processing chunk {i+1}/5...")
        time.sleep(1) 
    
    # Create dummy artifact folder
    output_dir = f"temp_outputs_{name}"
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir)
    with open(os.path.join(output_dir, "index.vec"), "w") as f:
        f.write("DUMMY_VECTOR_DATA_12345")
    with open(os.path.join(output_dir, "extracted.json"), "w") as f:
        f.write('{"text": "Extracted content from 2025 Report"}')
    
    return output_dir

def run_demo():
    ctx = CtxPack(cache_dir="ctxpack-demo/cache")
    
    # The Shared Contract
    contract = {
        "dataset": "SEC_FILING_2025",
        "model": "gpt-4o-vision",
        "embedding": "text-embedding-3",
        "params": {"chunk_size": 512, "strategy": "semantic"}
    }
    
    uri = ctx.get_uri(contract)
    print(f"--- DEMO START ---")
    print(f"Target URI: {uri}\n")

    # --- AGENT 1: THE FIRST WORKER ---
    print(f"SCENARIO 1: Agent 1 starts with a fresh cache.")
    cached_path = ctx.pull(uri)
    
    if not cached_path:
        print(f"[Agent 1] Cache Miss! Must perform re-computation.")
        start_time = time.time()
        results_dir = simulate_slow_work("Agent1")
        ctx.seed(results_dir, contract)
        end_time = time.time()
        print(f"[Agent 1] COMPLETED in {end_time - start_time:.2f} seconds.\n")
        shutil.rmtree(results_dir) # cleanup temp
    
    print("-" * 30)

    # --- AGENT 2: THE RESEARCHER ---
    print(f"SCENARIO 2: Agent 2 joins the swarm.")
    print(f"[Agent 2] Checking for URI: {uri}")
    
    start_time = time.time()
    cached_path = ctx.pull(uri)
    
    if cached_path:
        print(f"[Agent 2] CACHE HIT! Skipping all work.")
        print(f"[Agent 2] Loading pre-computed index from: {cached_path}")
        # Verify the data
        with open(cached_path / "extracted.json", "r") as f:
            print(f"[Agent 2] Data Verified: {f.read()}")
        
        end_time = time.time()
        print(f"[Agent 2] READY in {end_time - start_time:.4f} seconds.")
    else:
        print("[Agent 2] Cache Miss (This shouldn't happen!)")

if __name__ == "__main__":
    run_demo()
