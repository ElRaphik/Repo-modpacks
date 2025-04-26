import json
import os
import requests
from packaging import version
import subprocess
from datetime import date

GITHUB_REPO = os.getenv("GITHUB_REPOSITORY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

THUNDERSTORE_API = "https://thunderstore.io/api/experimental/package/"
MANIFEST_PATH = "manifest.json"
SNAPSHOT_PATH = ".dependencies_snapshot.json"

def update_changelog(new_version, added_mods, updated_mods, removed_mods):
    today = date.today().isoformat()
    changelog_entry = f"## v{new_version} - {today}\n\n"

    if added_mods:
        changelog_entry += "### Added\n"
        for mod in added_mods:
            changelog_entry += f"- {mod}\n"
        changelog_entry += "\n"

    if updated_mods:
        changelog_entry += "### Updated\n"
        for mod in updated_mods:
            changelog_entry += f"- {mod}\n"
        changelog_entry += "\n"

    if removed_mods:
        changelog_entry += "### Removed\n"
        for mod in removed_mods:
            changelog_entry += f"- {mod}\n"
        changelog_entry += "\n"

    try:
        with open("CHANGELOG.md", "r") as f:
            existing_changelog = f.read()
    except FileNotFoundError:
        existing_changelog = ""

    with open("CHANGELOG.md", "w") as f:
        f.write(changelog_entry + existing_changelog)

    print("CHANGELOG.md updated.")

def load_snapshot(path):
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return []

def save_snapshot(path, dependencies):
    with open(path, 'w') as f:
        json.dump(dependencies, f, indent=4)

def bump_patch(ver_str):
    if ver_str == "":
        return "1.0.0"
    parsed_version = version.parse(ver_str)
    if not isinstance(parsed_version, version.Version):
        raise ValueError(f"Invalid version format: {ver_str}")
    return f"{parsed_version.major}.{parsed_version.minor}.{parsed_version.micro + 1}"

def load_manifest(path):
    with open(path, 'r') as f:
        return json.load(f)

def save_manifest(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=4)

def get_latest_version(namespace, name):
    url = f"{THUNDERSTORE_API}{namespace}/{name}/"
    resp = requests.get(url)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    package_data = resp.json()
    return package_data['latest']['version_number']

def create_github_issue(mod_full_name):
    if not GITHUB_TOKEN or not GITHUB_REPO:
        print("Missing GitHub token or repo. Cannot create issue.")
        return

    url = f"https://api.github.com/repos/{GITHUB_REPO}/issues"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    data = {
        "title": f"Dependency not found: {mod_full_name}",
        "body": f"The dependency `{mod_full_name}` could not be found on Thunderstore. Please investigate."
    }
    resp = requests.post(url, headers=headers, json=data)
    if resp.status_code != 201:
        print(f"Failed to create issue: {resp.text}")

def main():
    manifest = load_manifest(MANIFEST_PATH)
    dependencies = manifest.get("dependencies", [])

    updated = False
    new_dependencies = []

    updated_mods = []
    added_mods = []
    removed_mods = []

    for dep in dependencies:
        try:
            namespace, name, current_version = dep.split("-")
        except ValueError:
            print(f"Skipping malformed dependency: {dep}")
            new_dependencies.append(dep)
            continue

        latest = get_latest_version(namespace, name)

        if latest is None:
            print(f"Dependency not found: {dep}")
            create_github_issue(dep)
            new_dependencies.append(dep)
            continue

        if version.parse(latest) > version.parse(current_version):
            print(f"Updating {dep} to version {latest}")
            updated = True
            new_dep = f"{namespace}-{name}-{latest}"
            new_dependencies.append(new_dep)
            updated_mods.append(f"{namespace}-{name} ({current_version} → {latest})")
        else:
            new_dependencies.append(dep)

    snapshot_dependencies = load_snapshot(SNAPSHOT_PATH)

    if new_dependencies != snapshot_dependencies:
        print("Dependencies list changed (mod added or removed).")
        updated = True

        snapshot_set = set(snapshot_dependencies)
        current_set = set(new_dependencies)

        added = current_set - snapshot_set
        removed = snapshot_set - current_set

        for mod in added:
            added_mods.append(mod)

        for mod in removed:
            removed_mods.append(mod)

    if updated:
        manifest["dependencies"] = new_dependencies

        current_version = manifest.get("version_number", "")
        new_version = bump_patch(current_version)
        manifest["version_number"] = new_version

        save_manifest(MANIFEST_PATH, manifest)
        print(f"Manifest updated. Version bumped to v{new_version}")

        save_snapshot(SNAPSHOT_PATH, new_dependencies)

        with open("version.txt", "w") as f:
            f.write(new_version)

        try:
            subprocess.run(["python", "generate_thunderstore_toml.py"], check=True)
            print("thunderstore.toml regenerated successfully.")
        except subprocess.CalledProcessError:
            print("Failed to regenerate thunderstore.toml.")

        update_changelog(new_version, added_mods, updated_mods, removed_mods)
    else:
        print("All dependencies are up to date. No changes, skipping thunderstore.toml regeneration.")

if __name__ == "__main__":
    main()