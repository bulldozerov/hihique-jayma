"use strict";

const byId = (id) => document.getElementById(id);
const fileInput = byId("file");
const drop = byId("drop");
const run = byId("run");
const status = byId("status");
const progress = byId("progress");
const result = byId("result");
const report = byId("report");
const severity = { critical: "Критично", major: "Существенно", minor: "Низкий приоритет" };
const kinds = {
  ambiguity: "Двусмысленность", unverifiable: "Непроверяемость",
  incomplete: "Неполнота", design_constraint: "Ограничение реализации",
  contradiction: "Противоречие", gap: "Пробел", duplication: "Дублирование",
};
let selectedFile;
let currentReview;

function selectFile(file) {
  if (!file) return;
  selectedFile = file;
  currentReview = undefined;
  sessionStorage.removeItem("requirementsReview");
  const fileName = byId("file-name");
  fileName.textContent = file.name;
  fileName.hidden = false;
  status.textContent = "Файл выбран. Запустите проверку.";
  result.hidden = true;
  run.hidden = false;
  run.disabled = false;
}

fileInput?.addEventListener("change", () => selectFile(fileInput.files[0]));
for (const eventName of ["dragenter", "dragover"]) {
  drop?.addEventListener(eventName, (event) => {
    event.preventDefault();
    if (!fileInput.disabled) drop.classList.add("drag");
  });
}
drop?.addEventListener("dragleave", (event) => {
  if (!drop.contains(event.relatedTarget)) drop.classList.remove("drag");
});
drop?.addEventListener("drop", (event) => {
  event.preventDefault();
  drop.classList.remove("drag");
  if (!fileInput.disabled) selectFile(event.dataTransfer.files[0]);
});

async function runReview(file) {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch("/api/reviews", { method: "POST", body: form });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(typeof error?.detail === "string" ? error.detail : "Не удалось проверить файл.");
  }
  return response.json();
}

function counts(review) {
  const findings = [...review.requirements.flatMap((item) => item.findings), ...review.document_findings];
  return { findings, critical: findings.filter((item) => item.severity === "critical") };
}

run?.addEventListener("click", async () => {
  if (!selectedFile) return;
  run.disabled = true;
  fileInput.disabled = true;
  progress.hidden = false;
  result.hidden = true;
  status.textContent = "Подготавливаем отчёт…";
  try {
    const review = await runReview(selectedFile);
    sessionStorage.setItem("requirementsReview", JSON.stringify(review));
    currentReview = review;
    result.hidden = false;
    status.textContent = "Отчёт готов.";
    result.scrollIntoView({ block: "nearest" });
  } catch (error) {
    status.textContent = error.message;
  } finally {
    progress.hidden = true;
    fileInput.disabled = false;
    run.disabled = false;
  }
});

function findingLabel(finding) {
  return `${severity[finding.severity]} · ${kinds[finding.kind]}`;
}

const scene = document.querySelector(".scene");
if (scene) {
  const settle = () => scene.classList.add("settled");
  window.addEventListener("pointermove", settle, { once: true });
  scene.addEventListener("focusin", settle, { once: true });
}

function sources(review, ids) {
  return ids.flatMap((id) => {
    const block = review.evidence[id];
    if (!block) return [];
    const location = block.page ? `стр. ${block.page}` : `строки ${block.start_line}–${block.end_line}`;
    return [`${id}, ${location}\n${block.source}`];
  });
}

function passport(review) {
  return [
    `Документ — ${review.document}`,
    `Модель — ${review.model}`,
    `Дата прогона — ${review.run_date ?? "не записана в исходном JSON"}`,
    `Версия агента — ${review.agent_version ?? "не записана в исходном JSON"}`,
  ];
}

function verdict() {
  return "Готовность к разработке и тестированию требует проверки замечаний. Сначала сверьте критичные замечания с источником.";
}

function append(parent, tag, content) {
  const element = document.createElement(tag);
  element.textContent = content;
  parent.append(element);
  return element;
}

function addFinding(parent, finding) {
  append(parent, "p", `${findingLabel(finding)}. ${finding.explanation}`);
  for (const quote of finding.conflicting_quotes ?? []) append(parent, "blockquote", quote);
}

function reportSection(container, id, title) {
  const section = append(container, "section", "");
  section.className = "report-section";
  section.id = id;
  append(section, "h2", title);
  return section;
}

