# Weekend Planner Rules and Logic

This document describes how tasks are parsed, displayed, and enforced in the Weekend Planner app.

## Sources and Tag Families

- Primary source: a markdown file configured in `config.json` (`markdown_relative_path`).
- Weekend tasks lines are detected if they include either tag family:
  - `#Task/WhatTASK/WeekendTASKgroup` (legacy)
  - `#Task/NameAndType/WeekendTASKgroup` (current)
- For each detected line, tags are parsed into a `tag_values` map keyed by their path (e.g., `Task/WhenAndDuration/Weekly`).

## Data exposed by backend `/api/tasks`

- `table_view.headers`: unique tag paths encountered across tasks (sorted with a custom order so `Task/When/*` appear first).
- `table_view.tasks`: array of `{ name, tag_values }` for use by the master overview table.
- `weekly` and `monthly`: simplified lists of draggable tasks inferred from tags. Each has:
  - `name`
  - `frequency_desc` like `1X Weekly` or `2X Monthly`
  - `frequency_count` integer
- `history`: map of task name to occurrences in daily journals with `done` status for rule checks.

## Master Table (All Tasks Overview)

- Renders `table_view.tasks` with dynamic headers (`table_view.headers`).
- UI uses fixed layout and wraps long content to avoid horizontal scrolling.
- Column windowing: only a window of headers (default 6) is rendered at a time.
  - Controls: "◀ Columns" and "Columns ▶" shift the window without scrolling the page.

## Unscheduled Lists (Weekly and Monthly)

- Weekly unscheduled list shows tasks that are weekly-recurring:
  - Check: `Task/WhenAndDuration/Weekly` has a value (e.g., `1X`, `2X`, ...). No legacy fallback is used anymore.
  - If backend `weekly` is empty, the UI infers weekly tasks strictly from the master table rows with `Task/WhenAndDuration/Weekly` values.
- Monthly unscheduled list shows tasks that are monthly-recurring:
  - Check: `Task/WhenAndDuration/Monthly` has a value. No legacy fallback is used anymore.

## Frequencies and Counts

- Frequency descriptors are read from tags:
  - Weekly: `Task/WhenAndDuration/Weekly`, values like `1X`, `2X`, etc. If inference is needed, default to `1X Weekly`.
  - Monthly: `Task/WhenAndDuration/Monthly` with `1X`, `2X`, etc.
- When scheduling in the calendar, live counters ensure you cannot exceed the allowed count within a week or a month. Previously completed occurrences (from `history`) are considered toward limits.

## Default Duration

- Per-task default duration is read from `Task/WhenAndDuration/DefaultDuration`.
  - Supported formats: `1h30m`, `90m`, `1:30`, `2h`, `45` (minutes).
  - When dragging a task from Unscheduled to the calendar, the chip’s duration is applied by splitting into 30-minute blocks.
  - When moving a task within the calendar, the current duration is preserved; if none, the default is applied.

## Day and Week Constraints

- `Task/When/Whichday`: allowed days (Friday, Saturday, Sunday). If present, drops outside allowed days are rejected and reverted.
- `Task/When/WhichWeek`: allowed week-of-month labels (`Week1`..`Week5`). If present, drops outside allowed week labels are rejected and reverted.

## Calendar Grid

- Only hours 04:00–22:00 are shown for Saturday and Sunday.
- Each hour is a single slot with 30-minute internal step for durations.
- Chips render contiguously across slots when duration exceeds one slot, with continued segments visually merged.

## Dark Mode and Zoom

- Dark mode toggle stored in `localStorage` (`weekendDark`).
- Vertical zoom auto-fits the calendar’s height to align with the bottom of the longer unscheduled table (Monthly, else Weekly), with a manual slider for temporary adjustments.

## Process Management UI

- Shows current process info and offers quick Restart/Kill actions.
- Lists multiple running planner processes and allows killing selected PIDs.

## Backward Compatibility Notes

- The UI always prefers `Task/WhenAndDuration/*` keys when present and falls back to `Task/When/*` to support older data.
- The Weekly and Monthly unscheduled lists reflect the presence of these keys rather than only explicit text in older formats.

## Known Assumptions

- Markdown task lines use `**Task Name**` for extracting the task name.
- Frequency values are well-formed like `1X`, `2X` etc.; when parsing fails, `1X` is assumed for inferred weekly tasks.

