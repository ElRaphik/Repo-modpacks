import json
import toml # type: ignore
import os

THUNDERSTORE_TEAM = os.getenv("THUNDERSTORE_TEAM")

MANIFEST_PATH = "manifest.json"
THUNDERSTORE_TOML_PATH = "thunderstore.toml"

def load_manifest(path):
    with open(path, 'r') as f:
        return json.load(f)

def save_thunderstore_toml(path, data):
    with open(path, 'w') as f:
        toml.dump(data, f)

def main():
    manifest = load_manifest(MANIFEST_PATH)
    
    dependencies = manifest.get("dependencies", [])
    deps = {}

    for dep in dependencies:
        try:
            namespace, name, version = dep.split("-")
            deps[f"{namespace}-{name}"] = f"{version}"  # Always latest compatible
        except ValueError:
            print(f"Skipping malformed dependency: {dep}")
            continue
    
    package = {
        "namespace": THUNDERSTORE_TEAM,
        "name": manifest.get("name", "PackageName"),
        "versionNumber": manifest.get("version_number", "1.0.0"),
        "description": manifest.get("description", "No description provided."),
        "website_url": manifest.get("website_url", "https://thunderstore.io"),
        "containsNsfwContent": False,
        "dependencies": deps
    }

    publish = {
        "repository": "https://thunderstore.io",
        "communities": [ "repo", ],
        "categories": { "repo": [ "modpacks", ] }
    }

    config = {
        "schemaVersion": "0.0.1"
    }

    build = {
        "icon": "./icon.png",
        "readme": "./README.md",
        "outdir": "./build",
        "copy": [{ "source": "./", "target": "" }]
    }

    thunderstore_data = {
        "config": config,
        "package": package,
        "publish": publish,
        "build": build
    }

    save_thunderstore_toml(THUNDERSTORE_TOML_PATH, thunderstore_data)
    print("thunderstore.toml updated.")

if __name__ == "__main__":
    main()
