"use strict";

// Draw with the browser's fonts so Cyrillic works in offline PDF downloads.
globalThis.createReportPdf = async function createReportPdf(article) {
  const canvas = document.createElement("canvas");
  canvas.width = 1190;
  canvas.height = 1684;
  const ctx = canvas.getContext("2d");
  const margin = 108;
  const width = canvas.width - 2 * margin;
  const bottom = canvas.height - margin;
  const family = '"Times New Roman", Georgia, serif';
  const ink = "#22252a";
  const muted = "#555c65";
  const colors = { critical: "#a31621", major: "#751d29", minor: "#465466" };
  const pages = [];
  const sections = [];
  let y;

  function startPage() {
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.textBaseline = "top";
    y = margin;
  }

  function rule(top) {
    ctx.fillStyle = "#c4c9cf";
    ctx.fillRect(margin, top, width, 1);
  }

  async function capturePage() {
    const image = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", .95));
    if (!image) throw new Error("Failed to encode PDF page");
    return new Uint8Array(await image.arrayBuffer());
  }

  function rightLabel(label, top, size) {
    ctx.font = `${size}px ${family}`;
    ctx.fillStyle = muted;
    ctx.fillText(label, canvas.width - margin - ctx.measureText(label).width, top);
  }

  async function finishPage() {
    rule(canvas.height - 83);
    rightLabel(String(pages.length + 2), canvas.height - 66, 19);
    pages.push(await capturePage());
    startPage();
  }

  async function text(content, {
    size = 22, bold = false, color = ink, indent = 0, after = 9, keep = 0,
  } = {}) {
    const lineHeight = Math.ceil(size * 1.3);
    const font = `${bold ? "bold " : ""}${size}px ${family}`;
    ctx.font = font;
    const lines = wrappedLines(ctx, content, width - indent);
    const needed = lineHeight * (lines.length + keep) + after;
    if (keep && y > margin && y + Math.min(needed, bottom - margin) > bottom) await finishPage();
    for (const line of lines) {
      if (y + lineHeight > bottom) await finishPage();
      ctx.font = font;
      ctx.fillStyle = color;
      ctx.fillText(line, margin + indent, y);
      y += lineHeight;
    }
    y += after;
  }

  startPage();
  async function tableRow(row) {
    const columnWidths = [150, 185, width - 335];
    const font = `${row.querySelector("th") ? "bold " : ""}20px ${family}`;
    const lineHeight = 26;
    ctx.font = font;
    const cells = Array.from(row.cells, (cell, index) =>
      wrappedLines(ctx, cell.textContent, columnWidths[index] - 20)
    );
    const height = Math.max(...cells.map((lines) => lines.length));
    if (y > margin && y + Math.min(height * lineHeight + 14, bottom - margin) > bottom) {
      await finishPage();
    }
    for (let index = 0; index < height; index++) {
      if (y + lineHeight > bottom) await finishPage();
      ctx.font = font;
      ctx.fillStyle = ink;
      let x = margin + 8;
      for (const [column, lines] of cells.entries()) {
        if (lines[index]) ctx.fillText(lines[index], x, y);
        x += columnWidths[column];
      }
      y += lineHeight;
    }
    rule(y + 2);
    y += 12;
  }

  for (const section of article.querySelectorAll("section")) {
    const heading = section.querySelector("h2").textContent;
    if (y + 125 > bottom) await finishPage();
    sections.push({ heading, page: pages.length + 2, top: y });
    await text(heading, { size: 31, bold: true, after: 10 });
    rule(y);
    y += 17;

    for (const block of section.querySelectorAll("h3, p, summary, blockquote, tr")) {
      if (block.matches("tr")) {
        await tableRow(block);
      } else if (section.id === "passport") {
        const separator = block.textContent.indexOf(" — ");
        await text(block.textContent.slice(0, separator), { color: muted, size: 20, after: 0, keep: 1 });
        await text(block.textContent.slice(separator + 3), { bold: true, after: 13 });
      } else if (block.matches("h3, summary") || block.dataset.severity) {
        await text(block.textContent, { bold: true, color: colors[block.dataset.severity] ?? ink, keep: 2 });
      } else if (block.matches("blockquote")) {
        await text(block.textContent, { size: 20, color: muted, indent: 34, after: 12 });
      } else {
        await text(block.textContent);
      }
    }
    y += 30;
  }
  await finishPage();

  y = 300;
  await text("Отчёт о проверке требований", { size: 52, bold: true, after: 27 });
  rule(y);
  y += 62;
  await text("Оглавление", { size: 30, bold: true, after: 21 });
  for (const section of sections) {
    section.rowTop = y;
    await text(section.heading, { size: 25, after: 15 });
    rightLabel(String(section.page), section.rowTop, 25);
    rule(y - 8);
    section.rowBottom = y;
  }
  pages.unshift(await capturePage());
  return writePdf(pages, canvas.width, canvas.height, sections);
};

