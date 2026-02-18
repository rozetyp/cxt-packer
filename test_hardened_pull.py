import os
import shutil
from ctxpack import CtxPack

# --- REAL CONFIGURATION ---
os.environ["CTXP_REGISTRY_URL"] = "ghcr.io"
os.environ["CTXP_REPO"] = "rozetyp/ctxpack-demo"
os.environ["CTXP_TOKEN"] = "YOUR_GITHUB_PAT"
os.environ["CTXP_USER"] = "YOUR_GITHUB_USERNAME"

def test_hardened_pull():
    ctx = CtxPack(cache_dir="ctxpack-demo/cache_test")
    
    # 1. We'll use the URI from our previous successful push
    # ctx://sha256:854346c6e66e556c04faf02c2a78725f1ea8bb4989c40538a092e06d9f69fec8
    uri = "ctx://sha256:854346c6e66e556c04faf02c2a78725f1ea8bb4989c40538a092e06d9f69fec8"
    
    # Clear local cache test folder to force a remote pull
    if os.path.exists("ctxpack-demo/cache_test"):
        shutil.rmtree("ctxpack-demo/cache_test")
    
    print(f"--- TESTING HARDENED PULL FOR: {uri} ---")
    
    try:
        path = ctx.pull(uri)
        print(f"Pull completed. Path: {path}")
        
        # Verify the file contents
        index_file = path / "index.bin"
        if index_file.exists():
            content = index_file.read_text()
            print(f"File content verified: {content}")
            if content == "REAL_DATA_INDEX_12345":
                print("\n✅ GOLD VERIFIED: Hardened pull, integrity check, and extraction all passed!")
            else:
                print("\n❌ VERIFICATION FAILED: Content mismatch.")
        else:
            print("\n❌ VERIFICATION FAILED: index.bin not found.")
            
    except Exception as e:
        print(f"\n❌ TEST FAILED with error: {e}")

if __name__ == "__main__":
    test_hardened_pull()
