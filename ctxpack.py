import json
import hashlib
import os
import shutil
import tarfile
import base64
import requests
import tempfile
from pathlib import Path

class CtxPackError(Exception): pass
class ManifestNotFoundError(CtxPackError): pass
class DigestMismatchError(CtxPackError): pass
class SecurityError(CtxPackError): pass

class CtxPack:
    def __init__(self, cache_dir=".ctx_cache"):
        self.cache_dir = Path(cache_dir).absolute()
        self.cache_dir.mkdir(exist_ok=True)
        self.registry_url = os.getenv("CTXP_REGISTRY_URL", "ghcr.io")
        self.repo = os.getenv("CTXP_REPO")
        self.token = os.getenv("CTXP_TOKEN")
        self.user = os.getenv("CTXP_USER", "rozetyp")

    def _get_auth_headers(self, scope="pull"):
        auth_str = base64.b64encode(f"{self.user}:{self.token}".encode()).decode()
        url = f"https://{self.registry_url}/token?service={self.registry_url}&scope=repository:{self.repo}:{scope}"
        r = requests.get(url, headers={"Authorization": f"Basic {auth_str}"})
        if r.status_code != 200:
            raise CtxPackError(f"Auth Failed: {r.status_code} {r.text}")
        token = r.json().get("token")
        return {"Authorization": f"Bearer {token}"}

    def _hash_dir(self, path):
        sha256 = hashlib.sha256()
        for file in sorted(Path(path).rglob('*')):
            if file.is_file():
                sha256.update(str(file.relative_to(path)).encode())
                with open(file, 'rb') as f:
                    while chunk := f.read(8192): sha256.update(chunk)
        return sha256.hexdigest()

    def get_uri(self, contract):
        c = contract.copy()
        if "inputs" in c:
            new_inputs = []
            for inp in c["inputs"]:
                item = inp.copy()
                if "path" in item:
                    item["digest"] = self._hash_dir(item["path"])
                    del item["path"]
                new_inputs.append(item)
            c["inputs"] = new_inputs
        
        # Identity depends on Transforms
        if "outputs" in c: del c["outputs"]
        
        contract_hash = hashlib.sha256(json.dumps(c, sort_keys=True).encode()).hexdigest()
        return f"ctx://sha256:{contract_hash}"

    def pull(self, uri):
        contract_hash = uri.split(":")[-1]
        short_id = contract_hash[:12]
        final_path = self.cache_dir / contract_hash
        
        if final_path.exists():
            return final_path

        print(f"--- HARDENED PULL: {uri} ---")
        headers = self._get_auth_headers("pull")
        headers["Accept"] = (
            "application/vnd.oci.image.index.v1+json, "
            "application/vnd.oci.image.manifest.v1+json, "
            "application/vnd.docker.distribution.manifest.list.v2+json, "
            "application/vnd.docker.distribution.manifest.v2+json"
        )

        extract_path = self.cache_dir / f"tmp_extract_{contract_hash}"
        if extract_path.exists(): shutil.rmtree(extract_path)
        extract_path.mkdir(parents=True)

        try:
            # 1. Resolve Manifest
            url = f"https://{self.registry_url}/v2/{self.repo}/manifests/{short_id}"
            print(f"Fetching manifest from {url}...")
            r = requests.get(url, headers=headers)
            if r.status_code != 200:
                raise ManifestNotFoundError(f"URI {uri} not found in registry (HTTP {r.status_code}): {r.text}")
            
            # Manifest Digest Verification
            manifest_bytes = r.content
            actual_digest = f"sha256:{hashlib.sha256(manifest_bytes).hexdigest()}"
            expected_digest = r.headers.get("Docker-Content-Digest")
            
            if expected_digest and actual_digest != expected_digest:
                raise DigestMismatchError(f"Manifest corruption! Expected {expected_digest}, got {actual_digest}")
            
            manifest = r.json()
            # Handle simple manifest selection if it's an index/list
            if manifest.get("mediaType") in ["application/vnd.oci.image.index.v1+json", "application/vnd.docker.distribution.manifest.list.v2+json"]:
                print("Resolving manifest from index...")
                digest = manifest["manifests"][0]["digest"]
                r = requests.get(f"https://{self.registry_url}/v2/{self.repo}/manifests/{digest}", headers=headers)
                manifest = r.json()

            # 2. Download Layers with Integrity Check
            for layer in manifest.get("layers", []):
                digest = layer["digest"]
                print(f"Downloading layer {digest[:12]}...")
                
                blob_url = f"https://{self.registry_url}/v2/{self.repo}/blobs/{digest}"
                with requests.get(blob_url, headers=headers, stream=True) as br:
                    br.raise_for_status()
                    sha = hashlib.sha256()
                    tar_tmp = self.cache_dir / f"tmp_{digest[:12].replace(':', '_')}.tar.gz"
                    with open(tar_tmp, "wb") as f:
                        for chunk in br.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                sha.update(chunk)
                    
                    if f"sha256:{sha.hexdigest()}" != digest:
                        raise DigestMismatchError(f"Layer corruption detected for {digest}")

                    # 3. Safe Extraction
                    with tarfile.open(tar_tmp, "r:gz") as tar:
                        for member in tar.getmembers():
                            if member.name.startswith("/") or ".." in member.name:
                                raise SecurityError(f"Unsafe tar member detected: {member.name}")
                        tar.extractall(path=extract_path)
                    os.remove(tar_tmp)

            # 4. Final Validation
            ctx_manifest_path = extract_path / "manifest.json"
            if not ctx_manifest_path.exists():
                raise CtxPackError("Downloaded pack missing internal manifest.json")
            
            with open(ctx_manifest_path) as f:
                inner = json.load(f)
                if inner["uri"] != uri:
                    raise CtxPackError(f"Identity mismatch! Expected {uri}, got {inner['uri']}")

            # Atomic move to final location
            print(f"Moving {extract_path} to {final_path}...")
            if final_path.exists(): shutil.rmtree(final_path)
            shutil.move(str(extract_path), str(final_path))
            print(f"✅ Successfully pulled and verified {short_id}")
            return final_path
        finally:
            if extract_path.exists():
                shutil.rmtree(extract_path)

    def seed(self, result_folder, contract):
        uri = self.get_uri(contract)
        full_hash = uri.split(":")[-1]
        target_path = self.cache_dir / full_hash
        if target_path.exists(): shutil.rmtree(target_path)
        shutil.copytree(result_folder, target_path)
        manifest = {
            "uri": uri,
            "contract": contract,
            "provenance": {"host": os.uname().nodename, "user": self.user, "timestamp": "2026-02-18T15:00:00Z"}
        }
        with open(target_path / "manifest.json", "w") as f:
            json.dump(manifest, f, indent=2)
        return uri

    def push(self, uri):
        full_hash = uri.split(":")[-1]
        short_id = full_hash[:12]
        path = self.cache_dir / full_hash
        tar_path = self.cache_dir / f"{full_hash}.tar.gz"
        
        with tarfile.open(tar_path, "w:gz") as tar:
            for item in os.listdir(path):
                tar.add(path / item, arcname=item)
        
        blob_data = tar_path.read_bytes()
        blob_digest = f"sha256:{hashlib.sha256(blob_data).hexdigest()}"
        blob_size = len(blob_data)

        print(f"--- HARDENED PUSH: {short_id} ---")
        token_headers = self._get_auth_headers("pull,push")
        headers = {**token_headers, "Accept": "application/vnd.oci.image.manifest.v1+json"}

        # 1. Start Blob Upload
        url = f"https://{self.registry_url}/v2/{self.repo}/blobs/uploads/"
        r = requests.post(url, headers=headers)
        upload_url = r.headers.get("Location")
        if not upload_url.startswith("http"):
            upload_url = f"https://{self.registry_url}{upload_url}" if upload_url.startswith("/") else f"https://{self.registry_url}/v2/{self.repo}/blobs/uploads/{upload_url}"

        # 2. Upload Blob
        separator = "?" if "?" not in upload_url else "&"
        requests.put(f"{upload_url}{separator}digest={blob_digest}", headers=headers, data=blob_data)

        # 3. Upload Config
        config_data = b"{}"
        config_digest = f"sha256:{hashlib.sha256(config_data).hexdigest()}"
        r = requests.post(f"https://{self.registry_url}/v2/{self.repo}/blobs/uploads/", headers=headers)
        cfg_url = r.headers.get("Location")
        if not cfg_url.startswith("http"): cfg_url = f"https://{self.registry_url}{cfg_url}"
        requests.put(f"{cfg_url}&digest={config_digest}", headers=headers, data=config_data)

        # 4. Upload Manifest
        manifest = {
            "schemaVersion": 2,
            "mediaType": "application/vnd.oci.image.manifest.v1+json",
            "config": {"mediaType": "application/vnd.oci.image.config.v1+json", "size": len(config_data), "digest": config_digest},
            "layers": [{"mediaType": "application/vnd.oci.image.layer.v1.tar+gzip", "size": blob_size, "digest": blob_digest}]
        }
        headers["Content-Type"] = "application/vnd.oci.image.manifest.v1+json"
        url = f"https://{self.registry_url}/v2/{self.repo}/manifests/{short_id}"
        r = requests.put(url, headers=headers, json=manifest)
        
        if r.status_code in [200, 201]:
            print(f"✅ Successfully pushed {short_id}")
            return True
        return False

    def inspect(self, uri):
        full_hash = uri.split(":")[-1]
        path = self.cache_dir / full_hash
        manifest_path = path / "manifest.json"
        if not manifest_path.exists():
            print(f"Error: {uri} not in local cache.")
            return
        with open(manifest_path) as f:
            print(json.dumps(json.load(f), indent=2))

def main():
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="CtxPack: Bazel for AI Artifacts")
    subparsers = parser.add_subparsers(dest="command")

    # Inspect
    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("uri", help="The ctx:// URI to inspect")

    # Seed
    seed_parser = subparsers.add_parser("seed")
    seed_parser.add_argument("folder", help="The output folder to seal")
    seed_parser.add_argument("--contract", required=True, help="Path to the contract.json file")

    # Pull
    pull_parser = subparsers.add_parser("pull")
    pull_parser.add_argument("uri", help="The ctx:// URI to pull")

    # Push
    push_parser = subparsers.add_parser("push")
    push_parser.add_argument("uri", help="The ctx:// URI to push")

    args = parser.parse_args()
    ctx = CtxPack()

    if args.command == "inspect":
        ctx.inspect(args.uri)
    elif args.command == "seed":
        with open(args.contract, "r") as f:
            contract = json.load(f)
        uri = ctx.seed(args.folder, contract)
        print(f"Seeded: {uri}")
    elif args.command == "pull":
        path = ctx.pull(args.uri)
        print(f"Artifact available at: {path}")
    elif args.command == "push":
        ctx.push(args.uri)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
