import os
import re
import datetime
import calendar
import webbrowser
import threading
import json
import time
import signal
import subprocess
from flask import Flask, render_template, jsonify, request
from collections import defaultdict

app = Flask(__name__)

# =============================
# User-configurable defaults
# Edit these values and save if needed
# =============================
MARKDOWN_RELATIVE_PATH = "1.5 Weekend Routine BLOCKS.md"
DEFAULT_HOST_FALLBACK = "127.0.0.1"
DEFAULT_PORT_FALLBACK = 5002
DEBUG_DEFAULT = False
OPEN_BROWSER_DEFAULT = True
BROWSER_OPEN_DELAY_SECONDS = 1
JOURNAL_FOLDER_DEFAULT = "/home/aditya/obsidian/All Things/Journal/Daily Journal/"

# --- Derived paths ---
MARKDOWN_FILE_PATH = os.path.join(os.path.dirname(__file__), MARKDOWN_RELATIVE_PATH)
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

# --- Runtime configuration (env overrides allowed) ---
HOST = os.environ.get("HOST", os.environ.get("FLASK_RUN_HOST", DEFAULT_HOST_FALLBACK))
_port_str = os.environ.get("PORT", os.environ.get("FLASK_RUN_PORT", str(DEFAULT_PORT_FALLBACK)))
try:
    PORT = int(_port_str)
except ValueError:
    PORT = DEFAULT_PORT_FALLBACK

_debug_env = os.environ.get("FLASK_DEBUG", os.environ.get("DEBUG", "1" if DEBUG_DEFAULT else "0")).strip().lower()
DEBUG_MODE = _debug_env in {"1", "true", "yes", "on"}
_open_browser_env = os.environ.get("OPEN_BROWSER", "1" if OPEN_BROWSER_DEFAULT else "0").strip().lower()
OPEN_BROWSER = _open_browser_env in {"1", "true", "yes", "on"}

# --- Config file helpers ---
DEFAULT_CONFIG = {
    "markdown_relative_path": MARKDOWN_RELATIVE_PATH,
    "host": DEFAULT_HOST_FALLBACK,
    "port": DEFAULT_PORT_FALLBACK,
    "debug": DEBUG_DEFAULT,
    "open_browser": OPEN_BROWSER_DEFAULT,
    "browser_open_delay_seconds": BROWSER_OPEN_DELAY_SECONDS,
    "journal_folder": JOURNAL_FOLDER_DEFAULT,
}

def load_config():
    config = DEFAULT_CONFIG.copy()
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                file_cfg = json.load(f)
                if isinstance(file_cfg, dict):
                    config.update(file_cfg)
    except Exception as e:
        print(f"Warning: Failed to load config.json: {e}")
    return config

def save_config(config: dict):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"Error writing config.json: {e}")
        return False

def get_markdown_file_path_from_config(config: dict) -> str:
    raw_path = config.get("markdown_relative_path") or MARKDOWN_RELATIVE_PATH
    if os.path.isabs(raw_path):
        return raw_path
    return os.path.join(os.path.dirname(__file__), raw_path)

def _parse_date_from_filename(filename: str):
    try:
        m = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
        if m:
            return datetime.date.fromisoformat(m.group(1))
    except Exception:
        return None
    return None

def build_history_for_tasks(task_names: list, journal_folder: str) -> dict:
    """Scan journal markdown files for scheduled task occurrences and completion status.
    Returns mapping: taskName -> { occurrences: [{date, done}], not_done_latest: 'YYYY-MM-DD' or None }
    """
    history: dict = {}
    for name in task_names:
        history[name] = {"occurrences": [], "not_done_latest": None}
    try:
        if not journal_folder or not os.path.isdir(journal_folder):
            return history
        for entry in os.listdir(journal_folder):
            if not entry.lower().endswith(".md"):
                continue
            file_date = _parse_date_from_filename(entry)
            if file_date is None:
                continue
            full_path = os.path.join(journal_folder, entry)
            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        # Basic checkbox pattern
                        if "- [" not in line:
                            continue
                        for task_name in task_names:
                            if task_name in line:
                                done = "- [x]" in line.lower()
                                history[task_name]["occurrences"].append({
                                    "date": file_date.isoformat(),
                                    "done": done
                                })
            except Exception:
                continue
        # compute latest not-done date
        for name in task_names:
            not_done_dates = [o["date"] for o in history[name]["occurrences"] if not o["done"]]
            if not_done_dates:
                history[name]["not_done_latest"] = sorted(not_done_dates)[-1]
    except Exception:
        return history
    return history

