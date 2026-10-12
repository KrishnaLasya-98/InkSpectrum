import { el, getJSON, fmtAgo } from "/ui/lib.js";

const id = decodeURIComponent(location.pathname.split("/").pop());
const container = document.getElementById("chapters");

async function refresh() {
  const state = await getJSON(`/api/collections/${encodeURIComponent(id)}`);
  document.getElementById("title").textContent = state.id.replaceAll("-", " ");
  document.getElementById("summary").textContent = `${state.completed_count} of ${state.chapter_count} chapters verified${state.next_chapter ? ` · Chapter ${state.next_chapter} is next` : " · Collection complete"}`;
  document.getElementById("bar").style.width = `${state.chapter_count ? 100 * state.completed_count / state.chapter_count : 0}%`;
  document.getElementById("updated").textContent = `Updated ${new Date().toLocaleTimeString()}`;
  container.replaceChildren();
  for (const chapter of state.chapters) {
    const stage = chapter.active_stage ? ` · Stage: ${chapter.active_stage.replaceAll("_", " ")}` : "";
    const activity = chapter.last_activity ? ` · Activity ${fmtAgo(chapter.last_activity)}` : "";
    const detail = chapter.status === "completed" ? "Encoded video and QA evidence verified"
      : chapter.status === "waiting_for_previous_chapter" ? "Waiting for prior chapter QA"
      : chapter.review_render ? `Review render ready · ${chapter.review_render.qa_status}`
      : chapter.status === "in_progress" ? `Project in progress${stage}${activity}`
      : chapter.status === "ready" ? "Ready after previous chapter" : "Queued";
    const link = chapter.project_id ? el("a", { href: `/p/${encodeURIComponent(chapter.project_id)}` }, "Open storyboard") : null;
    const reviewLink = chapter.review_render ? el("a", {
      href: chapter.review_render.url,
      target: "_blank",
      rel: "noopener noreferrer",
    }, "Watch review video") : null;
    const actions = el("div", { class: "actions" }, link, reviewLink);
    container.append(el("article", { class: `card ${chapter.status}` },
      el("div", { class: "num" }, String(chapter.chapter).padStart(2, "0")),
      el("div", {}, el("div", { class: "title" }, chapter.title), el("div", { class: "detail" }, detail), actions),
      el("span", { class: "badge" }, chapter.status.replaceAll("_", " ")),
    ));
  }
}

refresh().catch((error) => { container.textContent = `Unable to load collection: ${error.message}`; });
setInterval(() => refresh().catch(() => {}), 15000);