function wrappedLines(ctx, text, width) {
  const lines = [];
  for (const paragraph of text.split(/\r?\n/)) {
    let line = "";
    for (const word of paragraph.trim().split(/\s+/)) {
      const nextLine = line ? `${line} ${word}` : word;
      if (ctx.measureText(nextLine).width <= width) {
        line = nextLine;
        continue;
      }
      if (line) lines.push(line);
      line = "";
      for (const char of word) {
        if (ctx.measureText(line + char).width > width) {
          lines.push(line);
          line = "";
        }
        line += char;
      }
    }
    lines.push(line);
  }
  return lines;
}

function writePdf(pages, width, height, sections) {
  const encoder = new TextEncoder();
  const parts = [];
  const offsets = [0];
  let length = 0;
  function add(value) {
    const bytes = typeof value === "string" ? encoder.encode(value) : value;
    parts.push(bytes);
    length += bytes.length;
  }
  function object(content, stream) {
    add(`${offsets.push(length) - 1} 0 obj\n${content}\n`);
    if (stream) {
      add("stream\n");
      add(stream);
      add("\nendstream\n");
    }
    add("endobj\n");
  }

  add("%PDF-1.4\n");
  object("<< /Type /Catalog /Pages 2 0 R >>");
  const kids = pages.map((_, index) => `${3 + index * 3} 0 R`).join(" ");
  object(`<< /Type /Pages /Count ${pages.length} /Kids [${kids}] >>`);
  // Each A4 page has a drawing stream and one full-page JPEG image.
  const drawing = encoder.encode("q\n595 0 0 842 0 0 cm\n/PageImage Do\nQ");
  for (const [index, image] of pages.entries()) {
    const contentsId = 4 + index * 3;
    const links = index === 0 ? ` /Annots [${sections.map((section) => {
      const pageId = 3 + (section.page - 1) * 3;
      const bottom = 842 - section.rowBottom / 2;
      const top = 842 - section.rowTop / 2;
      return `<< /Type /Annot /Subtype /Link /Rect [54 ${bottom} 541 ${top}] /Border [0 0 0] /Dest [${pageId} 0 R /XYZ null ${842 - section.top / 2} null] >>`;
    }).join(" ")}]` : "";
    object(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents ${contentsId} 0 R /Resources << /XObject << /PageImage ${contentsId + 1} 0 R >> >>${links} >>`);
    object(`<< /Length ${drawing.length} >>`, drawing);
    object(`<< /Type /XObject /Subtype /Image /Width ${width} /Height ${height} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${image.length} >>`, image);
  }

  const xref = length;
  add(`xref\n0 ${offsets.length}\n0000000000 65535 f \n`);
  for (const offset of offsets.slice(1)) add(`${String(offset).padStart(10, "0")} 00000 n \n`);
  add(`trailer\n<< /Size ${offsets.length} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`);
  return new Blob(parts, { type: "application/pdf" });
}
