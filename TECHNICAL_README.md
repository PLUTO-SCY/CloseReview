# PaperTrail Technical Notes

A local-first paper submission tracker for OpenReview workflows.

## What works now

- Local web UI at `http://127.0.0.1:8000`
- SQLite storage in `data/submissions.sqlite3`
- Manual paper and venue entry
- Account-level OpenReview sync from configured credentials
- OpenReview URL/forum import endpoint
- Overview page with compact paper cards and venue history
- Paper detail view with full submission timeline and reviews
- Submission visualization dashboard with OpenReview activity density heatmap, year filtering, month labels, monthly rhythm, outcomes, and venue ranking
- Clean review extraction that separates first official reviews from rebuttals, responses, comments, decisions, and meta-reviews
- LLM-assisted paper analysis drawer with saved chat history, paper-level summaries, and attempt-level summaries
- Paper-level submission timeline with reviews, scores, and decisions when OpenReview exposes them
- Organize mode for title changes across resubmissions:
  - rename a paper's canonical title
  - merge papers that are really the same work
  - move a single submission attempt to another paper
  - delete a submission attempt and remember it as ignored for future syncs
  - preserve old titles as aliases

## Code Layout

- `app.py`: HTTP routes and static file serving
- `db.py`: SQLite connection and schema migration
- `repository.py`: paper listing, manual edits, merge/move/delete operations
- `llm_client.py`: DeepSeek/OpenAI-compatible chat completion client
- `openreview_sync.py`: OpenReview discovery, import, review parsing, sync
- `review_cleaner.py`: cached extraction of clean official reviews for display
- `utils.py`: shared parsing, time, text, and normalization helpers
- `paths.py`: shared project paths

## Setup

```bash
cp .env.example .env.local
```

Fill in:

```bash
OPENREVIEW_USERNAME=your_openreview_email
OPENREVIEW_PASSWORD=your_openreview_password
OPENREVIEW_API_VERSION=auto
DEEPSEEK_API_KEY=your_deepseek_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro
```

Install the official OpenReview Python client when you want live imports:

```bash
pip3 install openreview-py
```

Then start the app:

```bash
python3 start.py
```

Open `http://127.0.0.1:8000`.

## Organizing Title Changes

Open the app and click `整理模式`.

- Use `Canonical title` to set the project-level title you want to see.
- Use `Merge this paper into` when two imported papers are actually the same work under different titles.
- Use `Move attempt to` when only one submission attempt belongs under another paper.
- Use `删除投稿` to remove an attempt. The app asks for confirmation and records the OpenReview ids in `ignored_attempts` so sync will not import it again.

Re-running OpenReview sync will preserve your manual organization for existing attempts.

## AI Analysis

Open a paper detail page and click `AI 分析`.

- `总结投稿历程` first summarizes each submission attempt and then synthesizes the full resubmission history, which keeps long multi-round papers within context limits.
- `总结本轮` summarizes the currently selected attempt. Opening AI analysis directly selects the newest attempt by default; clicking `总结本轮` next to a timeline item selects that specific attempt.
- `修改建议` targets the currently selected attempt and uses other attempts only as comparison context.
- Free-form chat uses the current paper's attempts, decisions, scores, and clean reviews as context.

Chat messages and generated summaries are stored in the local SQLite database.

## Notes

- `.env.local` and the SQLite database are ignored by git.
- Do not paste OpenReview credentials or LLM API keys into chat or commit them.
- Some old OpenReview venues use the legacy API, so the importer tries API 2 first and then the legacy API when `OPENREVIEW_API_VERSION=auto`.
