import json
import toml # type: ignore

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
            namespace, name, _ = dep.split("-")
            deps[f"{namespace}-{name}"] = "*"  # Always latest compatible
        except ValueError:
            print(f"Skipping malformed dependency: {dep}")
            continue

    thunderstore_data = {
        "name": manifest.get("name", "UnknownModpack"),
        "description": manifest.get("description", "No description provided."),
        "version": manifest.get("version_number", "1.0.0"),
        "website_url": manifest.get("website_url", "https://example.com"),
        "contains_nsfw_content": False,
        "package_type": "modpack",
        "communities": ["repo"],  # You may want to adjust this community name
        "categories": ["modpacks"],
        "dependencies": deps
    }

    save_thunderstore_toml(THUNDERSTORE_TOML_PATH, thunderstore_data)
    print("thunderstore.toml updated.")

if __name__ == "__main__":
    main()
