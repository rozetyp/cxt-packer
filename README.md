# 📦 CtxPack: Reproducible AI Artifacts

**"Bazel-grade identity for AI data pipelines. Pull by URI."**

CtxPack is a content-addressed identity layer for AI agent artifacts. It ensures that expensive transforms (OCR, Chunking, Embedding, Parsing, Transcribing) are performed **once per unique contract** and then reused across your entire team (swarm) with cryptographic confidence.

---

## ⚡ 30-Second Demo: "RAG Index in a URI"
*   **Ingest:** Run your slow pipeline once → `ctxpack seed` → `ctxpack push`.
*   **Share:** Give the `ctx://sha256:...` URI to your team.
*   **Query:** On any other machine, `ctxpack pull` skips the ingest and is ready to query as soon as the pack is pulled.
    *   *Time becomes network-bound, not compute-bound.*

---

## 🚀 Use Cases
*   **Flagship: RAG Pipelines.** Stop re-embedding the same 10GB PDF corpus every time you debug a prompt.
*   **Also works for:** 
    *   **AI Transcription:** Cache Whisper JSON transcripts; skip re-transcribing the 2GB source audio.
    *   **Code Audits:** Only re-scan the files that actually changed in a PR.
    *   **Data ETL:** Share AI-normalized datasets across your team instantly.

---

## ❓ Why not just S3?
*   **Identity vs. Bytes:** S3 stores bytes; CtxPack stores **reproducible identity**. 
*   **Automatic Cache Correctness:** CtxPack prevents "stale cache" bugs by deriving the URI from the recipe (inputs + code + params), not just a file name.
*   **Built-in Provenance:** Every pack is cryptographically linked to the specific model and code that produced it.

---

## 🧠 Simple Terms: How it Works
1.  **The Recipe (Contract):** You define exactly what goes into your work (Source PDFs + Model + **Pipeline Code Hash**).
2.  **The Fingerprint (URI):** CtxPack generates a unique ID based on that recipe. If you change a single pixel in a PDF or a line in your code, the fingerprint changes.
3.  **The Pantry (Registry):** Before starting "cooking," an agent checks the pantry (GHCR/ACR/ECR).
4.  **The Resolution:** If the recipe is finished, the agent downloads it and skips the recomputation.

---

## 🛠 Usage (Internal Preview)

### 1. Define a Strict Contract (`contract.json`)
```json
{
  "inputs": [{"name": "raw_docs", "path": "./raw_pdfs"}],
  "transforms": [{
    "tool": "vision-pro",
    "tool_version": "1.2",
    "code_hash": "sha256:abc123...",
    "params": {"dpi": 300}
  }],
  "outputs": [{"path": "./processed_data"}]
}
```
*Note: CtxPack recursively hashes input paths to compute digests; paths are not part of identity. Identity is derived from the contract hash, not the output bytes.*

### 2. Seed and Push (Agent A)
```bash
# Register the output folder locally
ctxpack seed ./processed_data --contract contract.json
# Seeded: ctx://sha256:8543...

# Upload to your "Pantry"
ctxpack push ctx://sha256:8543...
```

### 3. Pull and Inspect (Agent B)
```bash
# On another machine
ctxpack pull ctx://sha256:8543...

# Verify exactly what produced the data
ctxpack inspect ctx://sha256:8543...
```

---

## 📦 What's in a Pack?
A CtxPack is a `.tar.gz` bundle containing:
*   `manifest.json`: The provenance, contract, and identity metadata.
*   **Your Artifacts:** The actual produced data (e.g., vector indexes, JSON extracts, markdown).

---

## 🛡️ Hardened Guarantees (Verified)
CtxPack is built for production trust. Verified against **GHCR** with real credentials:
*   **Manifest Verification:** The manifest bytes are hashed and compared against `Docker-Content-Digest` before any layers are downloaded.
*   **Streaming Integrity:** Every layer byte is verified via SHA256 *while downloading*.
*   **Atomic Deployment:** Artifacts are moved to the cache only after full validation.
*   **Path Traversal Protection:** Internal client blocks unsafe tar members (e.g., `../`).
*   **OCI-Compatible:** Tested on GHCR; should work with standard OCI registries (ECR/ACR next).

---

## 🌐 OCI Integration
- **Minimal Client:** Uses a custom Python OCI client (requests-only) to ensure portability without external credential helpers.
- **v0 Swarm:** Refers to **shared registry resolution**. True P2P transport is a non-goal for v0.

---

## 🚧 Non-Goals & Limitations
*   **NOT** a workflow engine (use Airflow/Prefect).
*   **NOT** a universal data lake.
*   **Single-Layer Only:** v0 stores the entire pack as a single OCI layer.
*   **Synchronous Hashing:** 10GB+ datasets may bottleneck during the initial "Deep Hash."

---

## 📦 Installation & Testing
1. **Setup Env:** `python3 -m venv .venv && source .venv/bin/activate && pip install requests`
2. **Install Local:** `pip install -e .`
3. **Verify Correctness:** `python3 ctxpack-demo/demo_bazel.py`
