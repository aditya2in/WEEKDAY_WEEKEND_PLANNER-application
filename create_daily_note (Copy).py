import os
import datetime
import re
import argparse

def create_obsidian_daily_note(debug_mode=False):
    """
    Creates an Obsidian daily note by concatenating a default template
    and a day-specific template based on the current day.
    """
    
    def debug_print(message):
        if debug_mode:
            print(f"🐞 DEBUG: {message}")

    print("✨ Starting the Obsidian Daily Note Creation Script ✨")
    print("-" * 50)

    # --- Configuration Paths ---
    template_folder = "/home/aditya/obsidian/All Things/Template/"
    journal_folder = "/home/aditya/obsidian/All Things/Journal/Daily Journal/"
    default_template_filename = "000 Default Day Template.md"
    
    default_template_path = os.path.join(template_folder, default_template_filename)
    debug_print(f"Default template path set to: {default_template_path}")


    # --- 1. Find and check existence of default day template ---
    print(f"🔍 Checking for default template:")
    print(f"   - File Name: {default_template_filename}")
    print(f"   - Path: {default_template_path}")
    if os.path.exists(default_template_path):
        print("   - Status: ✅ Exists")
    else:
        print(f"   - Status: ❌ Not Found!")
        print("Please ensure the path and filename are correct.")
        return

    # --- 2. Determine what day it is today ---
    today = datetime.date.today()
    day_of_week_num = today.weekday() # Monday is 0, Sunday is 6
    day_name = today.strftime("%A") # Full weekday name (e.g., Monday, Tuesday)
    
    print(f"\n🗓️ Today is {day_name} ({today.strftime('%Y-%m-%d')}).")
    debug_print(f"Day of week (numeric): {day_of_week_num}")


    # --- 3. Look for day-specific templates ---
    # Mapping for day prefixes
    day_prefix_map = {
        0: "0.1", # Monday
        1: "0.2", # Tuesday
        2: "0.3", # Wednesday
        3: "0.4", # Thursday
        4: "0.5", # Friday
        5: "0.6", # Saturday
        6: "0.7"  # Sunday
    }
    
    # Get the numeric prefix for today
    today_prefix = day_prefix_map.get(day_of_week_num)
    debug_print(f"Today's prefix is: {today_prefix}")

    
    # Search for day-specific template that starts with today_prefix
    day_specific_template_filename = None
    print(f"\n🔎 Searching for day-specific template in '{template_folder}' for today's prefix '{today_prefix}'...")
    
    for filename in os.listdir(template_folder):
        if filename.startswith(today_prefix) and filename.endswith(".md"):
            day_specific_template_filename = filename
            debug_print(f"Found matching day-specific template: {filename}")
            break # Found the first matching file, assume it's the correct one

    day_specific_template_path = None
    print(f"   - Expected Prefix: {today_prefix}")
    if day_specific_template_filename:
        day_specific_template_path = os.path.join(template_folder, day_specific_template_filename)
        print(f"   - File Name: {day_specific_template_filename}")
        print(f"   - Path: {day_specific_template_path}")
        print(f"   - Status: ✅ Exists")
        debug_print(f"Day-specific template path: {day_specific_template_path}")
    else:
        print(f"   - Status: ❌ Not Found for {day_name} starting with '{today_prefix}'.")
        print("The daily note will be created using only the default template (or appending if day-specific content is manually provided later).")

    # --- Read Template Contents (for internal use, not displayed) ---
    default_template_content = ""
    day_specific_template_content = ""

    # Read Default Template Content
    try:
        with open(default_template_path, 'r') as f:
            default_template_content = f.read()
        debug_print("Successfully read default template content.")
    except Exception as e:
        print(f"🚨 Could not read default template for processing: {e}")
        return

    # Read Day-Specific Template Content (if found)
    if day_specific_template_path:
        try:
            with open(day_specific_template_path, 'r') as f:
                day_specific_template_content = f.read()
            debug_print("Successfully read day-specific template content.")
        except Exception as e:
            print(f"🚨 Could not read day-specific template for processing: {e}")
            # Continue without day-specific content if it fails to read
            day_specific_template_content = ""
    
    # --- Concatenating Logic ---
    final_note_content = default_template_content.splitlines()
    debug_print(f"Default template has {len(final_note_content)} lines.")

    def clean_for_comparison(text):
        """Removes time-like patterns and extra characters for robust comparison."""
        # Remove time patterns like HH:MM or HH:MM - HH:MM
        cleaned_text = re.sub(r'\d{1,2}:\d{2}(\s*-\s*\d{1,2}:\d{2})?', '', text)
        # Remove any remaining digits and colons, then strip whitespace
        cleaned_text = re.sub(r'[\d:]', '', cleaned_text)
        return cleaned_text.strip()

    def print_summary_box(title, content):
        """Prints a formatted box with a title and content."""
        print("\n" + "+" + "-" * (len(title) + 2) + "+")
        print(f"| {title.upper()} |")
        print("+" + "-" * (len(title) + 2) + "+")
        for key, value in content.items():
            print(f"  {key}: {value}")
        print("\n")

    if day_specific_template_content:
        day_specific_lines = day_specific_template_content.splitlines()
        debug_print(f"Day-specific template has {len(day_specific_lines)} lines.")

        if day_specific_lines:
            search_keyword = day_specific_lines[0]
            cleaned_search_keyword = clean_for_comparison(search_keyword)
            debug_print(f"Using cleaned search keyword: '{cleaned_search_keyword}'")

            inserted = False
            if cleaned_search_keyword:
                for i, line in enumerate(final_note_content):
                    cleaned_line = clean_for_comparison(line)
                    debug_print(f"Comparing cleaned line {i+1}: '{cleaned_line}' with '{cleaned_search_keyword}'")

                    if cleaned_line and cleaned_line == cleaned_search_keyword:
                        summary = {
                            "Search Keyword": search_keyword,
                            "Matched Line": line.strip(),
                            "Line Number": i + 1
                        }
                        print_summary_box("Match Found", summary)

                        # Insert the day-specific content (minus the keyword line) after the matched line
                        final_note_content[i+1:i+1] = day_specific_lines[1:]
                        
                        inserted = True
                        break
            
            if inserted:
                summary = {
                    "Status": "Content was inserted at the matched line."
                }
                print_summary_box("Insertion Report", summary)
            else:
                summary = {
                    "Status": "No match was found. Content has been appended to the end of the file.",
                    "Search Keyword": cleaned_search_keyword
                }
                print_summary_box("Insertion Report", summary)
                debug_print("Appending day-specific content as no keyword match was found.")
                final_note_content.append("\n\n--- Day Specific Additions ---")
                final_note_content.extend(day_specific_lines)
        else:
            print("   - Day-specific template is empty, skipping concatenation.")
            debug_print("Day-specific template file was found but it is empty.")
    else:
        print("   - No day-specific template content to concatenate.")
        debug_print("No day-specific template file was found.")


    # Join the lines back into a single string
    final_note_content_str = "\n".join(final_note_content)
    debug_print(f"Final note content length: {len(final_note_content_str)} characters.")


    # --- Create daily note in format yyyy-mm-dd_TEST in Journal folder ---
    daily_note_filename = today.strftime("%Y-%m-%d") + "_TEST.md"
    daily_note_path = os.path.join(journal_folder, daily_note_filename)

    # Ensure the journal directory exists
    os.makedirs(journal_folder, exist_ok=True)

    print(f"\n✍️ Creating daily note at:")
    print(f"   - File Name: {daily_note_filename}")
    print(f"   - Path: {daily_note_path}")
    try:
        with open(daily_note_path, 'w') as f:
            f.write(final_note_content_str)
        print(f"🎉 Success! Daily note created.")
        debug_print("File write operation successful.")
    except Exception as e:
        print(f"🚨 Error creating daily note: {e}")
        return

    print("\n--- Script Finished ---")

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
