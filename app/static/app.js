const $ = (s) => document.querySelector(s);

// ---------- 工具函数 ----------
function fmt(x) {
  const v = Math.round(Number(x) * 1000) / 1000;
  return String(v);
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function groupPieces(pieces) {
  const map = new Map();
  pieces.forEach((x) => map.set(x, (map.get(x) || 0) + 1));
  return [...map.entries()]
    .map(([l, q]) => (q > 1 ? `${fmt(l)} mm × ${q} 件` : `${fmt(l)} mm × 1 件`))
    .join("、");
}

// ---------- 动态输入行 ----------
function addRemnantRow(value = "") {
  const row = document.createElement("div");
  row.className = "row";
  row.innerHTML = `
    <input type="number" class="remnant-length" min="1" step="any" placeholder="余料长度（mm）" value="${value}" />
    <span class="unit">mm</span>
    <button type="button" class="remove" title="删除该行">×</button>`;
  row.querySelector(".remove").addEventListener("click", () => row.remove());
  $("#remnant-list").appendChild(row);
}

function addPieceRow(length = "", qty = 1) {
  const row = document.createElement("div");
  row.className = "row";
  row.innerHTML = `
    <input type="number" class="piece-length" min="1" step="any" placeholder="裁件长度（mm）" value="${length}" />
    <span class="unit">mm ×</span>
    <input type="number" class="piece-qty" min="1" max="12" step="1" value="${qty}" />
    <span class="unit">件</span>
    <button type="button" class="remove" title="删除该行">×</button>`;
  row.querySelector(".remove").addEventListener("click", () => {
    row.remove();
    updatePieceTotal();
  });
  row.querySelector(".piece-qty").addEventListener("input", updatePieceTotal);
  $("#piece-list").appendChild(row);
  updatePieceTotal();
}

function updatePieceTotal() {
  let total = 0;
  document.querySelectorAll(".piece-qty").forEach((el) => {
    total += parseInt(el.value || "0", 10) || 0;
  });
  const el = $("#piece-total");
  el.textContent = total;
  el.classList.toggle("over", total > 12);
}

function gather() {
  const stock = parseFloat($("#stock-length").value);
  const kerf = parseFloat($("#kerf").value);
  if (!(stock > 0)) throw new Error("请填写有效的新料定长（正数）。");
  if (!(kerf >= 0)) throw new Error("请填写有效的锯缝宽度（≥ 0）。");

  const remnants = [];
  let bad = false;
  document.querySelectorAll(".remnant-length").forEach((el) => {
    if (el.value.trim() === "") return;
    const v = parseFloat(el.value);
    if (!(v > 0)) bad = true;
    remnants.push(v);
  });
  if (bad) throw new Error("余料长度必须为正数。");

  const pieces = [];
  let total = 0;
  document.querySelectorAll("#piece-list .row").forEach((row) => {
    const len = parseFloat(row.querySelector(".piece-length").value);
    const qty = parseInt(row.querySelector(".piece-qty").value, 10);
    if (!(len > 0) || !(qty >= 1)) throw new Error("请为每行裁件填写有效的长度（正数）和数量（≥ 1）。");
    total += qty;
    pieces.push({ length: len, qty });
  });
  if (pieces.length === 0) throw new Error("请至少添加一条裁件。");
  if (total > 12) throw new Error(`裁件总数为 ${total} 件，超过 12 件上限。`);

  return { stock_length: stock, kerf, remnants, pieces };
}

// ---------- 结果渲染 ----------
function segEl(widthPct, cls, label, title) {
  const d = document.createElement("div");
  d.className = `seg ${cls}`;
  d.style.width = `${widthPct}%`;
  if (label) d.textContent = label;
  if (title) d.title = title;
  return d;
}

function renderResult(data, params) {
  const sec = $("#result-section");
  sec.classList.remove("hidden");

  const totalQty = params.pieces.reduce((a, p) => a + p.qty, 0);
  $("#print-header").innerHTML = `
    <h1>木作裁切方案</h1>
    <p>新料定长 ${fmt(params.stock_length)} mm ｜ 锯缝宽度 ${fmt(params.kerf)} mm
       ｜ 裁件共 ${totalQty} 件 ｜ 生成时间 ${new Date().toLocaleString("zh-CN")}</p>`;

  const errBox = $("#result-error");
  const summaryBox = $("#summary-box");
  const planList = $("#plan-list");
  const unusedBox = $("#unused-box");
  const legend = $("#legend");
  errBox.classList.add("hidden");
  summaryBox.innerHTML = "";
  planList.innerHTML = "";
  unusedBox.innerHTML = "";

  if (!data.ok) {
    legend.classList.add("hidden");
    errBox.classList.remove("hidden");
    let html = `<b>⚠️ 无法生成完整裁切方案</b><br>${escapeHtml(data.error || "")}`;
    if (data.overlong_pieces && data.overlong_pieces.length) {
      html += `<div class="chips">` +
        data.overlong_pieces
          .map((p) => `<span class="chip bad">${fmt(p.length)} mm × ${p.qty}</span>`)
          .join("") +
        `</div>`;
    }
    errBox.innerHTML = html;
    return;
  }
  legend.classList.remove("hidden");

  const s = data.summary;
  summaryBox.innerHTML = `
    <div class="summary">
      <div class="stat"><div class="num">${s.new_stock_used}</div><div class="lbl">新料使用（根）</div></div>
      <div class="stat"><div class="num">${s.remnants_used}</div><div class="lbl">动用余料（根）</div></div>
      <div class="stat"><div class="num">${fmt(s.total_leftover)}</div><div class="lbl">尾料合计（mm）</div></div>
      <div class="stat"><div class="num">${fmt(s.total_kerf_loss)}</div><div class="lbl">锯缝损耗（mm）</div></div>
    </div>`;

  let newIdx = 0;
  let remIdx = 0;
  data.plans.forEach((p) => {
    const card = document.createElement("div");
    card.className = "card plan-card";

    let tag;
    let tagCls;
    if (p.source === "new") {
      newIdx += 1;
      tag = `新料 #${newIdx}`;
      tagCls = "tag-new";
    } else {
      remIdx += 1;
      tag = `余料 #${remIdx}`;
      tagCls = "tag-rem";
    }

    const head = document.createElement("div");
    head.className = "plan-head";
    head.innerHTML =
      `<span class="tag ${tagCls}">${tag}</span>` +
      `<span class="stock-len">原料长度 ${fmt(p.stock_length)} mm</span>`;

    // 条形图：尾料为 0 时锯缝只在裁件之间（n-1 道）；否则每切下一件一道锯缝
    const bar = document.createElement("div");
    bar.className = "bar";
    const S = p.stock_length;
    const n = p.pieces.length;
    p.pieces.forEach((len, i) => {
      bar.appendChild(segEl((len / S) * 100, `piece p${i % 2}`, fmt(len), `裁件 ${fmt(len)} mm`));
      const needKerf = p.leftover > 0 || i < n - 1;
      if (needKerf && params.kerf > 0) {
        bar.appendChild(segEl((params.kerf / S) * 100, "kerf", "", `锯缝 ${fmt(params.kerf)} mm`));
      }
    });
    if (p.leftover > 0) {
      bar.appendChild(segEl((p.leftover / S) * 100, "left", fmt(p.leftover), `尾料 ${fmt(p.leftover)} mm`));
    }

    const detail = document.createElement("div");
    detail.className = "plan-detail";
    detail.innerHTML = `
      <div><b>裁件</b>${groupPieces(p.pieces)}</div>
      <div><b>锯缝损耗</b>${fmt(p.kerf_loss)} mm</div>
      <div><b>尾料</b>${fmt(p.leftover)} mm</div>`;

    card.append(head, bar, detail);
    planList.appendChild(card);
  });

  if (data.unused_remnants && data.unused_remnants.length) {
    unusedBox.innerHTML =
      `<div class="card unused">未使用的余料：` +
      data.unused_remnants.map((r) => `${fmt(r)} mm`).join("、") +
      `（未动用，可留待下次使用）</div>`;
  }
}

// ---------- 事件绑定 ----------
$("#add-remnant").addEventListener("click", () => addRemnantRow());
$("#add-piece").addEventListener("click", () => addPieceRow());

$("#load-example").addEventListener("click", () => {
  $("#stock-length").value = 2440;
  $("#kerf").value = 3;
  $("#remnant-list").innerHTML = "";
  [1250, 700].forEach((v) => addRemnantRow(v));
  $("#piece-list").innerHTML = "";
  [[600, 2], [450, 2], [380, 1], [300, 3]].forEach(([l, q]) => addPieceRow(l, q));
});

$("#clear-all").addEventListener("click", () => {
  $("#stock-length").value = 2440;
  $("#kerf").value = 3;
  $("#remnant-list").innerHTML = "";
  $("#piece-list").innerHTML = "";
  $("#result-section").classList.add("hidden");
  $("#form-error").classList.add("hidden");
  addRemnantRow();
  addPieceRow();
});

$("#print-btn").addEventListener("click", () => window.print());

$("#optimize-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errBox = $("#form-error");
  errBox.classList.add("hidden");

  let payload;
  try {
    payload = gather();
  } catch (err) {
    errBox.textContent = err.message;
    errBox.classList.remove("hidden");
    return;
  }

  let data;
  try {
    const res = await fetch("/api/optimize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    data = await res.json();
    if (!res.ok) {
      const detail = typeof data.detail === "string" ? data.detail : "参数校验未通过，请检查输入。";
      throw new Error(detail);
    }
  } catch (err) {
    errBox.textContent = err.message || "请求失败，请稍后重试。";
    errBox.classList.remove("hidden");
    return;
  }

  renderResult(data, payload);
  $("#result-section").scrollIntoView({ behavior: "smooth", block: "start" });
});

// ---------- 初始行 ----------
addRemnantRow();
addPieceRow();
addPieceRow();
