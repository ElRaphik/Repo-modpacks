import json
import os
import requests
from packaging import version
import subprocess
from datetime import date
import sys
import time
import argparse
import threading
import itertools
from colorama import init, Fore, Style

GITHUB_REPO = os.getenv("GITHUB_REPOSITORY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

THUNDERSTORE_API = os.getenv(
    "THUNDERSTORE_API",
    "https://thunderstore.io/c/repo/api/v1/package/"
)
MANIFEST_PATH = "manifest.json"
SNAPSHOT_PATH = ".dependencies_snapshot.json"

MAX_RETRIES = int(os.getenv("THUNDERSTORE_MAX_RETRIES", 3))
RETRY_DELAY = int(os.getenv("THUNDERSTORE_RETRY_DELAY", 5))
TIMEOUT_TIME = int(os.getenv("THUNDERSTORE_TIMEOUT_TIME", 10))

class Spinner:
    def __init__(self, message="Processing... ", delay=0.1):
        self.spinner = itertools.cycle(['⠋', '⠙', '⠚', '⠞', '⠖', '⠦', '⠴', '⠲', '⠳', '⠓'])
        self.stop_running = False
        self.message = message
        self.delay = delay
        self.thread = threading.Thread(target=self.spin)
        self.use_cursor_control = sys.stdout.isatty()

    def hide_cursor(self):
        if self.use_cursor_control:
            sys.stdout.write("\033[?25l")
            sys.stdout.flush()

    def show_cursor(self):
        if self.use_cursor_control:
            sys.stdout.write("\033[?25h")
            sys.stdout.flush()

    def spin(self):
        self.hide_cursor()
        while not self.stop_running:
            sys.stdout.write(f"\r{self.message}{next(self.spinner)}")
            sys.stdout.flush()
            time.sleep(self.delay)
        self.show_cursor()

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_running = True
        self.thread.join()
        sys.stdout.write("\r" + " " * (len(self.message) + 2) + "\r")
        sys.stdout.flush()

def banner(title, filler, color=Fore.WHITE, width=80):
    print("\n" + color + "="*width, flush=True)
    print(f"{color}{title}\n", flush=True)
    print(color + filler, flush=True)
    print(color + "=" * width + Style.RESET_ALL, flush=True)


def log_info(message, spinner=None):
    if spinner:
        spinner.stop()
    print(Fore.BLUE + message, flush=True)
    if spinner:
        spinner.start()

def log_warning(message, spinner=None):
    if spinner:
        spinner.stop()
    print(Fore.YELLOW + message, flush=True)
    if spinner:
        spinner.start()

def log_error(message, spinner=None):
    if spinner:
        spinner.stop()
    print(Fore.RED + message, flush=True)
    if spinner:
        spinner.start()

def update_changelog(new_version, added_mods, updated_mods, removed_mods, dry_run=False):
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

    if dry_run:
        banner("[Dry Run] Would update CHANGELOG.md with:", changelog_entry)
        return

    try:
        with open("CHANGELOG.md", "r") as f:
            existing_changelog = f.read()
    except FileNotFoundError:
        existing_changelog = ""

    with open("CHANGELOG.md", "w") as f:
        f.write(changelog_entry + existing_changelog)

    log_info("CHANGELOG.md updated.")

def load_snapshot(path):
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return []

def save_snapshot(path, dependencies, dry_run=False):
    if dry_run:
        log_info(f"[Dry Run] Would update snapshot {path}")
        return
    with open(path, 'w') as f:
        json.dump(dependencies, f, indent=4)

def bump_patch(ver_str):
    if ver_str == "": return "1.0.0"
    parsed_version = version.parse(ver_str)
    if not isinstance(parsed_version, version.Version):
        raise ValueError(f"Invalid version format: {ver_str}")
    return f"{parsed_version.major}.{parsed_version.minor}.{parsed_version.micro + 1}"

def load_manifest(path):
    with open(path, 'r') as f:
        return json.load(f)

def save_manifest(path, data, dry_run=False):
    if dry_run:
        log_info(f"[Dry Run] Would update manifest {path}")
        return
    unique_dependencies = list(dict.fromkeys(sorted(data.get("dependencies", []))))
    data["dependencies"] = unique_dependencies
    with open(path, 'w') as f:
        json.dump(data, f, indent=4)

def load_thunderstore_packages(verbose=False):
    if verbose:
        log_info("Fetching Thunderstore packages...")
    spinner = Spinner(message="🔄 Fetching Thunderstore packages... ")
    spinner.start()
    try:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = requests.get(THUNDERSTORE_API, headers={"User-Agent": "ElRaphik-Repo-Modpack-Updater/1.0"}, timeout=TIMEOUT_TIME)
                resp.raise_for_status()
                packages = resp.json()

                lookup = {}
                for package in packages:
                    full_name = package.get("full_name")
                    versions = package.get("versions", [])
                    if full_name and versions:
                        lookup[full_name] = versions[0]["version_number"]

                if verbose:
                    log_info(f"Loaded {len(lookup)} packages from Thunderstore.")
                return lookup

            except requests.RequestException as e:
                log_warning(f"Attempt {attempt} failed: {e}")
                if attempt < MAX_RETRIES:
                    log_info(f"Retrying in {RETRY_DELAY} seconds...")
                    time.sleep(RETRY_DELAY)
                else:
                    log_error("❌ Failed to fetch Thunderstore packages after multiple attempts.")
                    sys.exit(1)
    finally:
        spinner.stop()

def create_github_issue(mod_full_name, no_issue=False):
    if no_issue:
        log_warning(f"Skipping issue creation for {mod_full_name} due to --no-issue flag.")
        return
    if not GITHUB_TOKEN or not GITHUB_REPO:
        log_warning("Missing GitHub token or repo. Cannot create issue.")
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
        log_error(f"Failed to create issue: {resp.text}")

def main():
    start_time = time.time()
    init(autoreset=True)

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Run without making any file changes")
    parser.add_argument("--force", action="store_true", help="Force version bump even if nothing changed")
    parser.add_argument("--verbose", action="store_true", help="More verbose output")
    parser.add_argument("--no-issue", action="store_true", help="Do not create GitHub issues for missing dependencies")
    args = parser.parse_args()

    try:
        manifest = load_manifest(MANIFEST_PATH)
    except json.JSONDecodeError:
        log_error(f"❌ Error: {MANIFEST_PATH} is not valid JSON. Please fix it before continuing.")
        sys.exit(1)

    dependencies = manifest.get("dependencies", [])

    updated = False
    new_dependencies = []

    updated_mods = []
    added_mods = []
    removed_mods = []

    thunderstore_lookup = load_thunderstore_packages(verbose=args.verbose)

    spinner = Spinner(message="🔄 Processing dependencies... ")
    spinner.start()

    try:
        for dep in dependencies:
            try:
                namespace, name, current_version = dep.split("-")
                full_mod_name = f"{namespace}-{name}"
            except ValueError:
                log_warning(f"Skipping malformed dependency: {dep}")
                new_dependencies.append(dep)
                continue

            latest = thunderstore_lookup.get(full_mod_name)

            if latest is None:
                log_warning(f"Dependency not found: {dep}")
                create_github_issue(dep, no_issue=args.no_issue)
                new_dependencies.append(dep)
                continue

            if version.parse(latest) > version.parse(current_version):
                log_info(f"Updating {dep} to version {latest}")
                updated = True
                new_dep = f"{namespace}-{name}-{latest}"
                new_dependencies.append(new_dep)
                updated_mods.append(f"{namespace}-{name} ({current_version} → {latest})")
            else:
                new_dependencies.append(dep)
    finally:
        spinner.stop()

    snapshot_dependencies = load_snapshot(SNAPSHOT_PATH)

    if new_dependencies != snapshot_dependencies:
        log_info("Dependencies list changed (mod added or removed).")
        updated = True

        snapshot_set = set(snapshot_dependencies)
        current_set = set(new_dependencies)

        added = current_set - snapshot_set
        removed = snapshot_set - current_set

        for mod in added:
            added_mods.append(mod)

        for mod in removed:
            removed_mods.append(mod)

    if updated or args.force:
        manifest["dependencies"] = sorted(new_dependencies)

        current_version = manifest.get("version_number", "")
        new_version = bump_patch(current_version)
        manifest["version_number"] = new_version

        save_manifest(MANIFEST_PATH, manifest, dry_run=args.dry_run)
        log_info(f"Manifest updated. Version bumped to v{new_version}")

        save_snapshot(SNAPSHOT_PATH, new_dependencies, dry_run=args.dry_run)

        if not args.dry_run:
            with open("version.txt", "w") as f:
                f.write(new_version)

        if not args.dry_run:
            try:
                subprocess.run(["python", "generate_thunderstore_toml.py"], check=True)
                log_info("thunderstore.toml regenerated successfully.")
            except subprocess.CalledProcessError:
                log_error("Failed to regenerate thunderstore.toml.")

        update_changelog(new_version, added_mods, updated_mods, removed_mods, dry_run=args.dry_run)
    else:
        log_info("All dependencies are up to date. No changes, skipping thunderstore.toml regeneration.")

    elapsed_time = time.time() - start_time
    banner("✅ Done", f"Update process completed in {elapsed_time:.2f} seconds.", color=Fore.GREEN)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log_error(f"❌ Unexpected error occurred: {e}")
        sys.exit(1)