function renderReport(review, container) {
  const metadata = reportSection(container, "passport", "Паспорт прогона");
  for (const line of passport(review)) append(metadata, "p", line);

  const whole = reportSection(container, "findings", "Замечания по документу");
  if (!review.document_findings.length) append(whole, "p", "Агент не нашёл замечаний.");
  for (const finding of review.document_findings) {
    const entry = append(whole, "div", "");
    entry.className = "finding";
    append(entry, "h3", findingLabel(finding));
    append(entry, "p", finding.explanation);
    for (const quote of finding.conflicting_quotes ?? []) append(entry, "blockquote", quote);
    const sourceBlocks = append(entry, "details", "");
    append(sourceBlocks, "summary", "Фрагменты документа");
    for (const source of sources(review, finding.block_ids)) append(sourceBlocks, "blockquote", source);
  }
  for (const warning of review.review_warnings ?? []) append(whole, "p", warning);

  const requirements = reportSection(container, "requirements", "Отдельные требования");
  for (const item of review.requirements) {
    const entry = append(requirements, "details", "");
    append(entry, "summary", [item.id, item.source_id, item.statement].filter(Boolean).join(" · "));
    if (!item.findings.length) append(entry, "p", "Агент не нашёл замечаний.");
    for (const finding of item.findings) addFinding(entry, finding);
    for (const source of sources(review, item.block_ids)) append(entry, "blockquote", source);
  }
  append(reportSection(container, "outcome", "Итог"), "p", verdict());
}

if (report) {
  const saved = sessionStorage.getItem("requirementsReview");
  if (saved) {
    currentReview = JSON.parse(saved);
    const { findings, critical } = counts(currentReview);
    byId("summary").textContent = `${currentReview.document} · Требований: ${currentReview.requirements.length} · Замечаний: ${findings.length} · Критичных по оценке агента: ${critical.length}`;
    renderReport(currentReview, report);
  } else {
    status.textContent = "Загрузите документ и запустите проверку.";
  }
}

function markdownReport(review) {
  const lines = ["# Отчёт о проверке требований", "", "## Паспорт прогона", ""];
  const quote = (text) => lines.push(...text.split("\n").map((line) => `> ${line}`), "");
  const findingLine = (item) => {
    lines.push(`- ${findingLabel(item)}. ${item.explanation}`, "");
    for (const text of item.conflicting_quotes ?? []) quote(text);
  };
  lines.push(...passport(review).map((line) => `- ${line}`), "", "## Карта требований", "");
  lines.push("| ID отчёта | ID источника | Формулировка |", "| --- | --- | --- |");
  const cell = (text) => text.replaceAll("|", "\\|").replace(/\r?\n/g, " ");
  for (const item of review.requirements) {
    lines.push(`| ${cell(item.id)} | ${cell(item.source_id || "—")} | ${cell(item.statement)} |`);
  }
  lines.push("", "## Проверка отдельных требований");
  for (const item of review.requirements) {
    lines.push("", `### ${item.id}`, "");
    if (!item.findings.length) lines.push("Агент не нашёл замечаний.", "");
    item.findings.forEach(findingLine);
    sources(review, item.block_ids).forEach(quote);
  }
  lines.push("## Проверка документа целиком", "");
  if (!review.document_findings.length) lines.push("Агент не нашёл замечаний.", "");
  for (const finding of review.document_findings) {
    findingLine(finding);
    sources(review, finding.block_ids).forEach(quote);
  }
  if (review.review_warnings?.length) {
    lines.push("## Предупреждения прогона", "", ...review.review_warnings.map((warning) => `- ${warning}`), "");
  }
  const { findings, critical } = counts(review);
  lines.push("## Сводка", "", `Требований — ${review.requirements.length}. Замечаний — ${findings.length}. Критичных по оценке агента — ${critical.length}.`, "");
  critical.forEach(findingLine);
  lines.push("## Итог", "", verdict(), "");
  return lines.join("\n");
}

for (const button of document.querySelectorAll("[data-download]")) {
  button.addEventListener("click", async () => {
    if (!currentReview) return;
    const review = currentReview;
    const format = button.dataset.download;
    button.disabled = true;
    try {
      let blob;
      if (format === "pdf") {
        const printable = document.createElement("article");
        append(printable, "h1", "Отчёт о проверке требований");
        renderReport(review, printable);
        blob = await globalThis.createReportPdf(printable);
      } else {
        blob = new Blob([markdownReport(review)], { type: "text/markdown;charset=utf-8" });
      }
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `review.${format}`;
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 30_000);
    } catch {
      if (currentReview === review) status.textContent = "Не удалось скачать отчёт. Попробуйте ещё раз.";
    } finally {
      button.disabled = false;
    }
  });
}
