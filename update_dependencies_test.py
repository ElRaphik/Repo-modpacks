import json
import os
import requests
from packaging import version
from datetime import date

THUNDERSTORE_API = "https://thunderstore.io/c/repo/api/v1/package/"
MANIFEST_PATH = "manifest.json"
SNAPSHOT_PATH = ".dependencies_snapshot.json"

def load_manifest(path):
    with open(path, 'r') as f:
        return json.load(f)

def load_snapshot(path):
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return []

def load_thunderstore_packages():
    print("Fetching Thunderstore packages...")
    resp = requests.get(THUNDERSTORE_API)
    resp.raise_for_status()
    packages = resp.json()

    lookup = {}
    for package in packages:
        full_name = package.get("full_name")
        versions = package.get("versions", [])
        if full_name and versions:
            lookup[full_name] = versions[0]["version_number"]

    print(f"Loaded {len(lookup)} packages from Thunderstore.")
    return lookup

def bump_patch(ver_str):
    if ver_str == "": return "1.0.0"
    parsed_version = version.parse(ver_str)
    if not isinstance(parsed_version, version.Version):
        raise ValueError(f"Invalid version format: {ver_str}")
    return f"{parsed_version.major}.{parsed_version.minor}.{parsed_version.micro + 1}"

def main():
    manifest = load_manifest(MANIFEST_PATH)
    dependencies = manifest.get("dependencies", [])

    updated_mods = []
    added_mods = []
    removed_mods = []

    thunderstore_lookup = load_thunderstore_packages()

    new_dependencies = []

    for dep in dependencies:
        try:
            namespace, name, current_version = dep.split("-")
            full_mod_name = f"{namespace}-{name}"
        except ValueError:
            print(f"Skipping malformed dependency: {dep}")
            new_dependencies.append(dep)
            continue

        latest = thunderstore_lookup.get(full_mod_name)

        if latest is None:
            print(f"Dependency not found: {dep} (would create issue)")
            new_dependencies.append(dep)
            continue

        if version.parse(latest) > version.parse(current_version):
            print(f"Would update {dep} to {latest}")
            new_dep = f"{namespace}-{name}-{latest}"
            new_dependencies.append(new_dep)
            updated_mods.append(f"{namespace}-{name} ({current_version} → {latest})")
        else:
            new_dependencies.append(dep)

    snapshot_dependencies = load_snapshot(SNAPSHOT_PATH)

    if new_dependencies != snapshot_dependencies:
        print("Dependencies list changed (mod added or removed).")

        snapshot_set = set(snapshot_dependencies)
        current_set = set(new_dependencies)

        added = current_set - snapshot_set
        removed = snapshot_set - current_set

        for mod in added:
            added_mods.append(mod)

        for mod in removed:
            removed_mods.append(mod)

    if updated_mods or added_mods or removed_mods:
        current_version = manifest.get("version_number", "")
        new_version = bump_patch(current_version)
        print(f"\n🆙 Would bump version from v{current_version} to v{new_version}")
        print("\n=== Summary ===")
        if updated_mods:
            print("Updated mods:")
            for mod in updated_mods:
                print(f" - {mod}")
        if added_mods:
            print("Added mods:")
            for mod in added_mods:
                print(f" - {mod}")
        if removed_mods:
            print("Removed mods:")
            for mod in removed_mods:
                print(f" - {mod}")
    else:
        print("\n✅ No changes detected. Nothing would be updated.")

if __name__ == "__main__":
    main()
