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
import shutil

GITHUB_REPO = os.getenv("GITHUB_REPOSITORY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

THUNDERSTORE_API = os.getenv(
    "THUNDERSTORE_API",
    "https://thunderstore.io/c/repo/api/v1/package/"
)
MANIFEST_PATH = "manifest.json"
SNAPSHOT_PATH = ".dependencies_snapshot.json"

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

def center_text_if_possible(text):
    try:
        terminal_width = shutil.get_terminal_size().columns
    except:
        terminal_width = 80  # fallback in case terminal size cannot be detected

    max_line_length = max(len(line) for line in text.split('\n'))

    if terminal_width >= max_line_length:
        return '\n'.join(line.center(terminal_width) for line in text.split('\n'))
    else:
        return text  # no centering if too small

def print_ascii_logo():
    logo = r"""
 _____ _______            _     _ _    _        ______       _____      ______       _____     
|  ___| | ___ \          | |   (_) |  ( )       | ___ \     |  ___|     | ___ \     |  _  |    
| |__ | | |_/ /__ _ _ __ | |__  _| | _|/ ___    | |_/ /     | |__       | |_/ /     | | | |    
|  __|| |    // _` | '_ \| '_ \| | |/ / / __|   |    /      |  __|      |  __/      | | | |    
| |___| | |\ \ (_| | |_) | | | | |   <  \__ \   | |\ \   _  | |___   _  | |      _  \ \_/ /  _ 
\____/|_\_| \_\__,_| .__/|_| |_|_|_|\_\ |___/   \_| \_| (_) \____/  (_) \_|     (_)  \___/  (_)
                   | |                                                                         
___  ___          _|_|               _        _   _           _       _                        
|  \/  |         | |                | |      | | | |         | |     | |                       
| .  . | ___   __| |_ __   __ _  ___| | __   | | | |_ __   __| | __ _| |_ ___ _ __             
| |\/| |/ _ \ / _` | '_ \ / _` |/ __| |/ /   | | | | '_ \ / _` |/ _` | __/ _ \ '__|            
| |  | | (_) | (_| | |_) | (_| | (__|   <    | |_| | |_) | (_| | (_| | ||  __/ |               
\_|  |_/\___/ \__,_| .__/ \__,_|\___|_|\_\    \___/| .__/ \__,_|\__,_|\__\___|_|               
                   | |                             | |                                         
                   |_|                             |_|                                         
    """
    print(Fore.CYAN + center_text_if_possible(logo), flush=True)

def announce_mode(dry_run):
    if dry_run:
        print(Fore.YELLOW + "[Mode] Running in DRY-RUN mode. No changes will be saved.", flush=True)
    else:
        print(Fore.GREEN + "[Mode] Running in REAL mode. Changes will be applied.", flush=True)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", default=os.getenv("DRY_RUN", "false").lower() == "true", help="Run without making any file changes")
    parser.add_argument("--force", action="store_true", default=os.getenv("FORCE", "false").lower() == "true", help="Force version bump even if nothing changed")
    parser.add_argument("--verbose", action="store_true", default=os.getenv("VERBOSE", "false").lower() == "true", help="More verbose output")
    parser.add_argument("--no-issue", action="store_true", default=os.getenv("NO_ISSUE", "false").lower() == "true", help="Do not create GitHub issues for missing dependencies")
    parser.add_argument("--major-upgrade", action="store_true", default=os.getenv("MAJOR_UPGRADE", "false").lower() == "true", help="Force a major version bump (resets minor and patch)")
    parser.add_argument("--max-retries", type=int, default=int(os.getenv("THUNDERSTORE_MAX_RETRIES", 3)), help="Max retries for Thunderstore API requests")
    parser.add_argument("--retry-delay", type=int, default=int(os.getenv("THUNDERSTORE_RETRY_DELAY", 5)), help="Delay between retries for Thunderstore API requests (seconds)")
    parser.add_argument("--timeout-time", type=int, default=int(os.getenv("THUNDERSTORE_TIMEOUT_TIME", 10)), help="Timeout for Thunderstore API requests (seconds)")
    return parser.parse_args()

def safe_run_subprocess(cmd):
    try:
        subprocess.run(cmd, check=True)
        log_info(f"Command succeeded: {' '.join(cmd)}")
    except subprocess.CalledProcessError:
        log_error(f"Failed command: {' '.join(cmd)}")
        sys.exit(1)

def banner(title, filler="", color=Fore.WHITE, width=80, endline=False):
    print("\n" + color + "="*width, flush=True)
    print(f"{color}{title}\n", flush=True)
    print(filler, flush=True)
    if endline: print(color + "=" * width + Style.RESET_ALL, flush=True)

def write_version_txt(version, dry_run=False):
    if dry_run:
        log_info("[Dry Run] Would write version.txt")
        return
    with open("version.txt", "w") as f:
        f.write(version)

def log_info(message, spinner=None):
    if spinner:
        spinner.stop()
        spinner = Spinner(message=spinner.message, delay=spinner.delay)
    print(Fore.BLUE + message, flush=True)
    if spinner:
        spinner.start()
        return spinner

def log_warning(message, spinner=None):
    if spinner:
        spinner.stop()
        spinner = Spinner(message=spinner.message, delay=spinner.delay)
    print(Fore.YELLOW + message, flush=True)
    if spinner:
        spinner.start()
        return spinner

def log_error(message, spinner=None):
    if spinner:
        spinner.stop()
        spinner = Spinner(message=spinner.message, delay=spinner.delay)
    print(Fore.RED + message, flush=True)
    if spinner:
        spinner.start()
        return spinner

def update_changelog(new_version, added_mods: list, updated_mods, removed_mods, thunderstore_lookup, dry_run=False):
    today = date.today().isoformat()
    changelog_entry = f"## v{new_version} - {today}\n\n"

    sections_written = False

    if added_mods:
        changelog_entry += f"<details>\n<summary>📦 Added ({len(added_mods)} mods)</summary>\n\n"
        for mod in sorted(added_mods):
            namespace, name = mod.split("-", 2)
            full_mod_name = f"{namespace}-{name}"
            package_url = thunderstore_lookup.get(full_mod_name).get("package_url")
            changelog_entry += f"- [{namespace}-{name}]({package_url})\n"
        changelog_entry += "</details>\n\n"
        sections_written = True

    if updated_mods:
        changelog_entry += f"<details>\n<summary>🔄 Updated ({len(updated_mods)} mods)</summary>\n\n"
        for mod in sorted(updated_mods):
            parts = mod.split(" (")
            namespace_name = parts[0]
            namespace, name = namespace_name.split("-", 1)
            full_mod_name = f"{namespace}-{name}"
            package_url = thunderstore_lookup.get(full_mod_name).get("package_url")
            changelog_entry += f"- [{namespace}-{name}]({package_url}) ({parts[1]}\n" # Is correct because parts[1] already includes the closing )
        changelog_entry += "</details>\n\n"
        sections_written = True

    if removed_mods:
        changelog_entry += f"<details>\n<summary>❌ Removed ({len(removed_mods)} mods)</summary>\n\n"
        for mod in sorted(removed_mods):
            namespace, name = mod.split("-", 2)
            full_mod_name = f"{namespace}-{name}"
            package_url = thunderstore_lookup.get(full_mod_name).get("package_url")
            changelog_entry += f"- [{namespace}-{name}]({package_url})\n"
        changelog_entry += "</details>\n\n"
        sections_written = True

    if not sections_written:
        changelog_entry += "No dependency changes in this release.\n\n"

    changelog_entry = changelog_entry.rstrip("\n") + "\n\n"

    if dry_run:
        banner("[Dry Run] Would update CHANGELOG.md with:", filler=changelog_entry)
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

def color_bumped_version(old_version, new_version):
    old_parts = old_version.split(".")
    new_parts = new_version.split(".")
    
    result = []
    bumped = False

    for i in range(3):
        if not bumped and old_parts[i] != new_parts[i]:
            if i == 0:
                result.append(Fore.RED + new_parts[i])
            elif i == 1:
                result.append(Fore.YELLOW + new_parts[i])
            elif i == 2:
                result.append(Fore.GREEN + new_parts[i])
            bumped = True
        else:
            result.append(new_parts[i])

    return ".".join(result)

def bump_version(current_version, added_mods, updated_mods, removed_mods, force_major_upgrade=False):
    if current_version == "":
        return "1.0.0"

    parsed_version = version.parse(current_version)
    if not isinstance(parsed_version, version.Version):
        raise ValueError(f"Invalid version format: {current_version}")

    major = parsed_version.major
    minor = parsed_version.minor
    patch = parsed_version.micro

    if force_major_upgrade:
        major += 1
        minor = 0
        patch = 0
    elif added_mods or removed_mods:
        minor += 1
        patch = 0
    elif updated_mods:
        patch += 1
    else:
        # No change needed if no mods at all, but return current
        pass

    return f"{major}.{minor}.{patch}"

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

def fetch_thunderstore_packages(max_retries, retry_delay, timeout_time, verbose=False):
    spinner = Spinner(message="🔄 Fetching Thunderstore packages... ")
    spinner.start()
    try:
        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.get(THUNDERSTORE_API, headers={"User-Agent": "ElRaphik-Repo-Modpack-Updater/1.0"}, timeout=timeout_time)
                resp.raise_for_status()
                packages = resp.json()
                lookup = {}
                for package in packages:
                    full_name = package.get("full_name")
                    versions = package.get("versions", [])
                    package_url = package.get("package_url", "")
                    if full_name:
                        lookup[full_name] = {
                            "version": versions[0]["version_number"],
                            "package_url": package_url
                        }
                if verbose:
                    spinner = log_info(f"Loaded {len(lookup)} packages from Thunderstore.", spinner=spinner)
                return lookup
            except requests.RequestException as e:
                log_warning(f"Attempt {attempt} failed: {e}")
                if attempt < max_retries:
                    spinner = log_info(f"Retrying in {retry_delay} seconds...", spinner=spinner)
                    time.sleep(retry_delay)
                else:
                    spinner = log_error("❌ Failed to fetch Thunderstore packages after multiple attempts.", spinner=spinner)
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

def process_dependencies(dependencies, thunderstore_lookup, args):
    updated = False
    new_dependencies = []
    updated_mods = []

    spinner = Spinner(message="🔄 Processing dependencies... ")
    spinner.start()

    try:
        for dep in dependencies:
            if args.verbose: spinner = log_info(f"Treating dependency: {dep}", spinner=spinner)
            try:
                namespace, name, current_version = dep.split("-")
                full_mod_name = f"{namespace}-{name}"
            except ValueError:
                spinner = log_warning(f"Skipping malformed dependency: {dep}", spinner=spinner)
                new_dependencies.append(dep)
                continue

            latest = thunderstore_lookup.get(full_mod_name).get("version")

            if latest is None:
                spinner = log_warning(f"Dependency not found: {dep}", spinner=spinner)
                create_github_issue(dep, no_issue=args.no_issue)
                new_dependencies.append(dep)
                continue

            if version.parse(latest) > version.parse(current_version):
                spinner = log_info(f"Updating {dep} to version {latest}", spinner=spinner)
                updated = True
                new_dep = f"{namespace}-{name}-{latest}"
                new_dependencies.append(new_dep)
                updated_mods.append(f"{namespace}-{name} ({current_version} → {latest})")
            else:
                new_dependencies.append(dep)
    finally:
        spinner.stop()

    return updated, new_dependencies, updated_mods

def main(args):
    start_time = time.time()
    init(autoreset=True)

    print_ascii_logo()
    announce_mode(args.dry_run)

    try:
        manifest = load_manifest(MANIFEST_PATH)
    except json.JSONDecodeError:
        log_error(f"❌ Error: {MANIFEST_PATH} is not valid JSON. Please fix it before continuing.")
        sys.exit(1)

    dependencies = manifest.get("dependencies", [])
    added_mods = []
    removed_mods = []

    thunderstore_lookup = fetch_thunderstore_packages(
        max_retries=args.max_retries,
        retry_delay=args.retry_delay,
        timeout_time=args.timeout_time,
        verbose=args.verbose
    )

    updated, new_dependencies, updated_mods = process_dependencies(dependencies, thunderstore_lookup, args)

    snapshot_dependencies = load_snapshot(SNAPSHOT_PATH)

    snapshot_names = {"-".join(dep.split("-")[:2]) for dep in snapshot_dependencies}
    current_names = {"-".join(dep.split("-")[:2]) for dep in new_dependencies}

    if current_names != snapshot_names:
        log_info("Dependencies list changed (mod added or removed).")
        updated = True

        snapshot_set = set(snapshot_names)
        current_set = set(current_names)

        added = current_set - snapshot_set
        removed = snapshot_set - current_set

        for mod in added:
            added_mods.append(mod)

        for mod in removed:
            removed_mods.append(mod)

    filtered_updated_mods = []
    if updated or args.force:
        manifest["dependencies"] = sorted(new_dependencies)

        current_version = manifest.get("version_number", "")
        new_version = bump_version(
            current_version,
            added_mods=added_mods,
            updated_mods=updated,
            removed_mods=removed_mods,
            force_major_upgrade=args.major_upgrade
            )
        
        manifest["version_number"] = new_version
        save_manifest(MANIFEST_PATH, manifest, dry_run=args.dry_run)

        colored_new_version = color_bumped_version(current_version, new_version)
        log_info(f"Manifest updated. Version bumped to v{colored_new_version}")

        save_snapshot(SNAPSHOT_PATH, new_dependencies, dry_run=args.dry_run)
        write_version_txt(new_version, dry_run=args.dry_run)

        if not args.dry_run:
            safe_run_subprocess(["python", "generate_thunderstore_toml.py"])


        # Prepare set of added mod names (namespace-name only)
        added_mods_basenames = set("-".join(mod.split("-")[:2]) for mod in added_mods)

        # Filter updated_mods to exclude any that were just added
        for mod in updated_mods:
            namespace_name = mod.split(" (")[0]  # Extract namespace-name from update string
            if namespace_name not in added_mods_basenames:
                filtered_updated_mods.append(mod)

        update_changelog(new_version, added_mods, filtered_updated_mods, removed_mods, thunderstore_lookup, dry_run=args.dry_run)
    else:
        log_info("All dependencies are up to date. No changes, skipping thunderstore.toml regeneration.")

    elapsed_time = time.time() - start_time
    banner(
        "✅ Done",
        filler=f"Update process completed in {elapsed_time:.2f} seconds.\n{Fore.BLUE}Summary: 📦 {len(added_mods)} added, 🔄 {len(filtered_updated_mods)} updated, ❌ {len(removed_mods)} removed.",
        color=Fore.GREEN,
        endline=True
        )


if __name__ == "__main__":
    args = parse_args()

    try:
        main(args)
    except KeyboardInterrupt:
        log_error("❌ Script interrupted by user.")
        sys.exit(1)
    except Exception as e:
        log_error(f"❌ Unexpected error occurred: {e}")
        sys.exit(1)