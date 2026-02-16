---
title: TraceCLI — The Terminal's Black Box for Your Digital Life
published: true
tags: devchallenge, githubchallenge, cli, githubcopilot, python, productivity
cover_image: https://dev-to-uploads.s3.amazonaws.com/uploads/articles/placeholder.png
---

*This is a submission for the [GitHub Copilot CLI Challenge](https://dev.to/challenges/github-2026-01-21)*

## What I Built

**TraceCLI** is a professional-grade, privacy-first productivity monitor designed for developers who demand complete visibility into their digital life.

It runs silently in the background from the moment you log in, capturing a precise, second-by-second timeline of your workflow—applications, window titles, CPU usage, and browser history—without ever sending a single byte of data to the cloud.

Key features include:

*   **� Seamless Auto-Start**: Starts automatically with your system, ensuring every minute of your work is captured perfectly without you having to remember to run a command.
*   **�🕵️ Privacy-First Tracking**: All data is stored in a secure, local SQLite database (`~/.tracecli/trace.db`). No accounts, no cloud sync, no tracking pixels.
*   **📊 GitHub-Style Heatmap**: Visualize your long-term consistency and productivity streaks right in your terminal with `tracecli heatmap`.
*   **🎯 Focus Mode**: A Pomodoro-style timer (`tracecli focus`) with **active distraction detection**. If you switch to a distraction app (like social media or games), the CLI alerts you immediately and deducts fro your focus score.
*   **🧠 AI Insights**: Integration with Gemini/OpenAI to analyze your local data and provide personalized productivity coaching (`tracecli insights`), helping you identify burnout patterns or distraction triggers.
*   **⚡ Live Dashboard**: A beautiful, real-time TUI (Terminal User Interface) built with `Rich` that shows current app usage, CPU/RAM stats, and daily progress at a glance.

### Why I Built It
I wanted a tool that could tell me *honestly* where my time went, without manually toggling timers or trusting my data to a third-party SaaS. As a developer, I needed something that felt native to my workflow—fast, keyboard-driven, and hackable. TraceCLI solves this by being an "always-on" observer that just works.

## Demo

Here is **TraceCLI** in action:

**(Add a GIF or video here showcasing the live dashboard updates)**

### 1. The Live Dashboard (`tracecli live`)
![Live Dashboard](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/placeholder_dashboard.png)
*Real-time monitoring of active window, CPU/RAM usage, and daily progress.*

### 2. Productivity Heatmap (`tracecli heatmap`)
![Productivity Heatmap](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/placeholder_heatmap.png)
*Visualize your consistency over time—green squares indicate high productivity.*

### 3. Focus Mode with Distraction Alert (`tracecli focus`)
![Focus Mode Alert](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/placeholder_focus.png)
*Stay in flow with active monitoring. TraceCLI catches you if you tab into a distraction.*

### 4. AI Insights (`tracecli insights`)
![AI Insights](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/placeholder_insights.png)
*Weekly AI-generated productivity digests and personalized coaching tips.*

## My Experience with GitHub Copilot CLI

Building **TraceCLI** with GitHub Copilot CLI was a game-changer. It transformed the development process from writing boilerplate to collaborating with a systems expert.

Here is how it accelerated my workflow:

### 1. Complex Regex & Categorization
One of the most challenging aspects was accurately categorizing windows based on their titles (e.g., distinguishing "Google Docs - Project" from "Reddit - Chrome"). Copilot suggested robust regex patterns to identify productive vs. distracting browser tabs instantly, saving hours of manual rule creation.

### 2. Building the Rich UI
I leveraged the `Rich` library to build a premium TUI. Copilot was incredibly helpful in generating the complex layout code for the dashboard—suggesting how to nest `Panel`, `Table`, and `Layout` objects to create a responsive, professional-looking grid.

### 3. Debugging System-Level Issues
When I encountered encoding issues (`UnicodeEncodeError`) on Windows due to emoji rendering, Copilot quickly identified the root cause and suggested a clean fix that maintained cross-platform compatibility.

### 4. Heatmap Algorithm Logic
Calculating streaks and generating the logic for the contribution graph in the terminal was mathematically complex. Copilot generated the entire algorithm to map daily productivity scores to the correct grid cells, handling edge cases like leap years perfectly.

Overall, GitHub Copilot CLI allowed me to focus on building a robust, feature-rich product rather than getting bogged down in implementation details.
