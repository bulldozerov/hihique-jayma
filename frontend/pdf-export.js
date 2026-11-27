"use strict";

// Draw with the browser's fonts so Cyrillic works in offline PDF downloads.
globalThis.createReportPdf = async function createReportPdf(article) {
  const canvas = document.createElement("canvas");
  canvas.width = 1190;
  canvas.height = 1684;
  const ctx = canvas.getContext("2d");
  const margin = 90;
  const width = canvas.width - 2 * margin;
  const pages = [];
  let y;

  function startPage() {
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#141415";
    ctx.textBaseline = "top";
    y = margin;
  }

  async function savePage() {
    ctx.font = "22px system-ui";
    ctx.fillText(String(pages.length + 1), margin, canvas.height - 60);
    const image = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", .92));
    if (!image) throw new Error("Failed to encode PDF page");
    pages.push(new Uint8Array(await image.arrayBuffer()));
  }

  startPage();
  for (const block of article.querySelectorAll("h1, h2, h3, p, summary, blockquote")) {
    const heading = block.matches("h1, h2, h3");
    const quote = block.matches("blockquote");
    const size = block.matches("h1") ? 49 : block.matches("h2") ? 38 : quote ? 25 : 29;
    const lineHeight = Math.ceil(size * 1.34);
    const font = `${heading || block.matches("summary") ? "bold " : ""}${size}px system-ui`;
    const indent = quote ? 24 : 0;
    ctx.font = font;
    const lines = wrappedLines(ctx, block.textContent, width - indent);
    if (heading && y + lineHeight * (lines.length + 2) > canvas.height - margin) {
      await savePage();
      startPage();
    }
    for (const line of lines) {
      if (y + lineHeight > canvas.height - margin) {
        await savePage();
        startPage();
      }
      ctx.font = font;
      ctx.fillStyle = quote ? "#47474a" : "#141415";
      ctx.fillText(line, margin + indent, y);
      y += lineHeight;
    }
    y += heading ? 17 : 11;
  }
  await savePage();
  return writePdf(pages, canvas.width, canvas.height);
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

function writePdf(pages, width, height) {
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
    object(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents ${contentsId} 0 R /Resources << /XObject << /PageImage ${contentsId + 1} 0 R >> >> >>`);
    object(`<< /Length ${drawing.length} >>`, drawing);
    object(`<< /Type /XObject /Subtype /Image /Width ${width} /Height ${height} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${image.length} >>`, image);
  }

  const xref = length;
  add(`xref\n0 ${offsets.length}\n0000000000 65535 f \n`);
  for (const offset of offsets.slice(1)) add(`${String(offset).padStart(10, "0")} 00000 n \n`);
  add(`trailer\n<< /Size ${offsets.length} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`);
  return new Blob(parts, { type: "application/pdf" });
}
