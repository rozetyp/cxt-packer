import os
import shutil
from ctxpack import CtxPack

def run_bazel_demo():
    ctx = CtxPack(cache_dir="ctxpack-demo/cache")
    
    # Setup dummy input data
    input_dir = "demo_inputs"
    if os.path.exists(input_dir):
        shutil.rmtree(input_dir)
    os.makedirs(input_dir)
    with open(os.path.join(input_dir, "data.txt"), "w") as f:
        f.write("Hello World")

    # Define Contract
    contract = {
        "inputs": [{"path": input_dir}],
        "transforms": [{"name": "ocr", "version": "1.0"}]
    }

    # 1. First Run
    uri1 = ctx.get_uri(contract)
    print(f"Run 1 URI: {uri1}")

    # 2. Change Input Content (The "Bazel" Moment)
    with open(os.path.join(input_dir, "data.txt"), "w") as f:
        f.write("Hello CtxPack")
    
    uri2 = ctx.get_uri(contract)
    print(f"Run 2 URI (After change): {uri2}")

    if uri1 != uri2:
        print("\nSUCCESS: Correctness Verified! URI changed because inputs changed.")
    else:
        print("\nFAILURE: URI did not change. Loose contract detected.")

if __name__ == "__main__":
    run_bazel_demo()
