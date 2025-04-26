import yaml
import json

# Load YAML file
with open('input.yml', 'r') as yaml_file:
    data = yaml.safe_load(yaml_file)

dependencies = []

# Iterate over each entry
for entry in data:
    if entry.get('enabled', False):
        name = entry.get('name')
        version = entry.get('versionNumber', {})
        major = version.get('major', 0)
        minor = version.get('minor', 0)
        patch = version.get('patch', 0)
        
        dep_string = f"{name}-{major}.{minor}.{patch}"
        dependencies.append(dep_string)

# Write to JSON
output = {
    "dependencies": dependencies
}

with open('output.json', 'w') as json_file:
    json.dump(output, json_file, indent=2)

print("Done! Written to output.json.")
