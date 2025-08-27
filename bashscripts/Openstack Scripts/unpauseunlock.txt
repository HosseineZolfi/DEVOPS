#!/usr/bin/env python3
import subprocess
import time
import sys

def run_cmd(cmd):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Error running command: {' '.join(cmd)}")
        print(e.stderr)
        return ""

def confirm():
    ans = input("Do you want to continue unlocking and unpausing paused instances? (yes/no): ")
    if ans.lower() != "yes":
        print("Operation aborted.")
        sys.exit(0)

def get_paused_instances():
    """Parse the full server list and return IDs of PAUSED instances."""
    output = run_cmd(["openstack", "server", "list", "--long"])
    paused = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("+") or line.startswith("| ID") or line.startswith("|ID"):
            continue
        cols = [c.strip() for c in line.split("|")[1:-1]]
        if len(cols) >= 3 and cols[2].upper() == "PAUSED":
            paused.append(cols[0])  # ID
    return paused

def wait_for_unlock(instance_id, name, max_attempts=15):
    for attempt in range(max_attempts):
        locked = run_cmd(["openstack", "server", "show", instance_id, "-f", "value", "-c", "locked"])
        if locked == "False":
            print(f"{name} is unlocked.")
            return True
        time.sleep(2)
    print(f"⚠️ WARNING: {name} is still LOCKED after {max_attempts*2} seconds.")
    return False

def wait_for_active(instance_id, name, max_attempts=30):
    for attempt in range(max_attempts):
        status = run_cmd(["openstack", "server", "show", instance_id, "-f", "value", "-c", "status"])
        if status == "ACTIVE":
            print(f"✅ {name} is ACTIVE now.")
            return True
        else:
            print(f"⏳ {name} status = {status} (waiting for ACTIVE)...")
        time.sleep(2)
    print(f"⚠️ WARNING: {name} did not reach ACTIVE after {max_attempts*2} seconds (last status: {status}).")
    return False

def process_instance(instance_id):
    name = run_cmd(["openstack", "server", "show", instance_id, "-f", "value", "-c", "name"])
    print(f"\n--- Processing instance: {name} ({instance_id}) ---")

    print(f"Unlocking {name}...")
    run_cmd(["openstack", "server", "unlock", instance_id])
    wait_for_unlock(instance_id, name)

    time.sleep(5)

    print(f"Unpausing {name}...")
    run_cmd(["openstack", "server", "unpause", instance_id])
    wait_for_active(instance_id, name)

    print(f"Done with {name}.")
    return instance_id

def final_report():
    print("\n===== FINAL REPORT =====")
    output = run_cmd(["openstack", "server", "list", "--long"])
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("+") or line.startswith("| ID") or line.startswith("|ID"):
            continue
        cols = [c.strip() for c in line.split("|")[1:-1]]
        if len(cols) >= 3:
            instance_id, name, status = cols[0], cols[1], cols[2]
            locked = run_cmd(["openstack", "server", "show", instance_id, "-f", "value", "-c", "locked"])
            print(f"- {name} ({instance_id}): status={status}, locked={locked}")

def main():
    print("Fetching the full list of instances...")
    print(run_cmd(["openstack", "server", "list", "--long"]))

    confirm()

    processed = set()

    while True:
        paused = get_paused_instances()
        paused = [p for p in paused if p not in processed]

        if not paused:
            break

        print(f"\n>>> Found {len(paused)} paused instances to process: {paused}")
        for instance_id in paused:
            processed.add(process_instance(instance_id))
            time.sleep(3)

        print("\n>>> Re-checking paused instances...")

    final_report()
    print("\n🎉 All pause-locked instances have been processed.")

if __name__ == "__main__":
    main()