# --- Process info ---
START_TIME_EPOCH = time.time()

def get_process_info() -> dict:
    uptime_seconds = max(0, int(time.time() - START_TIME_EPOCH))
    return {
        "pid": os.getpid(),
        "host": HOST,
        "port": PORT,
        "debug": DEBUG_MODE,
        "open_browser": OPEN_BROWSER,
        "start_time_epoch": int(START_TIME_EPOCH),
        "uptime_seconds": uptime_seconds,
    }

def list_weekend_processes() -> list:
    """List running processes related to the Weekend planner app, similar to WeekDAY implementation."""
    try:
        # Match common invocations: running app.py directly or via Flask CLI
        grep_patterns = [
            'WeekENDplanner/app.py',
            'FLASK_APP=',  # env-var style run
            'start_weekendplanner.sh',
        ]
        cmd = "ps aux"
        process = os.popen(cmd)
        output = process.read()
        processes = []
        for line in output.splitlines():
            # Skip the grep line safety isn't needed since we don't run grep, but keep simple filters
            if not any(pat in line for pat in grep_patterns):
                continue
            parts = line.split()
            if len(parts) > 1:
                try:
                    pid = int(parts[1])
                except Exception:
                    continue
                command = ' '.join(parts[10:]) if len(parts) > 10 else line
                processes.append({"pid": pid, "command": command})
        # De-duplicate by pid
        seen = set()
        unique = []
        for p in processes:
            if p["pid"] in seen:
                continue
            seen.add(p["pid"])
            unique.append(p)
        return unique
    except Exception as e:
        return [{"error": f"Failed to get processes: {e}"}]

def get_current_weekend():
    """Generates a list of Saturday and Sunday for the upcoming weekend."""
    today = datetime.date.today()
    # Upcoming Saturday from today
    saturday = today + datetime.timedelta(days=(calendar.SATURDAY - today.weekday() + 7) % 7)
    sunday = saturday + datetime.timedelta(days=1)

    weekends = []
    # Order: Saturday, Sunday
    for d in [saturday, sunday]:
        weekends.append({
            "date": d.isoformat(),
            "week_number": d.isocalendar()[1],
            "day_name": d.strftime("%A"),
            "full_date_display": d.strftime("(%A, %B %d, %Y)")
        })
    return weekends

