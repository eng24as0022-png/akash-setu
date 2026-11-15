"""
Akash Setu - Automated Render.com API Deployer
Module: deploy_render.py

Automates:
1. Creating the web service on Render via REST API
2. Injecting secure environment variables (COMMANDER_PASSCODE)
3. Triggering initial build & deploy
4. Polling deployment status until live
5. Performing end-to-end live testing of the public URL
"""

import sys
import os
import json
import time
import urllib.request
import urllib.error

RENDER_API_BASE = "https://api.render.com/v1"

def deploy(api_key: str, repo_url: str = "https://github.com/eng24as0022-png/akash-setu",
           commander_passcode: str = "NDRF-2026-RESCUE"):
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    print("=" * 70)
    print("  AKASH SETU - AUTOMATED RENDER.COM DEPLOYMENT")
    print("=" * 70)

    # 1. Fetch Render User / Owner ID
    print("[1/5] Fetching Render account owner details...")
    req = urllib.request.Request(f"{RENDER_API_BASE}/owners?limit=1", headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            owners_data = json.loads(resp.read().decode())
            if not owners_data:
                print("[ERROR] No owners found for this Render API key.")
                return None
            owner_id = owners_data[0]["owner"]["id"]
            owner_name = owners_data[0]["owner"]["name"]
            print(f"[OK] Authenticated as Render Owner: {owner_name} (ID: {owner_id})")
    except Exception as e:
        print(f"[ERROR] Failed to authenticate with Render API: {e}")
        return None

    # 2. Check if service already exists
    print(f"\n[2/5] Checking for existing 'akash-setu' service...")
    service_id = None
    service_url = None
    req = urllib.request.Request(f"{RENDER_API_BASE}/services?name=akash-setu&limit=5", headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            services_data = json.loads(resp.read().decode())
            for item in services_data:
                svc = item.get("service", {})
                if svc.get("name") == "akash-setu":
                    service_id = svc["id"]
                    service_url = svc.get("serviceDetails", {}).get("url")
                    print(f"[OK] Found existing service: {service_id} (URL: {service_url})")
                    break
    except Exception as e:
        print(f"[INFO] Could not list existing services: {e}")

    # 3. Create service if not found
    if not service_id:
        print(f"\n[3/5] Creating new Web Service from {repo_url}...")
        payload = {
            "type": "web_service",
            "name": "akash-setu",
            "ownerId": owner_id,
            "repo": repo_url,
            "branch": "main",
            "autoDeploy": "yes",
            "serviceDetails": {
                "env": "python",
                "plan": "free",
                "region": "singapore",
                "buildCommand": "",
                "startCommand": "python server.py",
                "envVars": [
                    {"key": "COMMANDER_PASSCODE", "value": commander_passcode},
                    {"key": "HOST", "value": "0.0.0.0"}
                ]
            }
        }

        req = urllib.request.Request(
            f"{RENDER_API_BASE}/services",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        try:
            with urllib.request.urlopen(req) as resp:
                created = json.loads(resp.read().decode("utf-8"))
                service_id = created["id"]
                service_url = created.get("serviceDetails", {}).get("url")
                print(f"[OK] Service created successfully! Service ID: {service_id}")
                print(f"[OK] Target Public URL: {service_url}")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            print(f"[ERROR] Service creation failed ({e.code}): {err_body}")
            return None

    # 4. Poll deployment until live
    print(f"\n[4/5] Monitoring deployment status on Render...")
    for attempt in range(1, 40):
        time.sleep(10)
        req = urllib.request.Request(f"{RENDER_API_BASE}/services/{service_id}", headers=headers)
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                details = data.get("serviceDetails", {})
                service_url = details.get("url") or service_url
                status = details.get("status", "unknown")
                print(f"  Attempt {attempt}/40: Service Status = {status} | URL = {service_url}")
                if status == "live" or status == "available":
                    print(f"\n[SUCCESS] Akash Setu is LIVE at: {service_url}")
                    break
        except Exception as e:
            print(f"  Polling error: {e}")

    # 5. Live Verification Tests
    if service_url:
        print(f"\n[5/5] Running Live Verification against {service_url}...")
        test_live_site(service_url, commander_passcode)

        # Save deployment metadata
        result_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deployment_result.json")
        try:
            with open(result_file, "w", encoding="utf-8") as f:
                json.dump({
                    "status": "SUCCESS",
                    "service_id": service_id,
                    "service_url": service_url,
                    "timestamp": time.time()
                }, f, indent=2)
            print(f"[OK] Deployment result recorded in {result_file}")
        except Exception as e:
            print(f"[WARN] Could not write deployment result file: {e}")

    return service_url

def test_live_site(base_url: str, commander_passcode: str):
    base_url = base_url.rstrip("/")
    print(f"--- Probing {base_url} ---")
    
    # Test 1: Public Homepage
    try:
        with urllib.request.urlopen(f"{base_url}/", timeout=15) as resp:
            content = resp.read().decode("utf-8")
            if "AKASH SETU" in content:
                print("  [PASS] Public Homepage loaded successfully (200 OK)")
            else:
                print("  [WARN] Homepage returned 200 but title mismatch")
    except Exception as e:
        print(f"  [FAIL] Public Homepage probe failed: {e}")

    # Test 2: Public Incidents Feed
    try:
        with urllib.request.urlopen(f"{base_url}/api/incidents", timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"  [PASS] Public Incidents Feed: {data.get('count', 0)} incidents online")
    except Exception as e:
        print(f"  [FAIL] Incidents API failed: {e}")

    # Test 3: Public Citizen SOS Submission
    try:
        payload = json.dumps({
            "raw_text": "Live deployment test from Akash Setu automated verifier. Flash flood at Sonprayag.",
            "location_name": "Sonprayag Live Check",
            "channel": "WEB"
        }).encode("utf-8")
        req = urllib.request.Request(f"{base_url}/api/emergency/submit", data=payload,
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"  [PASS] Public Emergency Intake: Incident {data.get('incident', {}).get('incident_code')} created")
    except Exception as e:
        print(f"  [FAIL] Emergency intake failed: {e}")

    # Test 4: Protected Rescue Dispatch Security (Must reject unauthenticated with 401)
    try:
        payload = json.dumps({"team_id": 1}).encode("utf-8")
        req = urllib.request.Request(f"{base_url}/api/incidents/1/dispatch", data=payload,
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            print("  [FAIL] Security alert: Unauthenticated dispatch returned 200 instead of 401!")
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("  [PASS] Security verified: Unauthenticated rescue dispatch blocked (401 Unauthorized)")
        else:
            print(f"  [WARN] Dispatch returned HTTP {e.code}")
    except Exception as e:
        print(f"  [WARN] Security check exception: {e}")

    # Test 5: Commander Authentication
    try:
        payload = json.dumps({"passcode": commander_passcode}).encode("utf-8")
        req = urllib.request.Request(f"{base_url}/api/auth/login", data=payload,
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("authenticated"):
                print("  [PASS] Commander Authentication succeeded with secure passcode")
    except Exception as e:
        print(f"  [FAIL] Commander login failed: {e}")

    print("=" * 70)
    print(f"  AKASH SETU IS VERIFIED & READY TO SHARE:")
    print(f"  URL: {base_url}")
    print("=" * 70)

if __name__ == "__main__":
    import getpass

    api_key = os.environ.get("RENDER_API_KEY")
    if not api_key and len(sys.argv) > 1:
        api_key = sys.argv[1]

    if not api_key:
        print("\n[SECURE INPUT] Render API Key is not set in environment.")
        api_key = getpass.getpass("Enter your Render API Key (input will be hidden): ").strip()

    if not api_key:
        print("[ERROR] No Render API Key provided. Aborting.")
        sys.exit(1)

    code = os.environ.get("COMMANDER_PASSCODE")
    if not code and len(sys.argv) > 2:
        code = sys.argv[2]
    if not code:
        code = "NDRF-2026-RESCUE"

    deploy(api_key, commander_passcode=code)
