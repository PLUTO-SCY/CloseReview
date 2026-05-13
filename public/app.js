const paperList = document.querySelector("#papers");
const appShell = document.querySelector(".app-shell");
const importForm = document.querySelector("#import-form");
const manualForm = document.querySelector("#manual-form");
const importStatus = document.querySelector("#import-status");
const syncButton = document.querySelector("#sync-account");
const syncStatus = document.querySelector("#sync-status");
const organizeToggle = document.querySelector("#organize-toggle");
const aiToggle = document.querySelector("#ai-toggle");
const aiDrawer = document.querySelector("#ai-drawer");
const aiClose = document.querySelector("#ai-close");
const aiTitle = document.querySelector("#ai-title");
const aiArtifacts = document.querySelector("#ai-artifacts");
const aiStatus = document.querySelector("#ai-status");
const aiMessages = document.querySelector("#ai-messages");
const aiForm = document.querySelector("#ai-form");
const aiInput = document.querySelector("#ai-input");
const backOverview = document.querySelector("#back-overview");
const viewTitle = document.querySelector("#view-title");
const navOverview = document.querySelector("#nav-overview");
const navVisuals = document.querySelector("#nav-visuals");
const sidebarToggle = document.querySelector("#sidebar-toggle");

let currentPapers = [];
let currentActivities = [];
let organizeMode = false;
let selectedPaperId = null;
let visualYear = "all";
let sidebarCollapsed = localStorage.getItem("papertrail.sidebar") === "collapsed";
let aiOpen = false;
let aiChat = null;
let aiLoading = false;
let aiFocusedAttemptId = null;

