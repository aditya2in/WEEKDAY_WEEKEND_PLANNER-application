import os
import re
import datetime
import calendar
import webbrowser
import threading
from flask import Flask, render_template, jsonify
from collections import defaultdict

app = Flask(__name__)

MARKDOWN_FILE_PATH = os.path.join(
    os.path.dirname(__file__), "1.5 Weekend Routine BLOCKS.md"
)

def get_current_weekend():
    """Generates a list of Saturday and Sunday for the current week."""
    today = datetime.date.today()
    # Find the most recent Saturday (or today if it's Saturday)
    saturday = today + datetime.timedelta(days=(calendar.SATURDAY - today.weekday() + 7) % 7)
    # Find the Sunday immediately following that Saturday
    sunday = saturday + datetime.timedelta(days=1)

    weekends = []
    weekends.append({"date": saturday.isoformat(), "week_number": saturday.isocalendar()[1], "day_name": saturday.strftime("%A"), "full_date_display": saturday.strftime("(%A, %B %d, %Y)")})
    weekends.append({"date": sunday.isoformat(), "week_number": sunday.isocalendar()[1], "day_name": sunday.strftime("%A"), "full_date_display": sunday.strftime("(%A, %B %d, %Y)")})
    return weekends

def extract_tasks_from_markdown(file_path):
    tasks_data = {"weekly": [], "monthly": [], "table_view": {}}
    all_tag_paths = set()
    task_lines = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                if "#Task/WhatTASK/WeekendTASKgroup" in line:
                    task_lines.append(line)
                    tags_in_line = re.findall(r'#(\S+)', line)
                    for tag in tags_in_line:
                        parts = tag.split('/')
                        if len(parts) > 1:
                            tag_path = '/'.join(parts[:-1])
                            all_tag_paths.add(tag_path)

        # Custom sort key for headers
        def custom_sort_key(tag_path):
            if tag_path.startswith('Task/When'):
                # Specific order for 'When' tags
                if tag_path == 'Task/When/Weekly':
                    return (0, 0, tag_path)
                elif tag_path == 'Task/When/Whichday':
                    return (0, 1, tag_path)
                elif tag_path == 'Task/When/Monthly':
                    return (0, 2, tag_path)
                elif tag_path == 'Task/When/WhichWeek':
                    return (0, 3, tag_path)
                else:
                    return (0, 99, tag_path) # Other 'When' tags last in this group
            elif tag_path.startswith('Task/Action'):
                return (1, tag_path) # 'Task/Action' tags come second
            else:
                return (2, tag_path) # All other tags come last

        sorted_tag_paths = sorted(list(all_tag_paths), key=custom_sort_key)
        
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
            
            table_tasks.append({"name": task_name, "tag_values": task_tag_values})

            # Logic for draggable tasks (unchanged)
            weekly_match = re.search(r'#Task/When/Weekly/(\d+)X', line)
            monthly_match = re.search(r'#Task/When/Monthly/(\d+)X', line)
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
                category = "monthly"
                frequency_desc = "1X"

            tasks_data[category].append({
                "name": task_name,
                "frequency_desc": frequency_desc,
                "frequency_count": frequency_count
            })

        tasks_data["table_view"] = {
            "headers": sorted_tag_paths,
            "tasks": table_tasks
        }

    except FileNotFoundError:
        print(f"Error: Markdown file not found at {file_path}")
    except Exception as e:
        print(f"An error occurred: {e}")
    return tasks_data

@app.route("/")
def home():
    weekends = get_current_weekend()
    month_name = datetime.date.today().strftime("%B %Y")
    print(f"Weekends data sent to template: {weekends}") # Diagnostic print
    return render_template("index.html", weekends=weekends, month_name=month_name)

@app.route("/api/tasks")
def get_tasks():
    tasks = extract_tasks_from_markdown(MARKDOWN_FILE_PATH)
    return jsonify(tasks)

def open_browser():
    webbrowser.open_new_tab('http://127.0.0.1:5000/')

if __name__ == "__main__":
    threading.Timer(1, open_browser).start()
    app.run(debug=True, use_reloader=False)