import os
import datetime
import re
import argparse

def create_obsidian_daily_note(debug_mode=False):
    """
    Creates an Obsidian daily note by concatenating a default template
    and a day-specific template based on the current day.
    """
    
    # Define a consistent width for all boxes
    TARGET_BOX_WIDTH = 100 # Adjust this value as needed for your terminal

    def debug_print(message):
        if debug_mode:
            print(f"🐞 DEBUG: {message}")

    def print_box(title, items, target_width):
        """Prints an illustrative box with a title and key-value details, with text wrapping."""
        if not items:
            return

        # Calculate widths
        max_key_len = max(len(k) for k in items.keys())
        # The content width is the target_width minus key length, padding, and borders
        max_content_width = target_width - max_key_len - 7 # 7 for ' : ' + ' |' + ' |'
        if max_content_width < 10: # Ensure a minimum content width
            max_content_width = 10

        wrapped_items = []
        for key, value in items.items():
            value_str = str(value)
            # Simple wrapping: split by newline first, then wrap each part
            sub_lines = []
            for part in value_str.split('\n'):
                while len(part) > max_content_width:
                    sub_lines.append(part[:max_content_width])
                    part = part[max_content_width:]
                sub_lines.append(part)
            wrapped_items.append((key, sub_lines))

        # Top border
        print("┌" + "─" * (target_width + 2) + "┐")
        # Title
        print(f"│ {title.center(target_width)} │")
        # Separator
        print("├" + "─" * (target_width + 2) + "┤")
        # Items
        for key, lines in wrapped_items:
            # Print the key on the first line of its value
            print(f"│ {key:<{max_key_len}} : {lines[0]:<{max_content_width}} │")
            # Print subsequent lines of the value, indented
            for line_idx in range(1, len(lines)):
                print(f"│ {' '*max_key_len} : {lines[line_idx]:<{max_content_width}} │")
        # Bottom border
        print("└" + "─" * (target_width + 2) + "┘")


    print("✨ Starting the Obsidian Daily Note Creation Script ✨")
    print("-" * 50)

    # --- Configuration Paths ---
    template_folder = "/home/aditya/obsidian/All Things/Template/"
    journal_folder = "/home/aditya/obsidian/All Things/Journal/Daily Journal/"
    default_template_filename = "000 Default Day Template.md"
    
    default_template_path = os.path.join(template_folder, default_template_filename)
    debug_print(f"Default template path set to: {default_template_path}")

    # --- 1. Find and check existence of default day template ---
    print("\n🔍 Locating Template A (Default)...")
    default_template_details = {
        "File Name": default_template_filename,
        "Path": default_template_path,
    }
    if os.path.exists(default_template_path):
        default_template_details["Status"] = "✅ Found"
    else:
        default_template_details["Status"] = "❌ Not Found!"
        print_box("Default Template (A)", default_template_details, TARGET_BOX_WIDTH)
        print("\nPlease ensure the path and filename are correct.")
        return
    print_box("Default Template (A)", default_template_details, TARGET_BOX_WIDTH)

    # --- 2. Determine what day it is today ---
    today = datetime.date.today()
    day_of_week_num = today.weekday() # Monday is 0, Sunday is 6
    day_name = today.strftime("%A") # Full weekday name (e.g., Monday, Tuesday)
    
    debug_print(f"Day of week (numeric): {day_of_week_num}")

    # --- 3. Look for day-specific templates ---
    day_prefix_map = {0: "0.1", 1: "0.2", 2: "0.3", 3: "0.4", 4: "0.5", 5: "0.6", 6: "0.7"}
    today_prefix = day_prefix_map.get(day_of_week_num)
    debug_print(f"Today's prefix is: {today_prefix}")

    print(f"\n🔎 Locating Template B (Day-Specific for {day_name})...")
    day_specific_template_filename = None
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
    print_box("Day-Specific Template (B)", day_specific_details, TARGET_BOX_WIDTH)

    # --- Read Template Contents ---
    default_template_content = ""
    day_specific_template_content = ""
    try:
        with open(default_template_path, 'r') as f:
            default_template_content = f.read()
        debug_print("Successfully read default template content.")
    except Exception as e:
        print(f"🚨 Could not read default template: {e}")
        return

    if day_specific_template_path:
        try:
            with open(day_specific_template_path, 'r') as f:
                day_specific_template_content = f.read()
            debug_print("Successfully read day-specific template content.")
        except Exception as e:
            print(f"🚨 Could not read day-specific template: {e}")
            day_specific_template_content = ""

    # --- Visual Separator ---
    print("\n" + " " * 15 + "➕")
    print(" " * 10 + "Combining A and B...")
    
    # --- Concatenating Logic ---
    final_note_content = default_template_content.splitlines()
    debug_print(f"Default template has {len(final_note_content)} lines.")

    def clean_for_comparison(text):
        cleaned_text = re.sub(r'\d{1,2}:\d{2}(\s*-\s*\d{1,2}:\d{2})?', '', text)
        cleaned_text = re.sub(r'[\d:]', '', cleaned_text)
        return cleaned_text.strip()

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
                        match_details = {
                            "Search Keyword": search_keyword,
                            "Matched Line": line.strip(),
                            "Line Number": i + 1
                        }
                        print_box("Match Found", match_details, TARGET_BOX_WIDTH)
                        final_note_content[i+1:i+1] = day_specific_lines[1:]
                        inserted = True
                        break
            
            if inserted:
                # Capture lines around the insertion point
                start_line = max(0, i - 9) # 10 lines before (0-indexed)
                end_line = min(len(final_note_content), i + 11) # 10 lines after (0-indexed)
                
                # ANSI color codes
                COLOR_RESET = "\033[0m"
                COLOR_MATCHED = "\033[92m"  # Green
                COLOR_INSERTION = "\033[94m" # Blue
                COLOR_CONTEXT = "\033[90m"  # Dark Gray

                context_lines = []
                for idx in range(start_line, end_line):
                    line_num = idx + 1 # Convert to 1-indexed for display
                    prefix = "" # No special prefix for context lines
                    line_color = COLOR_CONTEXT

                    if idx == i: # The matched line
                        prefix = "MATCHED -> "
                        line_color = COLOR_MATCHED
                    elif idx == i + 1: # The line immediately after the matched line, where insertion starts
                        prefix = "INSERTION -> "
                        line_color = COLOR_INSERTION
                    
                    context_lines.append(f"{line_color}{prefix}{line_num:4d}: {final_note_content[idx].strip()}{COLOR_RESET}")

                insertion_details = {
                    "Status": "Content was inserted.",
                    "Location": f"After line {i + 1}",
                    "Matched Line": line.strip(),
                    "Search Keyword": search_keyword,
                    "Context Snippet": "\n".join(context_lines)
                }
                print_box("Insertion Report", insertion_details, TARGET_BOX_WIDTH)
            else:
                debug_print("Executing 'else' block for Insertion Report (appending content).")
                insertion_details = {
                    "Status": "No match was found.",
                    "Location": "Appended to the end of the file.",
                    "Search Keyword": cleaned_search_keyword
                }
                print_box("Insertion Report", insertion_details, TARGET_BOX_WIDTH)
                final_note_content.append("\n\n--- Day Specific Additions ---\n")
                final_note_content.extend(day_specific_lines)
    
    final_note_content_str = "\n".join(final_note_content)
    debug_print(f"Final note content length: {len(final_note_content_str)} characters.")

    # --- Create Final Note ---
    daily_note_filename = today.strftime("%Y-%m-%d") + "_TEST.md"
    daily_note_path = os.path.join(journal_folder, daily_note_filename)
    os.makedirs(journal_folder, exist_ok=True)

    print("\n")
    final_details = {
        "File Name": daily_note_filename,
        "Path": daily_note_path,
        "Content": "A + B"
    }
    print_box("Final Note (C)", final_details, TARGET_BOX_WIDTH)

    print(f"\n✍️  Writing final file...")
    try:
        with open(daily_note_path, 'w') as f:
            f.write(final_note_content_str)
        print(f"🎉 Success! Daily note created.")
        debug_print("File write operation successful.")
    except Exception as e:
        print(f"🚨 Error creating daily note: {e}")
        return

    print("\n--- Script Finished ---\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Creates an Obsidian daily note by combining templates.")
    parser.add_argument(
        "--debug",
        choices=['on', 'off'],
        default='off',
        help="Enable debug logging. Shows detailed script execution steps. Default is 'off'.",
    )
    args = parser.parse_args()
    
    debug_enabled = args.debug == 'on'
    
    create_obsidian_daily_note(debug_mode=debug_enabled)