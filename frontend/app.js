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
  byId("file-name").textContent = file.name;
  status.textContent = "Файл выбран. Откроется пример готового отчёта.";
  result.hidden = true;
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

// Replace this adapter with the backend request when the API is available.
async function runReview(_file) {
  await new Promise((resolve) => setTimeout(resolve, 850));
  return globalThis.demoReport;
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
    currentReview = await runReview(selectedFile);
    result.hidden = false;
    status.textContent = "Отчёт готов к просмотру.";
  } catch {
    status.textContent = "Не удалось подготовить отчёт. Повторите запуск.";
  } finally {
    progress.hidden = true;
    fileInput.disabled = false;
    run.disabled = false;
  }
});

function findingLabel(finding) {
  return `${severity[finding.severity]} · ${kinds[finding.kind]}`;
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
    "Пример по сохранённому прогону для requirements.pdf.",
    `Документ — ${review.document}`,
    `Модель — ${review.model}`,
    `Дата прогона — ${review.run_date ?? "не записана в исходном JSON"}`,
    `Версия агента — ${review.agent_version ?? "не записана в исходном JSON"}`,
  ];
}

function verdict() {
  return "Готовность к разработке и тестированию по сохранённому прогону не определена. Сначала сверьте критичные замечания с источником.";
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

function reportSection(id, title) {
  const section = append(report, "section", "");
  section.className = "report-section";
  section.id = id;
  append(section, "h2", title);
  return section;
}

function renderReport(review) {
  const { findings, critical } = counts(review);
  byId("summary").textContent = `${review.document} · Требований: ${review.requirements.length} · Замечаний: ${findings.length} · Критичных по оценке агента: ${critical.length}`;

  const metadata = reportSection("passport", "Паспорт прогона");
  for (const line of passport(review)) append(metadata, "p", line);

  const whole = reportSection("findings", "Замечания по документу");
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

  const requirements = reportSection("requirements", "Отдельные требования");
  for (const item of review.requirements) {
    const entry = append(requirements, "details", "");
    append(entry, "summary", [item.id, item.source_id, item.statement].filter(Boolean).join(" · "));
    if (!item.findings.length) append(entry, "p", "Агент не нашёл замечаний.");
    for (const finding of item.findings) addFinding(entry, finding);
    for (const source of sources(review, item.block_ids)) append(entry, "blockquote", source);
  }
  append(reportSection("outcome", "Итог"), "p", verdict());
}

if (report) {
  currentReview = globalThis.demoReport;
  renderReport(currentReview);
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

byId("download").addEventListener("click", () => {
  if (!currentReview) return;
  const url = URL.createObjectURL(new Blob([markdownReport(currentReview)], { type: "text/markdown;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = "review.md";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});


function drawTexture() {
  const canvas = byId("texture");
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const width = canvas.width = Math.ceil(innerWidth / 2);
  const height = canvas.height = Math.ceil(innerHeight / 2);
  let seed = 12345;
  function random() {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    return seed / 4294967296;
  }

  ctx.fillStyle = "#140917";
  ctx.fillRect(0, 0, width, height);
  const fragments = [
    { ink: "#a831ee", points: [[0,0],[.36,0],[.32,.12],[.27,.14],[.29,.19],[.16,.48],[0,.67]] },
    { ink: "#ec2198", points: [[.64,0],[1,0],[1,.57],[.91,.49],[.81,.37],[.85,.33],[.76,.24]] },
    { ink: "#652aba", points: [[0,.7],[.28,.57],[.22,.7],[.39,.76],[.46,1],[0,1]] },
    { ink: "#b828d1", points: [[1,.51],[1,1],[.64,1],[.75,.89],[.73,.82],[.84,.75],[.9,.61]] },
  ];

  for (const { ink, points } of fragments) {
    ctx.save();
    ctx.beginPath();
    points.forEach(([x, y], index) => {
      if (index === 0) ctx.moveTo(x * width, y * height);
      else ctx.lineTo(x * width, y * height);
    });
    ctx.closePath();
    ctx.clip();
    ctx.fillStyle = ink;
    ctx.fillRect(0, 0, width, height);
    for (let y = 0; y < height; y += 2) {
      for (let x = y % 4; x < width; x += 4) {
        const grain = random();
        const phase = (x + 2 * y + 36 * Math.sin(y / 35)) % 79;
        ctx.fillStyle = grain > .98 ? "#fff6ff" : "#180a22";
        if (grain > .48 || phase < 27) ctx.fillRect(x, y, grain > .6 ? 2 : 1, 1);
      }
    }
    ctx.restore();
  }

  for (let i = 0; i < 76; i++) {
    const x = Math.floor(random() * width);
    const y = Math.floor(random() * height);
    const length = Math.floor(random() * width * .23) + 4;
    ctx.fillStyle = ["#fceaf7", "#2a0b37", "#ff49bc", "#6d36ac"][i % 4];
    ctx.fillRect(x, y, length, i % 7 === 0 ? 3 : 1);
    if (i % 3 === 0) {
      ctx.fillStyle = "#17091c";
      ctx.fillRect(x + 14, y + 1, length * .73, 4);
    }
  }

  const blocks = [[.11,.3], [.86,.14], [.09,.78], [.8,.86]];
  for (const [x, y] of blocks) {
    for (let row = 0; row < 9; row++) {
      for (let col = 0; col < 14; col++) {
        if (random() > .52) continue;
        ctx.fillStyle = random() > .62 ? "#fceaf7" : "#36104f";
        ctx.fillRect(Math.floor(x * width) + col * 4, Math.floor(y * height) + row * 4, 3, 3);
      }
    }
  }
}
drawTexture();
addEventListener("resize", drawTexture);
