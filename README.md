# CloseReview

**CloseReview** is a local-first research workflow tool for tracking OpenReview submissions across multiple resubmission rounds. It helps researchers remember what happened to each paper: where it was submitted, how reviewers responded, why it was rejected or accepted, and what should be improved next.

**CloseReview** 是一个本地优先的论文投稿管理工具，面向经常使用 OpenReview 投稿的研究者。它帮助你追踪一篇论文从初投稿、被拒、改投、再审到最终录用的完整过程，避免遗忘历史版本、审稿意见、分数和决策。

## Why CloseReview?

Top-conference papers often go through several submissions before acceptance. Titles change, venues change, reviewers change, and the memory of earlier feedback fades quickly. CloseReview turns those scattered OpenReview records into an organized workspace with timelines, review summaries, activity visualizations, manual paper grouping, and AI-assisted analysis.

顶会论文往往需要多次转投。标题可能改、会议可能变、审稿意见也分散在不同 OpenReview 页面中。CloseReview 会把这些零散记录整理成一个可浏览、可合并、可分析的论文工作台：时间线、审稿意见、投稿密度可视化、手动归类和 AI 分析都在一个地方。

## Features / 功能

### Submission Overview / 投稿总览

- Compact overview page for all tracked papers.
- Shows each paper's latest title, authors, and venue trail.
- Sorts papers by first submission time, with newer projects first.

- 总览页展示所有论文项目。
- 每篇论文显示最新标题、作者和投稿会议轨迹。
- 按首次投稿时间排序，最新项目在上。

### Paper Timeline / 论文时间线

- Each paper has a detailed reverse-chronological submission timeline.
- Each attempt stores venue, date, title, decision, status, scores, and clean official reviews.
- Accepted submissions are visually highlighted.

- 每篇论文都有独立详情页，按时间倒序展示投稿轮次。
- 每次投稿记录会议、日期、标题、decision、状态、分数和清理后的官方 review。
- 被录用的投稿会被特别高亮。

### OpenReview Sync / OpenReview 同步

- Sync submissions from your OpenReview account.
- Import a single OpenReview forum URL or forum id manually.
- Preserves manual organization when you sync again.

- 支持从 OpenReview 账号同步投稿记录。
- 支持手动导入单篇 OpenReview 链接或 forum id。
- 后续再次同步时，会保留你手动整理过的归类结果。

### Manual Organization / 手动归类

- Merge papers whose titles changed across resubmissions.
- Move a single submission attempt to another paper.
- Delete an unwanted attempt with confirmation.
- Deleted OpenReview attempts are remembered, so future syncs do not pull them back.

- 可以把“标题不同但其实是同一篇工作”的论文合并到一起。
- 可以把某一次投稿移动到另一篇论文下。
- 可以手动删除某次投稿，并进行二次确认。
- 删除记录会写入忽略列表，避免以后同步时又被拉回来。

### Review Cleanup / Review 清理

- Extracts first official reviews from messy OpenReview threads.
- Separates official reviews from author responses, rebuttals, comments, decisions, and meta-reviews.

- 从复杂的 OpenReview 数据中提取正式审稿意见。
- 尽量排除 author response、rebuttal、comment、decision 和 meta-review，让 review 展示更干净。

### AI Analysis / AI 分析

- Right-side AI drawer on each paper detail page.
- `总结本轮`: summarize the selected submission attempt.
- `修改建议`: generate revision advice for the selected attempt.
- `总结投稿历程`: first summarizes each attempt, then synthesizes the full resubmission journey to avoid long-context overflow.
- Free-form chat with paper-aware context.
- Chat history and generated summaries are stored locally.

- 每篇论文详情页都有右侧 `AI 分析`抽屉。
- `总结本轮`：只总结当前选中的投稿轮次。
- `修改建议`：只针对当前轮次给出修改建议。
- `总结投稿历程`：先对每轮投稿做摘要，再综合生成完整转投历程，避免上下文过长。
- 支持自由问答，AI 会基于当前论文的投稿、decision、分数和 review 作答。
- 聊天记录和 AI 摘要都会保存在本地数据库。

