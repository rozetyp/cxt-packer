import os
import shutil
import time
from ctxpack import CtxPack

# --- CONFIGURATION (The 'env' part) ---
os.environ["CTXP_REGISTRY"] = "ghcr.io/antonzaytsev/ctxpack-demo"
os.environ["CTXP_TOKEN"] = "ghp_fake_token_for_demo_12345"

def run_heavy_oci_demo():
    ctx = CtxPack(cache_dir="ctxpack-demo/cache")
    
    # 1. Create Heavy Input Data (Simulated)
    input_dir = "heavy_inputs"
    if os.path.exists(input_dir):
        shutil.rmtree(input_dir)
    os.makedirs(input_dir)
    
    # Create 5 dummy "large" files to hash
    for i in range(5):
        with open(os.path.join(input_dir, f"doc_{i}.pdf"), "w") as f:
            f.write(f"Content for PDF document {i} - Very important data.")

    # 2. Define the 'Bazel-Grade' Contract
    # Note: We use 'path' which CtxPack will now digest into a SHA256 hash
    contract = {
        "inputs": [{"name": "sec_filings", "path": input_dir}],
        "transforms": [
            {"tool": "vision-pro", "version": "1.2", "params": {"dpi": 300}},
            {"tool": "openai-embed", "model": "text-embedding-3-large"}
        ],
        "params": {"chunk_size": 1024}
    }
    
    print("--- STARTING HEAVY OCI & PROVENANCE DEMO ---")
    print("Step 1: Computing Contract Identity (Hashing inputs)...")
    uri = ctx.get_uri(contract)
    print(f"Computed URI: {uri}\n")

    # 3. SEED (Simulate Agent A)
    # This simulates the first agent finishing the slow work
    output_dir = "temp_outputs_AgentA"
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir)
    with open(os.path.join(output_dir, "vector_index.bin"), "wb") as f:
        f.write(os.urandom(1024)) # Dummy binary index
    with open(os.path.join(output_dir, "metadata.json"), "w") as f:
        f.write('{"status": "complete", "pages": 500}')

    print(f"Step 2: Sealing artifacts into local cache...")
    seeded_uri = ctx.seed(output_dir, contract)
    print(f"Seeded: {seeded_uri}\n")
    
    # 4. INSPECT (Provenance UI)
    print("Step 3: Verifying Provenance (The 'Who, What, When')...")
    ctx.inspect(seeded_uri)
    
    # 5. PUSH (OCI Remote)
    print("Step 4: Pushing Portably Identity to Registry...")
    ctx.push(seeded_uri)

    # Cleanup
    shutil.rmtree(output_dir)
    shutil.rmtree(input_dir)

    print("\n--- HEAVY DEMO COMPLETE ---")
    print("The URI is now a cryptographic guarantee of the work performed.")

if __name__ == "__main__":
    run_heavy_oci_demo()
