import json
import os
import requests
from packaging import version

GITHUB_REPO = os.getenv("GITHUB_REPOSITORY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

THUNDERSTORE_API = "https://thunderstore.io/api/v1/package/"
MANIFEST_PATH = "manifest.json"


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
    latest_version = package_data['latest']['version_number']
    return latest_version


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
        else:
            new_dependencies.append(dep)

    if updated:
        manifest["dependencies"] = new_dependencies
        save_manifest(MANIFEST_PATH, manifest)
        print("Manifest updated.")
    else:
        print("All dependencies are up to date.")


if __name__ == "__main__":
    main()
