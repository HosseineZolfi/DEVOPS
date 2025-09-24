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
    ans = input("Do you want to continue pausing and locking ACTIVE instances? (yes/no): ")
    if ans.lower() != "yes":
        print("Operation aborted.")
        sys.exit(0)

def get_active_instances():
    """Parse the full server list and return IDs of ACTIVE instances."""
    output = run_cmd(["openstack", "server", "list", "--long"])
    active = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("+") or line.startswith("| ID") or line.startswith("|ID"):
            continue
        cols = [c.strip() for c in line.split("|")[1:-1]]
        if len(cols) >= 3 and cols[2].upper() == "ACTIVE":
            active.append(cols[0])  # ID
    return active

def wait_for_pause(instance_id, name, max_attempts=30):
    for attempt in range(max_attempts):
        status = run_cmd(["openstack", "server", "show", instance_id, "-f", "value", "-c", "status"])
        if status == "PAUSED":
            print(f"✅ {name} is PAUSED now.")
            return True
        else:
            print(f"⏳ {name} status = {status} (waiting for PAUSED)...")
        time.sleep(2)
    print(f"⚠️ WARNING: {name} did not reach PAUSED after {max_attempts*2} seconds (last status: {status}).")
    return False

def wait_for_lock(instance_id, name, max_attempts=15):
    for attempt in range(max_attempts):
        locked = run_cmd(["openstack", "server", "show", instance_id, "-f", "value", "-c", "locked"])
        if locked == "True":
            print(f"{name} is LOCKED.")
            return True
        time.sleep(2)
    print(f"⚠️ WARNING: {name} is still UNLOCKED after {max_attempts*2} seconds.")
    return False

def process_instance(instance_id):
    name = run_cmd(["openstack", "server", "show", instance_id, "-f", "value", "-c", "name"])
    print(f"\n--- Processing instance: {name} ({instance_id}) ---")

    print(f"Pausing {name}...")
    run_cmd(["openstack", "server", "pause", instance_id])
    wait_for_pause(instance_id, name)

    time.sleep(5)

    print(f"Locking {name}...")
    run_cmd(["openstack", "server", "lock", instance_id])
    wait_for_lock(instance_id, name)

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
        active = get_active_instances()
        active = [a for a in active if a not in processed]

        if not active:
            break

        print(f"\n>>> Found {len(active)} active instances to process: {active}")
        for instance_id in active:
            processed.add(process_instance(instance_id))
            time.sleep(3)

        print("\n>>> Re-checking active instances...")

    final_report()
    print("\n🎉 All active instances have been paused and locked.")

if __name__ == "__main__":
    main()
