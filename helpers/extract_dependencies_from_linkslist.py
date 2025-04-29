import json

# File paths
input_file = "urls.txt"
output_file = "deps_from_urls.json"

# Read URLs from file
with open(input_file, "r") as f:
    urls = [line.strip() for line in f if line.strip()]

# Extract dependencies
dependencies = []
for url in urls:
    try:
        parts = url.strip("/").split("/")
        namespace = parts[-2]
        modname = parts[-1]
        dependencies.append(f"{namespace}-{modname}-0.0.0")
    except IndexError:
        print(f"Skipping malformed URL: {url}")

# Create output structure
output_data = {
    "dependencies": dependencies
}

# Write to JSON file
with open(output_file, "w") as f:
    json.dump(output_data, f, indent=4)

print(f"Written {len(dependencies)} dependencies to {output_file}")
