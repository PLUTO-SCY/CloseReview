# CloseReview

[English](README.md)

**CloseReview** 是一个本地优先的论文投稿管理工具，面向经常使用 OpenReview 投稿的研究者。它帮助你追踪一篇论文从初投稿、被拒、改投、再审到最终录用的完整过程，避免遗忘历史版本、审稿意见、分数和决策。

## 为什么需要 CloseReview？

顶会论文常常涉及多次转投。标题可能改、会议可能变、审稿意见也分散在不同 OpenReview 页面中。CloseReview 会把这些零散记录整理成一个可浏览、可合并、可分析的论文工作台：时间线、审稿意见、投稿密度可视化、手动归类和 AI 分析都在一个地方。

## 功能

### 投稿总览

- 总览页展示所有论文项目。
- 每篇论文显示最新标题、作者和投稿会议轨迹。
- 按首次投稿时间排序，最新项目在上。

### 论文时间线

- 每篇论文都有独立详情页，按时间倒序展示投稿轮次。
- 每次投稿记录会议、日期、标题、decision、状态、分数和清理后的官方 review。
- 被录用的投稿会被特别高亮。

### OpenReview 同步

- 支持从 OpenReview 账号同步投稿记录。
- 支持手动导入单篇 OpenReview 链接或 forum id。
- 后续再次同步时，会保留你手动整理过的归类结果。

### 手动归类

- 可以把“标题不同但其实是同一篇工作”的论文合并到一起。
- 可以把某一次投稿移动到另一篇论文下。
- 可以手动删除某次投稿，并进行二次确认。
- 删除记录会写入忽略列表，避免以后同步时又被拉回来。

### Review 清理

- 从复杂的 OpenReview 数据中提取正式审稿意见。
- 尽量排除 author response、rebuttal、comment、decision 和 meta-review，让 review 展示更干净。

### AI 分析

- 每篇论文详情页都有右侧 `AI 分析`抽屉。
- `总结本轮`：只总结当前选中的投稿轮次。
- `修改建议`：只针对当前轮次给出修改建议。
- `总结投稿历程`：先对每轮投稿做摘要，再综合生成完整转投历程，避免上下文过长。
- 支持自由问答，AI 会基于当前论文的投稿、decision、分数和 review 作答。
- 聊天记录和 AI 摘要都会保存在本地数据库。

### 活动可视化

- 类似 GitHub contributions 的活动热力图。
- 不只统计投稿，也统计 review、comment、response、decision 等 OpenReview 活动。
- 支持年份筛选、月份标签、月度节奏、结果统计和会议排名。

## 快速开始

### 1. 下载

```bash
git clone https://github.com/PLUTO-SCY/CloseReview.git
cd CloseReview
```

### 2. 创建环境配置

```bash
cp .env.example .env.local
```

编辑 `.env.local`：

```bash
OPENREVIEW_USERNAME=your_openreview_email
OPENREVIEW_PASSWORD=your_openreview_password
OPENREVIEW_API_VERSION=auto

DEEPSEEK_API_KEY=your_deepseek_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro
DEEPSEEK_REASONING_EFFORT=high
```

OpenReview 同步需要账号密码；AI 分析需要 `DEEPSEEK_API_KEY`。

### 3. 安装依赖

项目本身使用 Python 标准库启动本地服务、管理 SQLite 数据库，并调用 DeepSeek-compatible API。唯一的第三方 Python 依赖是官方 OpenReview 客户端，用于实时导入 OpenReview 数据和账号同步：

```bash
pip3 install openreview-py
```

### 4. 启动

```bash
python3 start.py
```

打开浏览器访问：

```text
http://127.0.0.1:8000
```

## 基本使用流程

1. 在 `.env.local` 中配置 OpenReview 账号。
2. 启动 CloseReview。
3. 点击 `同步我的投稿` 拉取投稿记录。
4. 使用 `整理模式` 合并标题变化但实际属于同一篇工作的论文。
5. 进入论文详情页查看完整投稿时间线和 review。
6. 使用 `AI 分析` 生成本轮总结、修改建议或完整投稿历程总结。
7. 使用 `投稿可视化` 查看 OpenReview 活动密度。

## 数据与隐私

- CloseReview 是本地优先工具。
- SQLite 数据库保存在 `data/submissions.sqlite3`。
- `.env.local` 和本地数据库默认不会被 git 提交。
- 不要提交 OpenReview 密码或 LLM API key。
- 使用 AI 功能时，当前论文相关上下文会发送给你配置的 DeepSeek-compatible API。

## 技术说明

原来的技术向说明已移动到 [`TECHNICAL_README.md`](TECHNICAL_README.md)。

## 当前状态

CloseReview 仍处于早期阶段，主要面向个人论文投稿管理。它已经可以用于 OpenReview 投稿追踪，但不同会议的 OpenReview 数据格式可能存在差异。重要场景下请自行核对导入结果。