function setSidebarCollapsed(collapsed) {
  sidebarCollapsed = collapsed;
  appShell.classList.toggle("sidebar-collapsed", collapsed);
  sidebarToggle.setAttribute("aria-label", collapsed ? "展开侧边栏" : "收起侧边栏");
  sidebarToggle.setAttribute("title", collapsed ? "展开侧边栏" : "收起侧边栏");
  localStorage.setItem("papertrail.sidebar", collapsed ? "collapsed" : "expanded");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function optionList(selectedId, excludeId = null) {
  return currentPapers
    .filter((paper) => paper.id !== excludeId)
    .map((paper) => {
      const selected = paper.id === selectedId ? "selected" : "";
      return `<option value="${paper.id}" ${selected}>${escapeHtml(paper.title)}</option>`;
    })
    .join("");
}

function reviewLabel(review) {
  const rating = review.rating == null ? "" : ` · score ${review.rating}`;
  const confidence = review.confidence == null ? "" : ` · confidence ${review.confidence}`;
  return `${review.review_type.replaceAll("_", " ")}${rating}${confidence}`;
}

function isAcceptedAttempt(attempt) {
  const decision = String(attempt.decision || "").toLowerCase();
  const venue = String(attempt.venue || "").toLowerCase();
  const status = String(attempt.status || "").toLowerCase();
  const combined = `${decision} ${venue} ${status}`;
  if (/(reject|rejected|withdraw|withdrawn|desk reject|submitted to|under review)/.test(combined)) {
    return false;
  }
  return /(accept|accepted|main conference|findings|poster|oral|spotlight|regular)/.test(combined);
}

function getSelectedPaperId() {
  const match = window.location.hash.match(/^#paper=(\d+)$/);
  return match ? Number(match[1]) : null;
}

function currentView() {
  if (window.location.hash === "#visuals") return "visuals";
  return getSelectedPaperId() ? "detail" : "overview";
}

function selectedPaper() {
  return currentPapers.find((paper) => paper.id === selectedPaperId) || null;
}

function currentAiAttempt() {
  const paper = selectedPaper();
  if (!paper) return null;
  return (paper.attempts || []).find((attempt) => attempt.id === aiFocusedAttemptId) || (paper.attempts || [])[0] || null;
}

function setAiFocusedAttempt(attemptId = null) {
  const paper = selectedPaper();
  const attempts = paper?.attempts || [];
  const selected = attempts.find((attempt) => attempt.id === attemptId) || attempts[0] || null;
  aiFocusedAttemptId = selected?.id || null;
}

function formatDate(value) {
  return value ? String(value).slice(0, 10) : "";
}

function allAttempts(papers) {
  return papers
    .flatMap((paper) =>
      (paper.attempts || []).map((attempt) => ({
        ...attempt,
        paper_title: paper.title,
        paper_id: paper.id,
      }))
    )
    .filter((attempt) => formatDate(attempt.submitted_at || attempt.created_at));
}

function localDate(dateText) {
  const [year, month, day] = dateText.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function addDays(date, days) {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
}

function isoDay(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function outcomeOf(attempt) {
  const text = `${attempt.decision || ""} ${attempt.venue || ""} ${attempt.status || ""}`.toLowerCase();
  if (isAcceptedAttempt(attempt)) return "accepted";
  if (/reject|rejected|desk reject/.test(text)) return "rejected";
  if (/withdraw|withdrawn/.test(text)) return "withdrawn";
  return "other";
}

function activityLabel(activity) {
  const type = String(activity.type || "activity").replaceAll("_", " ");
  const venue = activity.venue || "Unknown venue";
  const paper = activity.paper_title || activity.title || "Untitled";
  return `${type} · ${venue} · ${paper}`;
}

function venueTrail(paper) {
  const attempts = [...(paper.attempts || [])].reverse();
  if (!attempts.length) return '<span class="venue-chip muted-chip">No submissions</span>';
  return attempts
    .map((attempt) => {
      const accepted = isAcceptedAttempt(attempt);
      return `
        <span class="venue-chip ${accepted ? "accepted-chip" : ""}">
          <strong>${escapeHtml(attempt.venue || "Unknown venue")}</strong>
          ${formatDate(attempt.submitted_at) ? `<small>${escapeHtml(formatDate(attempt.submitted_at))}</small>` : ""}
        </span>
      `;
    })
    .join('<span class="trail-arrow">→</span>');
}

function organizePanel(paper) {
  if (!organizeMode) return "";
  const aliases = (paper.aliases || [])
    .slice(0, 8)
    .map((alias) => `<span title="${escapeHtml(alias.source)}">${escapeHtml(alias.title)}</span>`)
    .join("");
  return `
    <div class="organize-panel">
      <form class="title-form" data-action="rename-paper" data-paper-id="${paper.id}">
        <label>Canonical title</label>
        <div class="inline-form">
          <input name="title" value="${escapeHtml(paper.title)}" />
          <button type="submit">保存</button>
        </div>
      </form>
      <form class="merge-form" data-action="merge-paper" data-paper-id="${paper.id}">
        <label>Merge this paper into</label>
        <div class="inline-form">
          <select name="target_paper_id">${optionList(null, paper.id)}</select>
          <button type="submit" class="danger">合并</button>
        </div>
      </form>
      ${aliases ? `<div class="aliases"><strong>Alias titles</strong>${aliases}</div>` : ""}
    </div>
  `;
}

function attemptControls(attempt, paper) {
  if (!organizeMode) return "";
  return `
    <div class="attempt-tools">
      <form data-action="move-attempt" data-attempt-id="${attempt.id}">
        <label>Move attempt to</label>
        <select name="target_paper_id">${optionList(paper.id)}</select>
        <button type="submit">移动</button>
      </form>
      <form data-action="delete-attempt" data-attempt-id="${attempt.id}" data-attempt-title="${escapeHtml(attempt.title)}">
        <button type="submit" class="danger">删除投稿</button>
      </form>
    </div>
  `;
}

function aiAttemptButton(attempt) {
  return `<button type="button" class="ai-attempt-button" data-ai-summarize-attempt="${attempt.id}">总结本轮</button>`;
}

function renderOverview(papers) {
  viewTitle.textContent = "Paper overview";
  backOverview.classList.add("hidden");
  aiToggle.classList.add("hidden");
  organizeToggle.classList.add("hidden");
  paperList.classList.add("overview-grid");
  paperList.classList.remove("detail-view", "visual-view");

  paperList.innerHTML = papers
    .map((paper) => {
      const authors = Array.isArray(paper.authors) ? paper.authors.join(", ") : "";
      const acceptedCount = (paper.attempts || []).filter(isAcceptedAttempt).length;
      return `
        <article class="overview-card" data-paper-id="${paper.id}" tabindex="0">
          <header>
            <div>
              <h3>${escapeHtml(paper.title)}</h3>
              ${authors ? `<p class="authors">${escapeHtml(authors)}</p>` : ""}
            </div>
            <span class="badge">${paper.attempts.length} attempts</span>
          </header>
          <div class="venue-trail">${venueTrail(paper)}</div>
          <footer>
            <span>${acceptedCount ? `${acceptedCount} accepted` : "No acceptance marked"}</span>
            <span>查看详情</span>
          </footer>
        </article>
      `;
    })
    .join("");
}

function renderDetail(paper) {
  viewTitle.textContent = "Paper detail";
  backOverview.classList.remove("hidden");
  aiToggle.classList.remove("hidden");
  organizeToggle.classList.remove("hidden");
  paperList.classList.remove("overview-grid", "visual-view");
  paperList.classList.add("detail-view");

  const authors = Array.isArray(paper.authors) ? paper.authors.join(", ") : "";
  const timeline = (paper.attempts || [])
    .map((attempt) => {
      const accepted = isAcceptedAttempt(attempt);
      const reviewHtml = (attempt.reviews || [])
        .map(
          (review) => `
            <article class="review">
              <strong>${escapeHtml(reviewLabel(review))}</strong>
              <p>${escapeHtml(review.text || review.summary || review.strengths || "No review text captured.")}</p>
            </article>
          `
        )
        .join("");
      const title = attempt.openreview_url
        ? `<a href="${escapeHtml(attempt.openreview_url)}" target="_blank" rel="noreferrer">${escapeHtml(attempt.title)}</a>`
        : escapeHtml(attempt.title);
      return `
        <article class="attempt ${accepted ? "accepted-attempt" : ""}">
          <div class="dot"></div>
          <div class="attempt-body">
            <div class="attempt-meta">
              <span class="venue">${escapeHtml(attempt.venue || "Unknown venue")}</span>
              ${formatDate(attempt.submitted_at) ? `<span>${escapeHtml(formatDate(attempt.submitted_at))}</span>` : ""}
              ${accepted ? '<span class="accepted-label">Accepted</span>' : ""}
              <span>${escapeHtml(attempt.status || "imported")}</span>
              ${attempt.average_rating == null ? "" : `<span class="score">avg ${attempt.average_rating}</span>`}
              ${attempt.decision ? `<span class="${accepted ? "decision-pill" : ""}">${escapeHtml(attempt.decision)}</span>` : ""}
              ${aiAttemptButton(attempt)}
            </div>
            <div class="attempt-title">${title}</div>
            ${attemptControls(attempt, paper)}
            ${reviewHtml ? `<div class="review-list">${reviewHtml}</div>` : ""}
          </div>
        </article>
      `;
    })
    .join("");

  paperList.innerHTML = `
    <section class="paper-card">
      <header class="paper-header">
        <div>
          <h3 class="paper-title">${escapeHtml(paper.title)}</h3>
          ${authors ? `<p class="authors">${escapeHtml(authors)}</p>` : ""}
        </div>
        <span class="badge">${paper.attempts.length} attempts</span>
      </header>
      ${organizePanel(paper)}
      <div class="timeline">
        ${timeline || '<article class="attempt"><div class="dot"></div><div class="attempt-body">No attempts yet.</div></article>'}
      </div>
    </section>
  `;
}

function renderVisuals(papers, activities) {
  viewTitle.textContent = "Submission visuals";
  backOverview.classList.add("hidden");
  aiToggle.classList.add("hidden");
  organizeToggle.classList.add("hidden");
  navOverview.classList.remove("active");
  navVisuals.classList.add("active");
  paperList.classList.remove("overview-grid", "detail-view");
  paperList.classList.add("visual-view");

  const allDatedActivities = (activities || []).filter((activity) => formatDate(activity.occurred_at));
  if (!allDatedActivities.length) {
    paperList.innerHTML = '<div class="empty">还没有可视化数据。</div>';
    return;
  }

  const years = [...new Set(allDatedActivities.map((activity) => formatDate(activity.occurred_at).slice(0, 4)))].sort();
  if (visualYear !== "all" && !years.includes(visualYear)) visualYear = "all";
  const datedActivities =
    visualYear === "all"
      ? allDatedActivities
      : allDatedActivities.filter((activity) => formatDate(activity.occurred_at).startsWith(visualYear));
  const attempts = allAttempts(papers).filter((attempt) => {
    const day = formatDate(attempt.submitted_at || attempt.created_at);
    return visualYear === "all" || day.startsWith(visualYear);
  });
  const yearOptions = ['<option value="all">All years</option>']
    .concat(years.map((year) => `<option value="${year}" ${year === visualYear ? "selected" : ""}>${year}</option>`))
    .join("");

  const byDay = new Map();
  datedActivities.forEach((activity) => {
    const day = formatDate(activity.occurred_at);
    if (!byDay.has(day)) byDay.set(day, []);
    byDay.get(day).push(activity);
  });

  const dates = [...byDay.keys()].sort();
  const minYear = localDate(dates[0]).getFullYear();
  const maxYear = localDate(dates[dates.length - 1]).getFullYear();
  let cursor = localDate(`${minYear}-01-01`);
  cursor = addDays(cursor, -cursor.getDay());
  const end = localDate(`${maxYear}-12-31`);
  const endPadded = addDays(end, 6 - end.getDay());
  const cells = [];
  const monthLabels = [];
  let previousMonth = "";
  while (cursor <= endPadded) {
    if (cursor.getDay() === 0) {
      const month = cursor.toLocaleString("en", { month: "short" });
      monthLabels.push(month !== previousMonth ? `<span>${month}</span>` : "<span></span>");
      previousMonth = month;
    }
    const day = isoDay(cursor);
    const dayActivities = byDay.get(day) || [];
    const level = Math.min(dayActivities.length, 4);
    const label = dayActivities.map(activityLabel).join("\n");
    cells.push(
      `<span class="heat-cell level-${level}" title="${escapeHtml(dayActivities.length ? `${day}\n${label}` : day)}"></span>`
    );
    cursor = addDays(cursor, 1);
  }

  const byMonth = new Map();
  datedActivities.forEach((activity) => {
    const month = formatDate(activity.occurred_at).slice(0, 7);
    byMonth.set(month, (byMonth.get(month) || 0) + 1);
  });
  const maxMonthCount = Math.max(...byMonth.values());
  const monthBars = [...byMonth.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([month, count]) => {
      const height = Math.max(12, Math.round((count / maxMonthCount) * 120));
      return `<div class="month-bar" title="${escapeHtml(`${month}: ${count} activities`)}"><span style="height:${height}px"></span><small>${escapeHtml(month.slice(2))}</small></div>`;
    })
    .join("");

  const outcomeCounts = attempts.reduce((acc, attempt) => {
    const outcome = outcomeOf(attempt);
    acc[outcome] = (acc[outcome] || 0) + 1;
    return acc;
  }, {});

  const venues = [...attempts.reduce((map, attempt) => {
    const venue = attempt.venue || "Unknown venue";
    map.set(venue, (map.get(venue) || 0) + 1);
    return map;
  }, new Map()).entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([venue, count]) => `<li><span>${escapeHtml(venue)}</span><strong>${count}</strong></li>`)
    .join("");

  const busiest = [...byDay.entries()].sort((a, b) => b[1].length - a[1].length)[0];
  const activityTypes = datedActivities.reduce((acc, activity) => {
    const type = activity.type || "activity";
    acc[type] = (acc[type] || 0) + 1;
    return acc;
  }, {});
  const typeList = Object.entries(activityTypes)
    .sort((a, b) => b[1] - a[1])
    .map(([type, count]) => `<span>${escapeHtml(type.replaceAll("_", " "))} ${count}</span>`)
    .join("");

  paperList.innerHTML = `
    <section class="visual-dashboard">
      <div class="visual-toolbar">
        <div>
          <h3>OpenReview activity range</h3>
          <p>${escapeHtml(dates[0])} to ${escapeHtml(dates[dates.length - 1])}</p>
        </div>
        <label>
          <span>Year</span>
          <select id="visual-year">${yearOptions}</select>
        </label>
      </div>
      <div class="visual-summary">
        <div><strong>${datedActivities.length}</strong><span>activities</span></div>
        <div><strong>${attempts.length}</strong><span>submissions</span></div>
        <div><strong>${outcomeCounts.accepted || 0}</strong><span>accepted</span></div>
        <div><strong>${byMonth.size}</strong><span>active months</span></div>
      </div>

      <section class="visual-panel">
        <header>
          <h3>Submission density</h3>
          <p>Each square is a day. Darker squares mean more OpenReview activities: submissions, reviews, comments, responses, and decisions.</p>
        </header>
        <div class="heatmap-wrap">
          <div class="weekday-labels"><span>Sun</span><span>Mon</span><span>Tue</span><span>Wed</span><span>Thu</span><span>Fri</span><span>Sat</span></div>
          <div class="heatmap-area">
            <div class="month-labels">${monthLabels.join("")}</div>
            <div class="heatmap">${cells.join("")}</div>
          </div>
        </div>
        <div class="heat-legend"><span>Less</span><i class="level-0"></i><i class="level-1"></i><i class="level-2"></i><i class="level-3"></i><i class="level-4"></i><span>More</span></div>
      </section>

      <section class="visual-grid">
        <div class="visual-panel">
          <header>
            <h3>Monthly rhythm</h3>
            <p>OpenReview activity count by month.</p>
          </header>
          <div class="month-bars">${monthBars}</div>
        </div>
        <div class="visual-panel">
          <header>
            <h3>Outcomes</h3>
            <p>Current result labels across attempts.</p>
          </header>
          <div class="outcome-list">
            <span class="accepted-chip">Accepted ${outcomeCounts.accepted || 0}</span>
            <span>Rejected ${outcomeCounts.rejected || 0}</span>
            <span>Withdrawn ${outcomeCounts.withdrawn || 0}</span>
            <span>Other ${outcomeCounts.other || 0}</span>
          </div>
          <div class="outcome-list">${typeList}</div>
          <ol class="venue-rank">${venues}</ol>
        </div>
      </section>
    </section>
  `;
}

function render(papers) {
  currentPapers = papers;
  selectedPaperId = getSelectedPaperId();
  const attempts = papers.flatMap((paper) => paper.attempts || []);
  const reviews = attempts.flatMap((attempt) => attempt.reviews || []);
  document.querySelector("#paper-count").textContent = papers.length;
  document.querySelector("#attempt-count").textContent = attempts.length;
  document.querySelector("#review-count").textContent = reviews.length;
  organizeToggle.classList.toggle("active", organizeMode);
  navOverview.classList.toggle("active", currentView() === "overview");
  navVisuals.classList.toggle("active", currentView() === "visuals");

  if (!papers.length) {
    paperList.innerHTML = '<div class="empty">还没有论文。粘贴 OpenReview 链接导入，或先手动添加一篇。</div>';
    return;
  }

  if (currentView() === "visuals") {
    closeAiDrawer();
    renderVisuals(papers, currentActivities);
    return;
  }

  const selected = papers.find((paper) => paper.id === selectedPaperId);
  if (selected) {
    renderDetail(selected);
    if (aiOpen) {
      aiTitle.textContent = selected.title;
    }
  } else {
    closeAiDrawer();
    renderOverview(papers);
  }
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Request failed.");
  return data;
}

async function loadPapers() {
  const [papersResponse, activitiesResponse] = await Promise.all([fetch("/api/papers"), fetch("/api/activities")]);
  const papersData = await papersResponse.json();
  const activitiesData = await activitiesResponse.json();
  currentActivities = activitiesData.activities || [];
  render(papersData.papers || []);
}

function renderAiDrawer() {
  const paper = selectedPaper();
  aiDrawer.classList.toggle("open", aiOpen);
  aiDrawer.setAttribute("aria-hidden", aiOpen ? "false" : "true");
  aiToggle.classList.toggle("active", aiOpen);
  if (!aiOpen || !paper) return;

  aiTitle.textContent = paper.title;
  setAiFocusedAttempt(aiFocusedAttemptId);
  const attempt = currentAiAttempt();
  const configured = aiChat?.configured !== false;
  aiInput.disabled = !configured || aiLoading;
  aiForm.querySelector("button").disabled = !configured || aiLoading;
  aiDrawer.querySelectorAll("[data-ai-action]").forEach((button) => {
    button.disabled = !configured || aiLoading;
  });
  aiArtifacts.innerHTML = (aiChat?.artifacts || [])
    .slice(0, 3)
    .map((artifact) => {
      const label = artifact.artifact_type === "attempt_summary" ? `投稿总结 #${artifact.scope_key}` : "论文总结";
      return `
        <article class="ai-artifact">
          <strong>${escapeHtml(label)}</strong>
          <p>${escapeHtml(artifact.content)}</p>
        </article>
      `;
    })
    .join("");
  if (!configured) {
    aiStatus.textContent = "请在 .env.local 中配置 DEEPSEEK_API_KEY，然后重启服务。";
  } else if (!aiLoading && !aiStatus.textContent) {
    aiStatus.textContent = attempt
      ? `当前轮次：${attempt.venue || "Unknown venue"} · ${formatDate(attempt.submitted_at || attempt.created_at)}`
      : "已连接当前 paper 的全部投稿上下文。";
  }
  aiMessages.innerHTML = (aiChat?.messages || [])
    .map(
      (message) => `
        <article class="ai-message ${message.role}">
          <strong>${message.role === "assistant" ? "AI" : "You"}</strong>
          <p>${escapeHtml(message.content)}</p>
        </article>
      `
    )
    .join("");
  aiMessages.scrollTop = aiMessages.scrollHeight;
}

function closeAiDrawer() {
  aiOpen = false;
  renderAiDrawer();
}

async function loadAiChat() {
  const paper = selectedPaper();
  if (!paper) return;
  aiStatus.textContent = "Loading AI context...";
  renderAiDrawer();
  try {
    const response = await fetch(`/api/papers/${paper.id}/chat`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Failed to load chat.");
    aiChat = data;
    aiStatus.textContent = "";
  } catch (error) {
    aiStatus.textContent = error.message;
  } finally {
    renderAiDrawer();
  }
}

async function openAiDrawer() {
  setAiFocusedAttempt(aiFocusedAttemptId);
  aiOpen = true;
  renderAiDrawer();
  await loadAiChat();
}

async function sendAiMessage(message, attemptId = null) {
  const paper = selectedPaper();
  if (!paper || !message || aiLoading) return;
  aiLoading = true;
  aiStatus.textContent = "AI 正在分析...";
  renderAiDrawer();
  try {
    const data = await postJson(`/api/papers/${paper.id}/chat`, {
      message,
      attempt_id: attemptId,
    });
    aiChat = { ...(aiChat || {}), messages: data.messages };
    aiInput.value = "";
    aiStatus.textContent = "";
  } catch (error) {
    aiStatus.textContent = error.message;
  } finally {
    aiLoading = false;
    renderAiDrawer();
  }
}

async function summarizeWithAi(attemptId = null) {
  const paper = selectedPaper();
  if (!paper || aiLoading) return;
  aiLoading = true;
  aiStatus.textContent = attemptId ? "AI 正在总结这轮投稿..." : "AI 正在总结投稿历程...";
  renderAiDrawer();
  try {
    const data = await postJson(`/api/papers/${paper.id}/llm/summarize`, {
      attempt_id: attemptId,
    });
    aiChat = {
      ...(aiChat || {}),
      messages: data.messages,
      artifacts: data.artifacts || (data.artifact
        ? [data.artifact].concat((aiChat?.artifacts || []).filter((artifact) => artifact.id !== data.artifact.id))
        : aiChat?.artifacts || []),
    };
    aiStatus.textContent = "";
  } catch (error) {
    aiStatus.textContent = error.message;
  } finally {
    aiLoading = false;
    renderAiDrawer();
  }
}

organizeToggle.addEventListener("click", () => {
  organizeMode = !organizeMode;
  render(currentPapers);
});

navOverview.addEventListener("click", () => {
  window.location.hash = "";
});

navVisuals.addEventListener("click", () => {
  window.location.hash = "visuals";
});

backOverview.addEventListener("click", () => {
  window.location.hash = "";
});

aiToggle.addEventListener("click", () => {
  if (aiOpen) {
    closeAiDrawer();
  } else {
    openAiDrawer();
  }
});

aiClose.addEventListener("click", closeAiDrawer);

sidebarToggle.addEventListener("click", () => {
  setSidebarCollapsed(!sidebarCollapsed);
});

window.addEventListener("hashchange", () => {
  render(currentPapers);
});

paperList.addEventListener("click", (event) => {
  const summarizeButton = event.target.closest("[data-ai-summarize-attempt]");
  if (summarizeButton) {
    const attemptId = Number(summarizeButton.dataset.aiSummarizeAttempt);
    setAiFocusedAttempt(attemptId);
    openAiDrawer().then(() => summarizeWithAi(attemptId));
    return;
  }
  const card = event.target.closest(".overview-card");
  if (!card) return;
  window.location.hash = `paper=${card.dataset.paperId}`;
});

paperList.addEventListener("keydown", (event) => {
  if (event.key !== "Enter") return;
  const card = event.target.closest(".overview-card");
  if (!card) return;
  window.location.hash = `paper=${card.dataset.paperId}`;
});

paperList.addEventListener("change", (event) => {
  if (event.target.id !== "visual-year") return;
  visualYear = event.target.value;
  render(currentPapers);
});

aiDrawer.addEventListener("click", (event) => {
  const actionButton = event.target.closest("[data-ai-action]");
  if (!actionButton) return;
  const paper = selectedPaper();
  if (!paper) return;
  if (actionButton.dataset.aiAction === "paper-summary") {
    summarizeWithAi();
  }
  if (actionButton.dataset.aiAction === "attempt-summary") {
    summarizeWithAi(currentAiAttempt()?.id || null);
  }
  if (actionButton.dataset.aiAction === "revision-advice") {
    const attempt = currentAiAttempt();
    sendAiMessage(
      "请只针对当前轮次投稿的审稿意见，给出下一步修改优先级和具体行动建议。其他投稿轮次只作为对比参考。",
      attempt?.id || null
    );
  }
});

aiForm.addEventListener("submit", (event) => {
  event.preventDefault();
  sendAiMessage(new FormData(aiForm).get("message"));
});

paperList.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.target;
  const action = form.dataset.action;
  try {
    if (action === "rename-paper") {
      await postJson("/api/papers/update-title", {
        paper_id: Number(form.dataset.paperId),
        title: new FormData(form).get("title"),
      });
    }
    if (action === "merge-paper") {
      const formData = new FormData(form);
      const targetId = Number(formData.get("target_paper_id"));
      const target = currentPapers.find((paper) => paper.id === targetId);
      const source = currentPapers.find((paper) => paper.id === Number(form.dataset.paperId));
      if (!target || !source || !confirm(`Merge "${source.title}" into "${target.title}"?`)) return;
      await postJson("/api/papers/merge", {
        source_paper_id: Number(form.dataset.paperId),
        target_paper_id: targetId,
      });
    }
    if (action === "move-attempt") {
      await postJson("/api/attempts/move", {
        attempt_id: Number(form.dataset.attemptId),
        target_paper_id: Number(new FormData(form).get("target_paper_id")),
      });
    }
    if (action === "delete-attempt") {
      const title = form.dataset.attemptTitle || "this submission attempt";
      if (!confirm(`Delete this submission attempt?\n\n${title}\n\nIt will be ignored in future OpenReview syncs.`)) return;
      await postJson("/api/attempts/delete", {
        attempt_id: Number(form.dataset.attemptId),
        reason: "manual_delete",
      });
    }
    await loadPapers();
  } catch (error) {
    alert(error.message);
  }
});

importForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const url = new FormData(importForm).get("url");
  importStatus.textContent = "Importing from OpenReview...";
  try {
    const data = await postJson("/api/openreview/import-url", { url });
    importStatus.textContent = `Imported ${data.reviews} notes into the timeline.`;
    importForm.reset();
    await loadPapers();
  } catch (error) {
    importStatus.textContent = error.message;
  }
});

manualForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(manualForm);
  const payload = {
    title: form.get("title"),
    venue: form.get("venue"),
  };
  const response = await fetch("/api/papers", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (response.ok) {
    manualForm.reset();
    await loadPapers();
  }
});

syncButton.addEventListener("click", async () => {
  syncButton.disabled = true;
  syncStatus.textContent = "Discovering your OpenReview submissions...";
  try {
    const data = await postJson("/api/openreview/sync-account", {});
    const failed = data.failed?.length ? ` ${data.failed.length} failed.` : "";
    const skipped = data.skipped ? ` ${data.skipped} skipped.` : "";
    syncStatus.textContent = `Discovered ${data.discovered}, imported ${data.imported}.${skipped}${failed}`;
    await loadPapers();
  } catch (error) {
    syncStatus.textContent = error.message;
  } finally {
    syncButton.disabled = false;
  }
});

setSidebarCollapsed(sidebarCollapsed);
loadPapers();
