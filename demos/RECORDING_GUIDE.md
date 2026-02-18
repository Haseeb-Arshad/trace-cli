# TraceCLI Demo Recording Guide

## Prerequisites

1. Make sure TraceCLI has been running for at least 2-3 hours with varied usage
   (VS Code, browser, some YouTube/Reddit for distraction data).
   If not running yet: `tracecli start --background`

2. Terminalizer is installed: `npm install -g terminalizer`

3. The custom config is at `demos/config.yml`

---

## Recording 1: Daily Report Dashboard

This is the hero shot. Shows what TraceCLI gives you after a day of tracking.

```bash
# Start recording
terminalizer record demos/demo-report -c demos/config.yml

# Once recording starts, type these commands (pause 2-3 seconds between each):
tracecli report
# Wait 3 seconds for the full output to render
# Then press Ctrl+D to stop recording

# Render to GIF
terminalizer render demos/demo-report -o demos/demo-report.gif
```

**What viewers should see:** The full dashboard panel with date, tracked time,
productive time, distraction time, top app, and the productivity score bar.

---

## Recording 2: Heatmap

The GitHub-style contribution grid. Needs multiple days of data to look impressive.

```bash
terminalizer record demos/demo-heatmap -c demos/config.yml

# Type:
tracecli heatmap --weeks 12
# Wait 3 seconds
# Ctrl+D to stop

terminalizer render demos/demo-heatmap -o demos/demo-heatmap.gif
```

**What viewers should see:** The colored grid with month labels, streak info, and legend.
If you only have a few days of data, use `--weeks 4` for a more compact grid.

---

## Recording 3: Focus Mode (The Money Shot)

This demo needs you to ACTIVELY switch apps during recording to trigger distraction alerts.

```bash
terminalizer record demos/demo-focus -c demos/config.yml

# Type:
tracecli focus 5 --goal "Write API endpoints"
# Wait for the focus UI to appear (~2 seconds)
# NOW: Alt+Tab to YouTube or Reddit in your browser
# Wait 3-4 seconds for the distraction alert to appear in the terminal
# Alt+Tab back to the terminal so the recording captures the alert
# Wait 2 more seconds
# Press Ctrl+C to end the focus session early
# The session summary will print
# Wait 3 seconds, then Ctrl+D to stop recording

terminalizer render demos/demo-focus -o demos/demo-focus.gif
```

**What viewers should see:** The focus timer counting down, then a distraction
alert popping up when you switch away, focus score dropping, and the final summary.

---

## Recording 4: AI Ask

Shows the natural language query feature. Requires an AI provider configured.

```bash
# Make sure AI is configured first:
# tracecli config --provider gemini --key YOUR_KEY

terminalizer record demos/demo-ask -c demos/config.yml

# Type:
tracecli ask "What was my most used app today and for how long?"
# Wait for the full AI response to print (5-10 seconds depending on API speed)
# Pause 3 seconds after the answer appears
# Then type another question:
tracecli ask "How productive was I compared to yesterday?"
# Wait for response
# Pause 3 seconds, then Ctrl+D

terminalizer render demos/demo-ask -o demos/demo-ask.gif
```

**What viewers should see:** The question typed, a brief thinking pause,
then a clear natural language answer with specific numbers from the database.

---

## Recording 5: Live Activity Feed

Shows real-time tracking in action. You need to switch apps WHILE recording.

```bash
terminalizer record demos/demo-live -c demos/config.yml

# Type:
tracecli live
# Now the live feed is running. Alt+Tab between apps:
#   1. Switch to VS Code (wait 3 sec)
#   2. Switch to Chrome (wait 3 sec)
#   3. Switch to File Explorer (wait 3 sec)
#   4. Switch to a different Chrome tab (wait 3 sec)
#   5. Switch back to terminal
# The feed should show 4-5 entries with categories
# Wait 2 seconds, press Ctrl+C
# Then Ctrl+D to stop recording

terminalizer render demos/demo-live -o demos/demo-live.gif
```

**What viewers should see:** Entries appearing in real-time as you switch apps,
each labeled with its category (Development, Browsing, Distraction, etc.)

---

## Post-Recording Tips

### Editing a recording before rendering
Terminalizer saves recordings as YAML. You can edit the file to:
- Remove long idle pauses (delete frames or reduce delays)
- Cut out typos or mistakes
- Adjust timing

```bash
# Open the recording file in your editor:
code demos/demo-report.yml
```

Look for `records:` in the YAML — each entry has a `delay` and `content`.
Delete entries you don't want, or change `delay` values to speed things up.

### Recommended frame edits
- Set the first frame's delay to 1000ms (1 second pause before action starts)
- Cap any delay over 3000ms down to 2000ms (keeps the GIF tight)
- The final frame should have a delay of 3000ms (let viewers read the output)

### Uploading to dev.to
1. Go to your dev.to draft
2. Drag and drop each GIF into the editor (or use the upload button)
3. dev.to will host the GIF and give you a URL like:
   `https://dev-to-uploads.s3.amazonaws.com/uploads/articles/xxxxx.gif`
4. Replace the `<!-- INSERT ... -->` placeholders in `devto.md` with these URLs

### File size warning
Terminal GIFs can get large. If a GIF exceeds 10MB:
- Reduce the recording duration (keep demos under 15 seconds)
- Lower quality in config.yml: `quality: 80`
- Use fewer cols/rows in config.yml
- Or convert to MP4 and upload as a video instead

---

## Quick Reference

| Demo | Command | Duration | Key Moment |
|------|---------|----------|------------|
| Report | `tracecli report` | ~5 sec | The full dashboard rendering |
| Heatmap | `tracecli heatmap` | ~5 sec | The colored grid appearing |
| Focus | `tracecli focus 5 --goal "..."` | ~20 sec | Distraction alert triggering |
| AI Ask | `tracecli ask "..."` | ~15 sec | AI response appearing |
| Live | `tracecli live` | ~20 sec | Entries appearing in real-time |
