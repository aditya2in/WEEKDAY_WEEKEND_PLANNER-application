from flask import Flask, render_template, request, redirect, url_for, jsonify
import os
import datetime
import re
import io
import sys
import webbrowser
import json
import urllib.parse

app = Flask(__name__)

# Construct the absolute path to the configuration file
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, 'config.json')

DEFAULT_CONFIG = {
    "template_folder": "/home/aditya/obsidian/All Things/Template/",
    "journal_folder": "/home/aditya/obsidian/All Things/Journal/Daily Journal/",
    "default_template_filename": "000 Default Day Template.md",
    "daily_note_filename_format": "%Y-%m-%d_TEST.md"
}

def extract_name_and_tags(raw_text: str):
    """Extract hashtags from a task string and return (clean_name, tags_list).
    Tags are tokens starting with '#' and continuing until whitespace.
    """
    try:
        tag_pattern = re.compile(r"#[^\s]+")
        tags = tag_pattern.findall(raw_text)
        # Remove tags from the name and normalize spaces
        name_clean = tag_pattern.sub("", raw_text).strip()
        name_clean = re.sub(r"\s+", " ", name_clean)
        # Normalize tags to display as-is (with '#')
        return name_clean, tags
    except Exception:
        return raw_text.strip(), []

def load_config():
    """Loads the configuration from config.json."""
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            # Ensure all default keys are present in the loaded config
            for key, default_value in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = default_value
            return config
    except FileNotFoundError:
        # If the file doesn't exist, create it with default values
        with open(CONFIG_FILE, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        return DEFAULT_CONFIG

def save_config(config):
    """Saves the configuration to config.json."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def parse_default_scheduled_tasks(template_path):
    """Parse scheduled tasks from the default template for UI/preset building (times as strings)."""
    tasks = []
    if not os.path.exists(template_path):
        return tasks
    try:
        with open(template_path, 'r') as f:
            content = f.read()
        current_main_task_index = -1 # To track the index of the last main task
        for line in content.splitlines():
            # Check for main task with time range
            time_match = re.search(r"^\s*-\s*\[\s*\]\s*.*(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2}).*", line)

            if time_match:
                # This is a main task
                start_time_str = time_match.group(1).strip()
                end_time_str = time_match.group(2).strip()
                time_range = f"{start_time_str} - {end_time_str}"
                # Extract the task name by removing the time range and "- [ ]"
                task_name_raw = line.replace(time_range, "").replace("- [ ]", "").strip()

                clean_name, tags = extract_name_and_tags(task_name_raw)
                task_id = f"{clean_name}-{time_range}"
                tasks.append({
                    "id": task_id,
                    "name": clean_name,
                    "time": time_range,
                    "tags": tags,
                    "subtasks": [] # Initialize an empty list for subtasks
                })
                current_main_task_index = len(tasks) - 1
            elif current_main_task_index != -1 and (line.strip().startswith('-') or line.strip().startswith('*')) and line.startswith(' '):
                # This is a potential subtask (indented and starts with - or *)
                # A simple check for now: if it starts with a space, consider it a subtask
                tasks[current_main_task_index]["subtasks"].append(line.strip())
            else:
                # Not a main task or a subtask, reset current_main_task_index
                current_main_task_index = -1

        # Sort by start time string for stable UI ordering
        def to_minutes(t):
            try:
                h, m = map(int, t.split(':'))
                return h * 60 + m
            except Exception:
                return 99999
        tasks.sort(key=lambda t: to_minutes(t["time"].split(' - ')[0]))
    except Exception:
        return []
    return tasks

def assign_task_columns(tasks):
    # Sort tasks by start time to process them in order
    tasks.sort(key=lambda x: x["start_time"])

    # List of lists, where each inner list represents a column and contains tasks assigned to it
    columns = []

    for task in tasks:
        assigned = False
        # Try to place the task in an existing column
        for col_idx, column_tasks in enumerate(columns):
            # Check if this task overlaps with any task already in this column
            overlap = False
            for existing_task in column_tasks:
                if not (task["end_time"] <= existing_task["start_time"] or task["start_time"] >= existing_task["end_time"]):
                    overlap = True
                    break
            if not overlap:
                # No overlap, assign task to this column
                task["column"] = col_idx
                column_tasks.append(task)
                assigned = True
                break
        
        if not assigned:
            # If no suitable column found, create a new one
            task["column"] = len(columns)
            columns.append([task])
    
    # After assigning initial columns, determine total columns for each overlapping group
    # This is a simplified approach; a more robust solution would involve interval trees or similar.
    # For now, we'll just set total_columns to the max column index + 1 within any overlapping set.
    for task in tasks:
        # Find all tasks that overlap with the current task
        overlapping_group = [t for t in tasks if not (task["end_time"] <= t["start_time"] or task["start_time"] >= t["end_time"])]
        
        if overlapping_group:
            max_col_in_group = max(t["column"] for t in overlapping_group)
            for t in overlapping_group:
                t["total_columns"] = max_col_in_group + 1
        else:
            task["total_columns"] = 1 # No overlap, so it takes 1 column

        return tasks

def plan_note(debug_mode=False):
    output_buffer = io.StringIO()
    sys.stdout = output_buffer

    results = {
        "status": "",
        "general_output": "",
        "default_template_details": {},
        "day_specific_details": {},
        "insertion_report": {},
        "final_note_details": {},
        "error_message": "",
        "final_note_content_str": "",
        "running_processes": []
    }

    def get_script_processes():
        try:
            # Use a shell command to find processes related to this script
            # Exclude the grep command itself
            cmd = "ps aux | grep 'WeekDAYplannerDAILYnoteCreater.py' | grep -v grep"
            process = os.popen(cmd)
            output = process.read()
            processes = []
            for line in output.splitlines():
                parts = line.split()
                if len(parts) > 1:
                    pid = parts[1]
                    command = ' '.join(parts[10:]) # Command starts from 11th part (index 10)
                    processes.append({"pid": pid, "command": command})
            return processes
        except Exception as e:
            return [{"error": f"Failed to get processes: {e}"}]

    def assign_task_columns(tasks):
        # Sort tasks by start time to process them in order
        tasks.sort(key=lambda x: x["start_time"])

        # List of lists, where each inner list represents a column and contains tasks assigned to it
        columns = []

        for task in tasks:
            assigned = False
            # Try to place the task in an existing column
            for col_idx, column_tasks in enumerate(columns):
                # Check if this task overlaps with any task already in this column
                overlap = False
                for existing_task in column_tasks:
                    if not (task["end_time"] <= existing_task["start_time"] or task["start_time"] >= existing_task["end_time"]):
                        overlap = True
                        break
                if not overlap:
                    # No overlap, assign task to this column
                    task["column"] = col_idx
                    column_tasks.append(task)
                    assigned = True
                    break
            
            if not assigned:
                # If no suitable column found, create a new one
                task["column"] = len(columns)
                columns.append([task])
        
        # After assigning initial columns, determine total columns for each overlapping group
        # This is a simplified approach; a more robust solution would involve interval trees or similar.
        # For now, we'll just set total_columns to the max column index + 1 within any overlapping set.
        for task in tasks:
            # Find all tasks that overlap with the current task
            overlapping_group = [t for t in tasks if not (task["end_time"] <= t["start_time"] or task["start_time"] >= t["end_time"])]
            
            if overlapping_group:
                max_col_in_group = max(t["column"] for t in overlapping_group)
                for t in overlapping_group:
                    t["total_columns"] = max_col_in_group + 1
            else:
                task["total_columns"] = 1 # No overlap, so it takes 1 column

        return tasks

    # Update results with running processes
    results["running_processes"] = get_script_processes()

    # Define a consistent width for all boxes (not directly used for web UI, but kept for context)
    TARGET_BOX_WIDTH = 100

    def debug_print(message):
        print(f"🐞 DEBUG: {message}")

    print("✨ Starting the Obsidian Daily Note Creation Script ✨")
    print("-" * 50)

    # --- Configuration Paths (from config.json) ---
    config = load_config()
    template_folder = config.get("template_folder", "")
    journal_folder = config.get("journal_folder", "")
    default_template_filename = config.get("default_template_filename", "")
    daily_note_filename_format = config.get("daily_note_filename_format", "%Y-%m-%d_TEST.md")

    default_template_path = os.path.join(template_folder, default_template_filename)
    debug_print(f"Default template path set to: {default_template_path}")

    # --- 1. Find and check existence of default day template ---
    print("\n🔍 Locating Template A (Default)...")
    default_template_details = {
        "File Name": default_template_filename,
        "Path": default_template_path,
        "ScheduledTasks": [] # Initialize ScheduledTasks to an empty list
    }
    if os.path.exists(default_template_path):
        default_template_details["Status"] = "✅ Found"
        try:
            with open(default_template_path, 'r') as f:
                template_content = f.read()

            scheduled_tasks = []
            current_main_task_index = -1 # To track the index of the last main task
            for line_num, line in enumerate(template_content.splitlines(), start=1):
                # Check for main task with time range
                time_match = re.search(r"^\s*-\s*\[\s*\]\s*.*(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2}).*", line)

                if time_match:
                    # This is a main task
                    start_time_str = time_match.group(1).strip()
                    end_time_str = time_match.group(2).strip()
                    time_range = f"{start_time_str} - {end_time_str}"
                    # Extract the task name by removing the time range and "- [ ]"
                    task_name_raw = line.replace(time_range, "").replace("- [ ]", "").strip()

                    start_time_obj, end_time_obj, duration_minutes = None, None, 0
                    try:
                        start_hour, start_minute = map(int, start_time_str.split(':'))
                        end_hour, end_minute = map(int, end_time_str.split(':'))
                        start_time_obj = datetime.datetime(1, 1, 1, start_hour, start_minute)
                        end_time_obj = datetime.datetime(1, 1, 1, end_hour, end_minute)
                        duration_minutes = (end_time_obj - start_time_obj).total_seconds() / 60
                    except (ValueError, IndexError, TypeError):
                        pass

                    clean_name, tags = extract_name_and_tags(task_name_raw)
                    task_id = f"{clean_name}-{time_range}"
                    scheduled_tasks.append({
                        "id": task_id,
                        "name": clean_name,
                        "time": time_range,
                        "start_time": start_time_obj,
                        "end_time": end_time_obj,
                        "duration_minutes": duration_minutes,
                        "source": "default",
                        "tags": tags,
                        "subtasks": [], # Initialize an empty list for subtasks
                        "line_number": line_num
                    })
                    current_main_task_index = len(scheduled_tasks) - 1
                elif current_main_task_index != -1 and (line.strip().startswith('-') or line.strip().startswith('*')) and line.startswith(' '):
                    # This is a potential subtask (indented and starts with - or *)
                    # Check if it's actually indented more than the parent task
                    # A simple check for now: if it starts with a space, consider it a subtask
                    scheduled_tasks[current_main_task_index]["subtasks"].append(line.strip())
                else:
                    # Not a main task or a subtask, reset current_main_task_index
                    current_main_task_index = -1

            # Sort scheduled_tasks by start_time
            scheduled_tasks.sort(key=lambda x: x["start_time"] if x["start_time"] else datetime.datetime.max)

            # Identify tasks with parallel times and assign colors
            time_counts = {}
            for task in scheduled_tasks:
                time_counts[task["time"]] = time_counts.get(task["time"], 0) + 1

            # Define a list of colors for parallel task groups
            parallel_colors = [
                "#a8d8ff", "#ffb3ba", "#bae1ff", "#ffdfba", "#ffffba",
                "#baffc9", "#e0bbe4", "#ffb3ba", "#ffdfba", "#ffffba"
            ]
            color_index = 0
            time_color_map = {}

            for task in scheduled_tasks:
                task["is_parallel_time"] = time_counts[task["time"]] > 1
                if task["is_parallel_time"]:
                    if task["time"] not in time_color_map:
                        time_color_map[task["time"]] = parallel_colors[color_index % len(parallel_colors)]
                        color_index += 1
                    task["color"] = time_color_map[task["time"]]
                else:
                    task["color"] = None # No color for non-parallel tasks

            default_template_details["ScheduledTasks"] = scheduled_tasks
        except Exception as e:
            default_template_details["Sections"] = []
            results["error_message"] = f"Could not read or parse default template: {e}"
    else:
        default_template_details["Status"] = "❌ Not Found!"
        results["default_template_details"] = default_template_details
        results["error_message"] = "Please ensure the path and filename for the default template are correct in the configuration."
        results["status"] = "error"
        sys.stdout = sys.__stdout__ # Restore stdout
        results["general_output"] = output_buffer.getvalue()
        return results
    results["default_template_details"] = default_template_details
    # This call is not strictly necessary as the final task list is what's used, but keeping it for now
    # in case there's a use for it I'm not seeing.
    # results["default_template_calendar_tasks"] = assign_task_columns(default_template_details["ScheduledTasks"].copy())

    # --- 2. Determine what day it is today ---
    today = datetime.date.today()
    day_of_week_num = today.weekday() # Monday is 0, Sunday is 6
    day_name = today.strftime("%A") # Full weekday name (e.g., Monday, Tuesday)

    debug_print(f"Day of week (numeric): {day_of_week_num}")

    # --- 3. Look for day-specific templates ---
    print(f"\n🔎 Locating Template B (Day-Specific for {day_name})...")
    day_prefix_map = {0: "0.1", 1: "0.2", 2: "0.3", 3: "0.4", 4: "0.5", 5: "0.6", 6: "0.7"}
    today_prefix = day_prefix_map.get(day_of_week_num)
    debug_print(f"Today's prefix is: {today_prefix}")

    day_specific_template_filename = None
    if os.path.exists(template_folder):
        for filename in os.listdir(template_folder):
            if filename.startswith(today_prefix) and filename.endswith(".md"):
                day_specific_template_filename = filename
                debug_print(f"Found matching day-specific template: {filename}")
                break

    day_specific_template_path = None
    day_specific_details = {"Expected Prefix": today_prefix}
    if day_specific_template_filename:
        day_specific_template_path = os.path.join(template_folder, day_specific_template_filename)
        day_specific_details["File Name"] = day_specific_template_filename
        day_specific_details["Path"] = day_specific_template_path
        day_specific_details["Status"] = "✅ Found"
    else:
        day_specific_details["Status"] = f"❌ Not Found for {day_name}"
    results["day_specific_details"] = day_specific_details

    # --- Read Template Contents ---
    default_template_content = ""
    day_specific_template_content = ""
    try:
        with open(default_template_path, 'r') as f:
            default_template_content = f.read()
        debug_print("Successfully read default template content.")
    except Exception as e:
        results["error_message"] = f"Could not read default template: {e}"
        results["status"] = "error"
        sys.stdout = sys.__stdout__ # Restore stdout
        results["general_output"] = output_buffer.getvalue()
        return results

    if day_specific_template_path:
        try:
            with open(day_specific_template_path, 'r') as f:
                day_specific_template_content = f.read()
            debug_print("Successfully read day-specific template content.")

            # Extract scheduled tasks from day-specific template
            day_specific_scheduled_tasks = []
            current_main_task_index = -1 # To track the index of the last main task
            for line in day_specific_template_content.splitlines():
                # Check for main task with time range
                time_match = re.search(r"^\s*-\s*\[\s*\]\s*.*(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2}).*", line)

                if time_match:
                    # This is a main task
                    start_time_str = time_match.group(1).strip()
                    end_time_str = time_match.group(2).strip()
                    time_range = f"{start_time_str} - {end_time_str}"
                    # Extract the task name by removing the time range and "- [ ]"
                    task_name_raw = line.replace(time_range, "").replace("- [ ]", "").strip()

                    start_time_obj, end_time_obj, duration_minutes = None, None, 0
                    try:
                        start_hour, start_minute = map(int, start_time_str.split(':'))
                        end_hour, end_minute = map(int, end_time_str.split(':'))
                        start_time_obj = datetime.datetime(1, 1, 1, start_hour, start_minute)
                        end_time_obj = datetime.datetime(1, 1, 1, end_hour, end_minute)
                        duration_minutes = (end_time_obj - start_time_obj).total_seconds() / 60
                    except (ValueError, IndexError, TypeError):
                        pass

                    clean_name, tags = extract_name_and_tags(task_name_raw)
                    task_id = f"{clean_name}-{time_range}"
                    day_specific_scheduled_tasks.append({
                        "id": task_id,
                        "name": clean_name,
                        "time": time_range,
                        "start_time": start_time_obj,
                        "end_time": end_time_obj,
                        "duration_minutes": duration_minutes,
                        "source": "day_specific",
                        "tags": tags,
                        "subtasks": [] # Initialize an empty list for subtasks
                    })
                    current_main_task_index = len(day_specific_scheduled_tasks) - 1
                elif current_main_task_index != -1 and (line.strip().startswith('-') or line.strip().startswith('*')) and line.startswith(' '):
                    # This is a potential subtask (indented and starts with - or *)
                    # Check if it's actually indented more than the parent task
                    # A simple check for now: if it starts with a space, consider it a subtask
                    day_specific_scheduled_tasks[current_main_task_index]["subtasks"].append(line.strip())
                else:
                    # Not a main task or a subtask, reset current_main_task_index
                    current_main_task_index = -1
            day_specific_details["ScheduledTasks"] = day_specific_scheduled_tasks

        except Exception as e:
            results["error_message"] = f"Could not read day-specific template: {e}"
            results["status"] = "error"
            day_specific_template_content = ""
            # Don't return here, try to proceed with only default content

    # --- Visual Separator ---
    print("\n" + " " * 15 + "➕")
    print(" " * 10 + "Combining A and B...")

    # --- Concatenating Logic ---
    final_note_content = default_template_content.splitlines()
    inserted_line_numbers_for_preview = []  # 1-based line numbers in preview content
    debug_print(f"Default template has {len(final_note_content)} lines.")

    def clean_for_comparison(text):
        cleaned_text = re.sub(r'\d{1,2}:\d{2}(\s*-\s*\d{1,2}:\d{2})?', '', text)
        cleaned_text = re.sub(r'[\d:]', '', cleaned_text)
        return cleaned_text.strip()

    insertion_details = {"Context Snippet": ""}
    if day_specific_template_content:
        day_specific_lines = day_specific_template_content.splitlines()
        debug_print(f"Day-specific template has {len(day_specific_lines)} lines.")

        if day_specific_lines:
            search_keyword = day_specific_lines[0]
            cleaned_search_keyword = clean_for_comparison(search_keyword)
            inserted = False
            if cleaned_search_keyword:
                for i, line in enumerate(final_note_content):
                    cleaned_line = clean_for_comparison(line)
                    if cleaned_line and cleaned_line == cleaned_search_keyword:
                        insertion_details["Search Keyword"] = search_keyword
                        insertion_details["Matched Line"] = line.strip()
                        insertion_details["Line Number"] = i + 1
                        # Insert all lines from the day-specific template except the first header line
                        final_note_content[i+1:i+1] = day_specific_lines[1:]
                        # Track inserted line numbers for preview highlighting (1-based)
                        insert_start = i + 1  # 0-based index of first inserted line
                        insert_len = max(0, len(day_specific_lines) - 1)
                        inserted_line_numbers_for_preview = [n + 1 for n in range(insert_start, insert_start + insert_len)]
                        inserted = True
                        break

            if inserted:
                insertion_details["Status"] = "Content was inserted."
                insertion_details["Location"] = f"After line {i + 1}"
                # Context snippet for web display (expanded)
                start_line = max(0, i - 10)
                end_line = min(len(final_note_content), i + 11)
                context_lines = []
                for idx, line in enumerate(final_note_content[start_line:end_line]):
                    original_line_num = start_line + idx + 1
                    prefix = "--> " if "Matched Line" in insertion_details and line.strip() == insertion_details["Matched Line"].strip() else ""
                    context_lines.append(f"{original_line_num:4d}: {prefix}{line}")
                insertion_details["Context Snippet"] = "\n".join(context_lines)
            else:
                debug_print("Executing 'else' block for Insertion Report (appending content).")
                insertion_details["Status"] = "No match was found."
                insertion_details["Location"] = "Appended to the end of the file."
                insertion_details["Search Keyword"] = cleaned_search_keyword
                insertion_details["Context Snippet"] = "No specific insertion context available (content appended)."
                # Append a clear single-line marker, then the day-specific lines
                # Avoid embedding newlines inside a single list element so line numbers are accurate
                final_note_content.append("")
                final_note_content.append("--- Day Specific Additions ---")
                final_note_content.append("")
                append_start_idx = len(final_note_content)  # index where day-specific lines will start
                final_note_content.extend(day_specific_lines)
                # Compute inserted line numbers for preview (marker + blank lines + appended day-specific lines)
                # We'll highlight only the day-specific lines (not the blank lines), and the marker for clarity
                # Build a temporary joined view to count lines accurately
                joined = "\n".join(final_note_content)
                all_lines = joined.splitlines()
                # Find the marker line index (0-based) in the splitlines view
                try:
                    marker_idx = next(idx for idx, ln in enumerate(all_lines) if ln.strip() == "--- Day Specific Additions ---")
                except StopIteration:
                    marker_idx = None
                if marker_idx is not None:
                    # Highlight marker and all following lines that came from day-specific content
                    inserted_line_numbers_for_preview = list(range(marker_idx + 1, len(all_lines) + 1))
    results["insertion_report"] = insertion_details

    final_note_content_str = "\n".join(final_note_content)
    debug_print(f"Final note content length: {len(final_note_content_str)} characters.")
    results["final_note_inserted_line_numbers"] = inserted_line_numbers_for_preview

    # --- Combine, Sort, and Process All Scheduled Tasks ---
    # No preset filtering: include all default tasks; day-specific tasks are additions
    default_tasks_all = default_template_details.get("ScheduledTasks", [])
    parsed_calendar_tasks = default_tasks_all + day_specific_details.get("ScheduledTasks", [])

    # Sort tasks by start time
    parsed_calendar_tasks.sort(key=lambda x: x["start_time"] if x["start_time"] else datetime.datetime.max)

    # Identify tasks with parallel times and assign colors
    time_counts = {}
    for task in parsed_calendar_tasks:
        time_counts[task["time"]] = time_counts.get(task["time"], 0) + 1

    # Define a list of colors for parallel task groups
    parallel_colors = [
        "#a8d8ff", "#ffb3ba", "#bae1ff", "#ffdfba", "#ffffba",
        "#baffc9", "#e0bbe4", "#ffb3ba", "#ffdfba", "#ffffba"
    ]
    color_index = 0
    time_color_map = {}

    for task in parsed_calendar_tasks:
        task["is_parallel_time"] = time_counts[task["time"]] > 1
        if task["is_parallel_time"]:
            if task["time"] not in time_color_map:
                time_color_map[task["time"]] = parallel_colors[color_index % len(parallel_colors)]
                color_index += 1
            task["color"] = time_color_map[task["time"]]
        else:
            task["color"] = None # No color for non-parallel tasks

    parsed_calendar_tasks = assign_task_columns(parsed_calendar_tasks)
    results["parsed_calendar_tasks"] = parsed_calendar_tasks

    debug_print("--- Parsed Calendar Tasks Debug ---")
    for task in results["parsed_calendar_tasks"]:
        debug_print(f"Task: {task['name']} ({task['time']})")
        debug_print(f"  Start Time: {task['start_time']}")
        debug_print(f"  End Time: {task['end_time']}")
        debug_print(f"  Duration (minutes): {task['duration_minutes']}")
        debug_print(f"  Column: {task.get('column', 'N/A')}")
        debug_print(f"  Total Columns: {task.get('total_columns', 'N/A')}")
        debug_print(f"  Is Parallel Time: {task.get('is_parallel_time', False)}")
    debug_print("-----------------------------------")

    # --- Create Final Note ---
    daily_note_filename = today.strftime(daily_note_filename_format)
    daily_note_path = os.path.join(journal_folder, daily_note_filename)
    os.makedirs(journal_folder, exist_ok=True)

    final_note_details = {
        "File Name": daily_note_filename,
        "Path": daily_note_path,
        "Content": "A + B"
    }
    results["final_note_details"] = final_note_details
    results["final_note_content_str"] = final_note_content_str

    print("✅ Planning complete. Review the details below.")
    results["status"] = "success"

    print("\n--- Script Finished ---\n")
    sys.stdout = sys.__stdout__ # Restore stdout
    results["general_output"] = output_buffer.getvalue()
    print(f"DEBUG: Final General Output:\n{results['general_output']}") # Added debug print
    return results


PIXELS_PER_MINUTE = 1 # Define a global constant for the calendar scale

@app.route('/')
def index():
    config = load_config()
    message = request.args.get('message') # Get message from query parameter

    # Check if today's daily note exists
    config = load_config()
    journal_folder = config.get("journal_folder", "")
    daily_note_filename_format = config.get("daily_note_filename_format", "%Y-%m-%d_TEST.md")
    today = datetime.date.today()
    daily_note_filename = today.strftime(daily_note_filename_format)
    daily_note_path = os.path.join(journal_folder, daily_note_filename)
    daily_note_exists = os.path.exists(daily_note_path)

    # Build default tasks list for UI toggles
    default_template_path = os.path.join(config.get("template_folder", ""), config.get("default_template_filename", ""))
    default_tasks_for_ui = parse_default_scheduled_tasks(default_template_path)
    return render_template('index.html', config=config, results=None, message=message, daily_note_exists=daily_note_exists, pixels_per_minute=PIXELS_PER_MINUTE, default_tasks_for_ui=default_tasks_for_ui)

@app.route('/plan_note', methods=['POST'])
def plan_note_route():
    config = load_config()
    results = plan_note(debug_mode=True)
    daily_note_path = results.get('final_note_details', {}).get('Path')
    daily_note_exists = os.path.exists(daily_note_path) if daily_note_path else False
    # Build default tasks list for UI toggles
    default_template_path = os.path.join(config.get("template_folder", ""), config.get("default_template_filename", ""))
    default_tasks_for_ui = parse_default_scheduled_tasks(default_template_path)
    return render_template('index.html', config=config, results=results, daily_note_exists=daily_note_exists, pixels_per_minute=PIXELS_PER_MINUTE, default_tasks_for_ui=default_tasks_for_ui)

def generate_markdown_from_tasks(tasks, original_content):
    """Generates a new markdown string from a list of task objects, including subtasks."""

    generated_task_lines = []
    for task in tasks:
        # Main task line
        # Ensure start_time and end_time are strings for formatting
        start_time_str = task['start_time'].strftime('%H:%M') if isinstance(task['start_time'], datetime.datetime) else task['time'].split(' - ')[0]
        end_time_str = task['end_time'].strftime('%H:%M') if isinstance(task['end_time'], datetime.datetime) else task['time'].split(' - ')[1]

        time_range = f"{start_time_str} - {end_time_str}"
        generated_task_lines.append(f"- [ ] {task['name']} {time_range}")

        # Add subtasks with indentation
        for subtask_line in task.get('subtasks', []):
            # Preserve original indentation of subtask if it exists, otherwise add 4 spaces
            if subtask_line.startswith(' '):
                generated_task_lines.append(subtask_line)
            else:
                generated_task_lines.append(f"    {subtask_line}") # Default indentation

    # Find insertion point in original_content
    original_lines = original_content.splitlines()

    # 1) Priority: insert under an existing schedule header (accept common variants)
    def is_schedule_header(text: str) -> bool:
        if not isinstance(text, str):
            return False
        stripped = text.strip()
        if not stripped.startswith('#'):
            return False
        # Only consider level 2 or 3 headers for placement
        if not (stripped.startswith('##') or stripped.startswith('###')):
            return False
        # Normalize header content
        header_text = stripped.lstrip('#').strip().lower()
        # Accept common variants
        accepted = {
            'schedule',
            'daily plan',
            'daily schedule',
            'day planner',
            'daily planner',
        }
        return header_text in accepted

    insertion_point = -1
    schedule_header_found = False
    for i, line in enumerate(original_lines):
        if is_schedule_header(line):
            insertion_point = i + 1
            schedule_header_found = True
            break

    if schedule_header_found:
        # Replace existing content under the header up to the next header
        end_of_schedule_section = len(original_lines)
        for j in range(insertion_point, len(original_lines)):
            if original_lines[j].strip().startswith('#'):
                end_of_schedule_section = j
                break
        final_content_lines = original_lines[:insertion_point] + generated_task_lines + original_lines[end_of_schedule_section:]
        return "\n".join(final_content_lines)

    # 2) Else: replace the first detected time-block of checklist tasks (with subtasks)
    time_task_re = re.compile(r"^\s*-\s*\[\s*\]\s*.*\b\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}\b")
    def is_main_time_task_line(text: str) -> bool:
        return bool(time_task_re.search(text or ""))

    def is_indented_bullet(text: str) -> bool:
        if not text:
            return False
        # Indented list items like "    - something" or "    * something"
        return bool(re.match(r"^\s+[-*]\s+", text))

    start_idx = -1
    for i, line in enumerate(original_lines):
        if is_main_time_task_line(line):
            start_idx = i
            break

    if start_idx != -1:
        end_idx = start_idx + 1
        while end_idx < len(original_lines):
            cur = original_lines[end_idx]
            if cur.strip().startswith('#'):
                break
            if cur.strip() == "":
                end_idx += 1
                continue
            if is_main_time_task_line(cur) or is_indented_bullet(cur):
                end_idx += 1
                continue
            # Any other non-blank, non-subtask, non-time-task line ends the block
            break
        final_content_lines = original_lines[:start_idx] + generated_task_lines + original_lines[end_idx:]
        return "\n".join(final_content_lines)

    # 3) Else: insert at end with no heading
    if original_lines and original_lines[-1].strip() != "":
        final_content_lines = original_lines + [""] + generated_task_lines
    else:
        final_content_lines = original_lines + generated_task_lines

    return "\n".join(final_content_lines)


def remove_excluded_tasks_from_content(original_content: str, all_tasks: list, excluded_ids: set) -> str:
    """Remove lines for excluded tasks (and their indented subtasks) from the original content.
    A task line is identified by presence of '- [ ]', the cleaned task name, and its time range.
    Subsequent indented bullet lines are treated as subtasks and removed together.
    """
    if not original_content or not excluded_ids:
        return original_content

    # Build quick lookup of tasks to remove by id
    tasks_by_id = {t.get('id'): t for t in all_tasks if t.get('id') in excluded_ids}

    lines = original_content.splitlines()
    new_lines = []
    i = 0

    def leading_spaces(s: str) -> int:
        # Treat tabs as 4 spaces for indentation calculation
        count = 0
        for ch in s:
            if ch == ' ':
                count += 1
            elif ch == '\t':
                count += 4
            else:
                break
        return count

    while i < len(lines):
        line = lines[i]

        def is_main_task_line_for(task, text: str) -> bool:
            if not task:
                return False
            # Expect a checklist bullet line
            if '- [ ]' not in text:
                return False
            # Match by name and explicit time range tokens
            name = task.get('name') or ''
            time_range = task.get('time') or ''
            if not name or not time_range:
                return False
            try:
                start_tok, end_tok = [s.strip() for s in time_range.split('-')]
            except Exception:
                return False
            return (name in text) and (start_tok in text) and (end_tok in text)

        matched_task_id = None
        for tid, task in tasks_by_id.items():
            if is_main_task_line_for(task, line):
                matched_task_id = tid
                break

        if matched_task_id:
            # Compute base indentation of the matched main task line
            base_indent = leading_spaces(line)
            # Skip the main task line itself
            i += 1
            # Skip all following lines that are more indented than the main line
            while i < len(lines):
                nxt = lines[i]
                # Always remove blank lines immediately following within the block
                if nxt.strip() == '':
                    i += 1
                    continue
                if leading_spaces(nxt) > base_indent:
                    i += 1
                    continue
                # Reached next task or higher/equal indentation level -> stop
                break
            continue  # Do not add removed lines
        else:
            new_lines.append(line)
            i += 1

    return "\n".join(new_lines)

@app.route('/create_note', methods=['POST'])
def create_note_route():
    # Re-plan to get full tasks (including subtasks) then honor client plan
    results = plan_note(debug_mode=False)
    all_tasks = results.get('parsed_calendar_tasks', [])

    data = request.get_json(silent=True) or {}
    original_content = data.get('original_content')
    removed_ids = set(data.get('removed_ids') or [])
    # Simplified flow per user intent: ignore overrides and mode; just delete red (removed) blocks
    overrides = {}
    mode = None

    if not all_tasks or not original_content:
        return jsonify({"status": "error", "message": "Missing tasks or original content."}), 400

    # No filtering/overrides. We'll only remove the selected (red) blocks from the provided Planned Final Note (C) content.

    config = load_config()
    journal_folder = config.get("journal_folder", "")
    daily_note_filename_format = config.get("daily_note_filename_format", "%Y-%m-%d_TEST.md")

    today = datetime.date.today()
    daily_note_filename = today.strftime(daily_note_filename_format)
    daily_note_path = os.path.join(journal_folder, daily_note_filename)
    os.makedirs(journal_folder, exist_ok=True)

    # Expose removed defaults for UI highlighting in A table (optional)
    results['removed_default_ids'] = list(removed_ids)

    # Remove only the selected (red) tasks and their subtasks from the provided Planned Final Note (C)
    cleaned_original_content = remove_excluded_tasks_from_content(original_content, all_tasks, removed_ids)
    final_note_content_str = cleaned_original_content

    try:
        with open(daily_note_path, 'w') as f:
            f.write(final_note_content_str)

        # Attempt to open in Obsidian (best effort)
        try:
            encoded_path = urllib.parse.quote(daily_note_path)
            obsidian_uri = f"obsidian://open?path={encoded_path}"
            webbrowser.open(obsidian_uri)
        except Exception as e:
            print(f"DEBUG: Error opening Obsidian URI: {e}")

        return jsonify({"status": "success", "message": f"Daily note created at {daily_note_path}"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error creating daily note: {e}"}), 500

@app.route('/save_config', methods=['POST'])
def save_config_route():
    new_config = {
        "template_folder": request.form.get('template_folder'),
        "journal_folder": request.form.get('journal_folder'),
        "default_template_filename": request.form.get('default_template_filename'),
        "daily_note_filename_format": request.form.get('daily_note_filename_format')
    }
    save_config(new_config)
    return redirect(url_for('index'))

@app.route('/delete_note', methods=['POST'])
def delete_note_route():
    config = load_config()
    journal_folder = config.get("journal_folder", "")
    daily_note_filename_format = config.get("daily_note_filename_format", "%Y-%m-%d_TEST.md")

    today = datetime.date.today()
    daily_note_filename = today.strftime(daily_note_filename_format)
    daily_note_path = os.path.join(journal_folder, daily_note_filename)

    message = ""
    if os.path.exists(daily_note_path):
        try:
            os.remove(daily_note_path)
            message = f"✅ Successfully deleted: {daily_note_filename}"
        except Exception as e:
            message = f"❌ Error deleting note: {e}"
    else:
        message = f"ℹ️ Daily note not found: {daily_note_filename}"
    
    # For simplicity, we'll pass the message via query parameter. 
    # In a real app, you might use Flask's flash messages.
    return redirect(url_for('index', message=message))

    return redirect(url_for('index', message=message))



@app.route('/kill_processes', methods=['POST'])
def kill_processes_route():
    pids_to_kill = request.form.getlist('pid')
    message = ""
    killed_count = 0
    for pid_str in pids_to_kill:
        try:
            pid = int(pid_str)
            os.kill(pid, 9)  # SIGKILL
            killed_count += 1
        except ValueError:
            message += f"Invalid PID: {pid_str}. "
        except ProcessLookupError:
            message += f"Process {pid_str} not found. "
        except Exception as e:
            message += f"Error killing process {pid_str}: {e}. "
    
    if killed_count > 0:
        message = f"✅ Successfully killed {killed_count} process(es). " + message
    elif not message:
        message = "ℹ️ No processes selected to kill."

    return redirect(url_for('index', message=message))

import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Obsidian Daily Note Planner.')
    parser.add_argument('--plan-only', action='store_true', help='Run planning function and print output, then exit.')
    args = parser.parse_args()

    if args.plan_only:
        results = plan_note(debug_mode=True)
        print(results['general_output'])
    else:
        # webbrowser.open('http://127.0.0.1:5000/')
        app.run(debug=True, host='0.0.0.0')