### Activity Visualization / 活动可视化

- GitHub-style heatmap for OpenReview activity.
- Counts submissions, reviews, comments, responses, and decisions as activities.
- Includes year filtering, month labels, monthly rhythm, outcomes, and venue ranking.

- 类似 GitHub contributions 的活动热力图。
- 不只统计投稿，也统计 review、comment、response、decision 等 OpenReview 活动。
- 支持年份筛选、月份标签、月度节奏、结果统计和会议排名。

## Quick Start / 快速开始

### 1. Clone / 下载

```bash
git clone https://github.com/PLUTO-SCY/CloseReview.git
cd CloseReview
```

### 2. Create Environment File / 创建环境配置

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

编辑 `.env.local`，填入你的 OpenReview 登录邮箱、密码，以及可选的 DeepSeek API key。OpenReview 同步需要账号密码；AI 分析需要 `DEEPSEEK_API_KEY`。

### 3. Install Dependencies / 安装依赖

The app itself uses Python standard library for the local web server and SQLite. Install the official OpenReview client if you want live OpenReview import and account sync:

项目本身使用 Python 标准库启动本地服务和 SQLite。若需要实时导入 OpenReview 数据，请安装官方 OpenReview 客户端：

```bash
pip3 install openreview-py
```

### 4. Start / 启动

```bash
python3 start.py
```

Open:

```text
http://127.0.0.1:8000
```

打开浏览器访问 `http://127.0.0.1:8000`。

## Basic Workflow / 基本使用流程

1. Fill `.env.local` with your OpenReview account.
2. Start CloseReview.
3. Click `同步我的投稿` to pull your OpenReview submissions.
4. Use `整理模式` to merge papers whose titles changed across submissions.
5. Open a paper detail page to inspect the full timeline and reviews.
6. Use `AI 分析` for per-round summaries, revision advice, or full resubmission history.
7. Use `投稿可视化` to inspect activity density over time.

1. 在 `.env.local` 中配置 OpenReview 账号。
2. 启动 CloseReview。
3. 点击 `同步我的投稿` 拉取投稿记录。
4. 使用 `整理模式` 合并标题变化但实际属于同一篇工作的论文。
5. 进入论文详情页查看完整投稿时间线和 review。
6. 使用 `AI 分析` 生成本轮总结、修改建议或完整投稿历程总结。
7. 使用 `投稿可视化` 查看 OpenReview 活动密度。

## Data & Privacy / 数据与隐私

- CloseReview is local-first.
- The SQLite database is stored at `data/submissions.sqlite3`.
- `.env.local` and local databases are ignored by git.
- Do not commit OpenReview credentials or LLM API keys.
- LLM features send selected paper/review context to the configured DeepSeek-compatible API.

- CloseReview 是本地优先工具。
- SQLite 数据库保存在 `data/submissions.sqlite3`。
- `.env.local` 和本地数据库默认不会被 git 提交。
- 不要提交 OpenReview 密码或 LLM API key。
- 使用 AI 功能时，当前论文相关上下文会发送给你配置的 DeepSeek-compatible API。

## Technical Notes / 技术说明

The original technical README has been moved to [`TECHNICAL_README.md`](TECHNICAL_README.md).

原来的技术向说明已移动到 [`TECHNICAL_README.md`](TECHNICAL_README.md)。

## Current Status / 当前状态

CloseReview is an early local-first research tool built for personal paper-submission workflows. It is already useful for OpenReview-based submission tracking, but the data formats of different venues can vary. Please verify imported records before relying on them for important decisions.

CloseReview 仍处于早期阶段，主要面向个人论文投稿管理。它已经可以用于 OpenReview 投稿追踪，但不同会议的 OpenReview 数据格式可能存在差异。重要场景下请自行核对导入结果。