def extract_tasks_from_markdown(file_path):
    tasks_data = {"weekly": [], "monthly": [], "table_view": {}}
    all_tag_paths = set()
    task_lines = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                # Accept both historical and current tag families for weekend tasks
                if re.search(r'#Task/(?:WhatTASK|NameAndType)/WeekendTASKgroup\b', line):
                    task_lines.append(line)
                    tags_in_line = re.findall(r'#(\S+)', line)
                    for tag in tags_in_line:
                        parts = tag.split('/')
                        if len(parts) > 1:
                            tag_path = '/'.join(parts[:-1])
                            all_tag_paths.add(tag_path)

        # Custom sort key for headers (prefer Task/WhenAndDuration family)
        def custom_sort_key(tag_path):
            if tag_path.startswith('Task/WhenAndDuration'):
                order_map = {
                    'Task/WhenAndDuration/Weekly': (0, 0),
                    'Task/WhenAndDuration/Whichday': (0, 1),
                    'Task/WhenAndDuration/Monthly': (0, 2),
                    'Task/WhenAndDuration/WhichWeek': (0, 3),
                    'Task/WhenAndDuration/DefaultDuration': (0, 4),
                }
                return order_map.get(tag_path, (0, 99,)) + (tag_path,)
            if tag_path.startswith('Task/When'):
                order_map_legacy = {
                    'Task/When/Weekly': (1, 0),
                    'Task/When/Whichday': (1, 1),
                    'Task/When/Monthly': (1, 2),
                    'Task/When/WhichWeek': (1, 3),
                }
                return order_map_legacy.get(tag_path, (1, 99,)) + (tag_path,)
            elif tag_path.startswith('Task/Action'):
                return (1, tag_path) # 'Task/Action' tags come second
            else:
                return (2, tag_path) # All other tags come last

        sorted_tag_paths = sorted(list(all_tag_paths), key=custom_sort_key)
        # Normalize some legacy keys for UI expectations
        normalized_headers = []
        for h in sorted_tag_paths:
            if h == 'Task/When/Whichday':
                normalized_headers.append('Task/When/Whichday')
            else:
                normalized_headers.append(h)
        
        table_tasks = []

        for line in task_lines:
            task_name_match = re.search(r'\*\*(.*?)\*\*', line)
            if not task_name_match: continue
            
            task_name = task_name_match.group(1).strip()
            tags_in_line = re.findall(r'#(\S+)', line)
            
            task_tag_values = defaultdict(list)
            for tag in tags_in_line:
                parts = tag.split('/')
                if len(parts) > 1:
                    tag_path = '/'.join(parts[:-1])
                    value = parts[-1]
                    task_tag_values[tag_path].append(value)
            
            table_tasks.append({"name": task_name, "tag_values": dict(task_tag_values)})

            # Logic for draggable tasks
            # Prefer WhenAndDuration family; accept legacy as fallback
            weekly_match = re.search(r'#Task/WhenAndDuration/Weekly/(\d+)[xX]', line, flags=re.IGNORECASE) or \
                           re.search(r'#Task/When/Weekly/(\d+)[xX]', line, flags=re.IGNORECASE)
            monthly_match = re.search(r'#Task/WhenAndDuration/Monthly/(\d+)[xX]', line, flags=re.IGNORECASE) or \
                            re.search(r'#Task/When/Monthly/(\d+)[xX]', line, flags=re.IGNORECASE)
            frequency_count = 1
            
            if weekly_match:
                category = "weekly"
                count = int(weekly_match.group(1))
                frequency_desc = f"{count}X Weekly"
                frequency_count = count
            elif monthly_match:
                category = "monthly"
                count = int(monthly_match.group(1))
                frequency_desc = f"{count}X Monthly"
                frequency_count = count
            else:
                # Default to monthly if neither weekly nor explicit monthly counts present
                category = "monthly"
                frequency_desc = "1X Monthly"

            tasks_data[category].append({
                "name": task_name,
                "frequency_desc": frequency_desc,
                "frequency_count": frequency_count
            })

        tasks_data["table_view"] = {
            "headers": normalized_headers,
            "tasks": table_tasks
        }

    except FileNotFoundError:
        print(f"Error: Markdown file not found at {file_path}")
    except Exception as e:
        print(f"An error occurred: {e}")
    return tasks_data

def _update_line_tags(line: str, updates: dict) -> str:
    """Given a markdown line and a mapping tag_path -> [values],
    remove existing tags for provided paths (and legacy When/* for WhenAndDuration/*),
    then append new tags at the end in a stable order."""
    try:
        tokens = line.split()
        # Build set of paths to remove
        remove_prefixes = set(updates.keys())
        # Also remove legacy When/* variants for WhenAndDuration/* paths
        for p in list(remove_prefixes):
            if p.startswith('Task/WhenAndDuration/'):
                legacy = p.replace('Task/WhenAndDuration/', 'Task/When/')
                remove_prefixes.add(legacy)

        def keep_token(tok: str) -> bool:
            if not tok.startswith('#'):
                return True
            body = tok[1:]
            # Token shape: Path/Value (no spaces)
            # Remove if body starts with any remove_prefix
            for pref in remove_prefixes:
                if body.startswith(pref + '/') or body == pref:
                    return False
            return True

        kept = [t for t in tokens if keep_token(t)]

        # Append new tags (skip empty values)
        new_tags = []
        def add_tags_for(path: str, values: list):
            for v in values or []:
                v = str(v).strip()
                if not v:
                    continue
                new_tags.append(f"#{path}/{v}")

        # Stable order: WhenAndDuration first, then everything else alpha
        wad = {k: v for k, v in updates.items() if k.startswith('Task/WhenAndDuration/')}
        other = {k: v for k, v in updates.items() if k not in wad}
        for k in sorted(wad.keys()):
            add_tags_for(k, wad[k])
        for k in sorted(other.keys()):
            add_tags_for(k, other[k])

        # Rebuild line: preserve original non-tag spacing by joining with single spaces
        result = ' '.join([t for t in kept if t])
        if new_tags:
            result = (result + ' ' + ' '.join(new_tags)).strip()
        return result
    except Exception:
        return line

