# CloseReview

[中文版本](README.zh-CN.md)

**CloseReview** is a local-first research workflow tool for tracking OpenReview submissions across multiple resubmission rounds. It helps researchers remember what happened to each paper: where it was submitted, how reviewers responded, why it was rejected or accepted, and what should be improved next.

## Why CloseReview?

Top-conference papers often go through several submissions before acceptance. Titles change, venues change, reviewers change, and the memory of earlier feedback fades quickly. CloseReview turns those scattered OpenReview records into an organized workspace with timelines, review summaries, activity visualizations, manual paper grouping, and AI-assisted analysis.

## Features

### Submission Overview

- Compact overview page for all tracked papers.
- Shows each paper's latest title, authors, and venue trail.
- Sorts papers by first submission time, with newer projects first.

### Paper Timeline

- Each paper has a detailed reverse-chronological submission timeline.
- Each attempt stores venue, date, title, decision, status, scores, and clean official reviews.
- Accepted submissions are visually highlighted.

### OpenReview Sync

- Sync submissions from your OpenReview account.
- Import a single OpenReview forum URL or forum id manually.
- Preserves manual organization when you sync again.

### Manual Organization

- Merge papers whose titles changed across resubmissions.
- Move a single submission attempt to another paper.
- Delete an unwanted attempt with confirmation.
- Deleted OpenReview attempts are remembered, so future syncs do not pull them back.

### Review Cleanup

- Extracts first official reviews from messy OpenReview threads.
- Separates official reviews from author responses, rebuttals, comments, decisions, and meta-reviews.

### AI Analysis

- Right-side AI drawer on each paper detail page.
- `总结本轮`: summarize the selected submission attempt.
- `修改建议`: generate revision advice for the selected attempt.
- `总结投稿历程`: first summarizes each attempt, then synthesizes the full resubmission journey to avoid long-context overflow.
- Free-form chat with paper-aware context.
- Chat history and generated summaries are stored locally.

### Activity Visualization

- GitHub-style heatmap for OpenReview activity.
- Counts submissions, reviews, comments, responses, and decisions as activities.
- Includes year filtering, month labels, monthly rhythm, outcomes, and venue ranking.

## Quick Start

### 1. Clone

```bash
git clone https://github.com/PLUTO-SCY/CloseReview.git
cd CloseReview
```

### 2. Create Environment File

```bash
cp .env.example .env.local
```

Edit `.env.local`:

```bash
OPENREVIEW_USERNAME=your_openreview_email
OPENREVIEW_PASSWORD=your_openreview_password
OPENREVIEW_API_VERSION=auto

DEEPSEEK_API_KEY=your_deepseek_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro
DEEPSEEK_REASONING_EFFORT=high
```

OpenReview sync requires your OpenReview account credentials. AI analysis requires `DEEPSEEK_API_KEY`.

### 3. Install Dependencies

The app itself uses Python standard library for the local web server and SQLite. Install the official OpenReview client if you want live OpenReview import and account sync:

```bash
pip3 install openreview-py
```

### 4. Start

```bash
python3 start.py
```

Open:

```text
http://127.0.0.1:8000
```

## Basic Workflow

1. Fill `.env.local` with your OpenReview account.
2. Start CloseReview.
3. Click `同步我的投稿` to pull your OpenReview submissions.
4. Use `整理模式` to merge papers whose titles changed across submissions.
5. Open a paper detail page to inspect the full timeline and reviews.
6. Use `AI 分析` for per-round summaries, revision advice, or full resubmission history.
7. Use `投稿可视化` to inspect activity density over time.

## Data & Privacy

- CloseReview is local-first.
- The SQLite database is stored at `data/submissions.sqlite3`.
- `.env.local` and local databases are ignored by git.
- Do not commit OpenReview credentials or LLM API keys.
- LLM features send selected paper/review context to the configured DeepSeek-compatible API.

## Technical Notes

The original technical README has been moved to [`TECHNICAL_README.md`](TECHNICAL_README.md).

## Current Status

CloseReview is an early local-first research tool built for personal paper-submission workflows. It is already useful for OpenReview-based submission tracking, but the data formats of different venues can vary. Please verify imported records before relying on them for important decisions.
