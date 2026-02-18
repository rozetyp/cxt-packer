import os
import shutil
from ctxpack import CtxPack

# --- REAL CONFIGURATION ---
os.environ["CTXP_REGISTRY_URL"] = "ghcr.io"
os.environ["CTXP_REPO"] = "rozetyp/ctxpack-demo"
os.environ["CTXP_TOKEN"] = "YOUR_GITHUB_PAT"
os.environ["CTXP_USER"] = "YOUR_GITHUB_USERNAME"

def test_push():
    ctx = CtxPack(cache_dir="ctxpack-demo/cache")
    
    # 1. Create real dummy data
    input_dir = "test_inputs"
    if os.path.exists(input_dir):
        shutil.rmtree(input_dir)
    os.makedirs(input_dir)
    with open(os.path.join(input_dir, "test.pdf"), "w") as f:
        f.write("Real-world PDF content for testing CtxPack OCI push.")

    # 2. Define Contract
    contract = {
        "inputs": [{"path": input_dir}],
        "transforms": [{"tool": "tester", "version": "1.0"}]
    }
    
    # 3. Seed
    output_dir = "test_outputs"
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir)
    with open(os.path.join(output_dir, "index.bin"), "w") as f:
        f.write("REAL_DATA_INDEX_12345")

    print("--- ATTEMPTING REAL OCI PUSH ---")
    uri = ctx.seed(output_dir, contract)
    print(f"Seeded URI: {uri}")
    
    # 4. Push
    success = ctx.push(uri)
    
    if success:
        print("\n✅ GOLD VERIFIED: Real artifact pushed to GHCR!")
    else:
        print("\n❌ VERIFICATION FAILED: Check the error logs.")

    # Cleanup
    shutil.rmtree(input_dir)
    shutil.rmtree(output_dir)

if __name__ == "__main__":
    test_push()