@app.route('/api/tasks/save', methods=['POST'])
def api_tasks_save():
    """Save edits from the master table back to the markdown file.
    Expected JSON: { tasks: [ { name: str, tag_values: { path: [values...] } }, ... ] }
    Only provided tag paths are updated for each task; other tags remain untouched."""
    try:
        payload = request.get_json(force=True, silent=False)
        if not isinstance(payload, dict) or not isinstance(payload.get('tasks'), list):
            return jsonify({"error": "Invalid payload"}), 400

        cfg = load_config()
        md_path = get_markdown_file_path_from_config(cfg)
        if not os.path.isfile(md_path):
            return jsonify({"error": f"Markdown not found: {md_path}"}), 404

        with open(md_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Index task lines by name occurrence (bold **name**)
        name_to_idx = {}
        for idx, line in enumerate(lines):
            m = re.search(r"\*\*(.*?)\*\*", line)
            if m:
                name = m.group(1).strip()
                # First occurrence wins
                if name not in name_to_idx:
                    name_to_idx[name] = idx

        changed = 0
        for item in payload['tasks']:
            name = (item.get('name') or '').strip()
            tv = item.get('tag_values') or {}
            if not name or not isinstance(tv, dict):
                continue
            idx = name_to_idx.get(name)
            if idx is None:
                # Skip unknown tasks (not found in file)
                continue
            # Normalize tv values to lists of strings
            normalized = {}
            for path, vals in tv.items():
                if not path or not isinstance(path, str):
                    continue
                if vals is None:
                    vals = []
                if isinstance(vals, str):
                    vals = [vals]
                vals2 = []
                for v in vals:
                    if v is None:
                        continue
                    s = str(v).strip()
                    if s:
                        vals2.append(s)
                normalized[path] = vals2
            new_line = _update_line_tags(lines[idx].rstrip('\n'), normalized)
            if new_line != lines[idx].rstrip('\n'):
                lines[idx] = new_line + "\n"
                changed += 1

        if changed > 0:
            # Backup
            try:
                backup_path = md_path + ".bak"
                if not os.path.exists(backup_path):
                    with open(backup_path, 'w', encoding='utf-8') as bf:
                        bf.writelines(lines)
            except Exception:
                pass
            with open(md_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)

        return jsonify({"ok": True, "updated": changed})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/")
def home():
    weekends = get_current_weekend()
    month_name = datetime.date.today().strftime("%B %Y")
    print(f"Weekends data sent to template: {weekends}") # Diagnostic print
    return render_template("index.html", weekends=weekends, month_name=month_name)

@app.route("/api/tasks")
def get_tasks():
    cfg = load_config()
    md_path = get_markdown_file_path_from_config(cfg)
    tasks = extract_tasks_from_markdown(md_path)
    # Attach history/status info from journal
    journal_folder = cfg.get("journal_folder", JOURNAL_FOLDER_DEFAULT)
    all_task_names = [t["name"] for t in tasks.get("weekly", [])] + [t["name"] for t in tasks.get("monthly", [])]
    history = build_history_for_tasks(all_task_names, journal_folder)
    tasks["history"] = history
    return jsonify(tasks)

@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    if request.method == "GET":
        return jsonify(load_config())

    # POST: accept JSON body
    try:
        payload = request.get_json(force=True, silent=False)
        if not isinstance(payload, dict):
            return jsonify({"error": "Invalid JSON"}), 400

        cfg = load_config()
        new_markdown = str(payload.get("markdown_relative_path", cfg.get("markdown_relative_path", "")).strip())
        new_host = str(payload.get("host", cfg.get("host", "")).strip())
        new_port = payload.get("port", cfg.get("port", PORT))
        new_debug = bool(payload.get("debug", cfg.get("debug", DEBUG_MODE)))
        new_open_browser = bool(payload.get("open_browser", cfg.get("open_browser", OPEN_BROWSER)))
        new_delay = payload.get("browser_open_delay_seconds", cfg.get("browser_open_delay_seconds", 1))

        try:
            new_port = int(new_port)
        except Exception:
            return jsonify({"error": "Port must be an integer"}), 400
        try:
            new_delay = max(0, int(new_delay))
        except Exception:
            return jsonify({"error": "Browser open delay must be a non-negative integer"}), 400

        cfg.update({
            "markdown_relative_path": new_markdown,
            "host": new_host or DEFAULT_HOST_FALLBACK,
            "port": new_port,
            "debug": new_debug,
            "open_browser": new_open_browser,
            "browser_open_delay_seconds": new_delay,
        })

        if save_config(cfg):
            return jsonify({"ok": True, "message": "Settings saved. Host/port/debug changes require restart."})
        return jsonify({"error": "Failed to write settings. Check file permissions."}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/process", methods=["GET"])
def api_process_info():
    return jsonify(get_process_info())

def _shutdown_server_background():
    # Attempt graceful Werkzeug shutdown; fall back to SIGTERM, then hard exit
    def _do_shutdown():
        try:
            shutdown_func = request.environ.get('werkzeug.server.shutdown')
            if callable(shutdown_func):
                shutdown_func()
                return
        except Exception:
            pass
        try:
            os.kill(os.getpid(), signal.SIGTERM)
            return
        except Exception:
            pass
        os._exit(0)  # Last resort

    threading.Thread(target=_do_shutdown, daemon=True).start()

@app.route("/api/process/kill", methods=["POST"])
def api_process_kill():
    # Respond first, then stop in the background so client gets a reply
    _shutdown_server_background()
    return jsonify({"ok": True, "message": "Server shutting down..."})

def _restart_in_background():
    """Spawn a new app instance via the start script after a short delay, then stop current."""
    def _runner():
        try:
            time.sleep(1.5)
            script_path = os.path.join(os.path.dirname(__file__), 'start_weekendplanner.sh')
            # Ensure executable spawn detached
            subprocess.Popen([
                script_path
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"Failed to spawn restart: {e}")
        finally:
            try:
                os.kill(os.getpid(), signal.SIGTERM)
            except Exception:
                os._exit(0)
    threading.Thread(target=_runner, daemon=True).start()

@app.route("/api/process/restart", methods=["POST"])
def api_process_restart():
    # Fire-and-forget restart; return immediately
    _restart_in_background()
    return jsonify({"ok": True, "message": "Restarting server..."})

@app.route("/api/processes", methods=["GET"])
def api_list_processes():
    return jsonify({"running_processes": list_weekend_processes()})

@app.route("/api/processes/kill", methods=["POST"])
def api_kill_selected_processes():
    try:
        payload = request.get_json(force=True, silent=False)
        pids = payload.get("pids", []) if isinstance(payload, dict) else []
        if not isinstance(pids, list):
            return jsonify({"error": "pids must be a list"}), 400
        killed = 0
        errors = []
        for pid in pids:
            try:
                os.kill(int(pid), signal.SIGKILL)
                killed += 1
            except ProcessLookupError:
                errors.append({"pid": pid, "error": "not found"})
            except Exception as e:
                errors.append({"pid": pid, "error": str(e)})
        return jsonify({"ok": True, "killed": killed, "errors": errors})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/settings", methods=["GET", "POST"])
def settings():
    cfg = load_config()
    message = None
    error = None

    if request.method == "POST":
        try:
            new_markdown = request.form.get("markdown_relative_path", cfg.get("markdown_relative_path", "")).strip()
            new_host = request.form.get("host", cfg.get("host", "")).strip()
            new_port_str = request.form.get("port", str(cfg.get("port", DEFAULT_PORT_FALLBACK))).strip()
            new_debug = request.form.get("debug") == "on"
            new_open_browser = request.form.get("open_browser") == "on"
            new_delay_str = request.form.get("browser_open_delay_seconds", str(cfg.get("browser_open_delay_seconds", 1))).strip()

            try:
                new_port = int(new_port_str)
            except ValueError:
                raise ValueError("Port must be an integer")

            try:
                new_delay = max(0, int(new_delay_str))
            except ValueError:
                raise ValueError("Browser open delay must be a non-negative integer")

            cfg.update({
                "markdown_relative_path": new_markdown,
                "host": new_host or DEFAULT_HOST_FALLBACK,
                "port": new_port,
                "debug": new_debug,
                "open_browser": new_open_browser,
                "browser_open_delay_seconds": new_delay,
            })

            if save_config(cfg):
                message = "Settings saved. Host/port/debug changes require restart to take effect."
            else:
                error = "Failed to write settings. Check file permissions."
        except Exception as e:
            error = str(e)

    return render_template("settings.html", config=cfg, message=message, error=error)

def open_browser():
    # If binding to 0.0.0.0/::, open localhost in browser instead
    browser_host = "127.0.0.1" if HOST in {"0.0.0.0", "::"} else HOST
    webbrowser.open_new_tab(f'http://{browser_host}:{PORT}/')

if __name__ == "__main__":
    if OPEN_BROWSER:
        threading.Timer(BROWSER_OPEN_DELAY_SECONDS, open_browser).start()
    app.run(host=HOST, port=PORT, debug=DEBUG_MODE, use_reloader=False)