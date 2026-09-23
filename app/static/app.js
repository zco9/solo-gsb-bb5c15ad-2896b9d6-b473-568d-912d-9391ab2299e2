"use strict";

const MAX_PIECES = 12;

const $ = (sel) => document.querySelector(sel);

const els = {
  newLength: $("#new-length"),
  kerf: $("#kerf"),
  leftoverList: $("#leftover-list"),
  addLeftover: $("#add-leftover"),
  pieceList: $("#piece-list"),
  addPiece: $("#add-piece"),
  pieceTotal: $("#piece-total"),
  solveBtn: $("#solve-btn"),
  formError: $("#form-error"),
  inputCard: $("#input-card"),
  resultArea: $("#result-area"),
  backBtn: $("#back-btn"),
  printBtn: $("#print-btn"),
  printHead: $("#print-head"),
  errorPanel: $("#error-panel"),
  errorText: $("#error-text"),
  overlongList: $("#overlong-list"),
  planPanel: $("#plan-panel"),
  summaryRow: $("#summary-row"),
  bars: $("#bars"),
  unusedPanel: $("#unused-panel"),
  unusedList: $("#unused-list"),
};

/* ---------- 输入行管理 ---------- */

function addLeftoverRow(value = "") {
  const row = document.createElement("div");
  row.className = "row";
  row.innerHTML = `
    <div class="input-wrap">
      <input type="number" step="any" min="0" class="leftover-input" placeholder="如 1250" />
      <span class="unit">mm</span>
    </div>
    <button type="button" class="btn-del" title="删除">✕</button>
  `;
  const input = row.querySelector("input");
  input.value = value;
  row.querySelector(".btn-del").addEventListener("click", () => {
    row.remove();
  });
  els.leftoverList.appendChild(row);
  input.focus();
}

function addPieceRow(length = "", qty = 1) {
  const row = document.createElement("div");
  row.className = "piece-row";
  row.innerHTML = `
    <div class="input-wrap">
      <input type="number" step="any" min="0" class="piece-length" placeholder="裁件长度" />
      <span class="unit">mm</span>
    </div>
    <input type="number" step="1" min="1" class="piece-qty" />
    <span class="cell-total">0 件</span>
    <button type="button" class="btn-del" title="删除">✕</button>
  `;
  const lenInput = row.querySelector(".piece-length");
  const qtyInput = row.querySelector(".piece-qty");
  const cell = row.querySelector(".cell-total");
  lenInput.value = length;
  qtyInput.value = qty;

  const refresh = () => {
    const q = parseInt(qtyInput.value, 10);
    cell.textContent = Number.isFinite(q) && q > 0 ? `${q} 件` : "—";
    updatePieceTotal();
  };
  lenInput.addEventListener("input", refresh);
  qtyInput.addEventListener("input", refresh);
  row.querySelector(".btn-del").addEventListener("click", () => {
    row.remove();
    updatePieceTotal();
  });
  els.pieceList.appendChild(row);
  refresh();
}

function updatePieceTotal() {
  let total = 0;
  els.pieceList.querySelectorAll(".piece-qty").forEach((inp) => {
    const q = parseInt(inp.value, 10);
    if (Number.isFinite(q) && q > 0) total += q;
  });
  els.pieceTotal.textContent = total;
  const wrap = document.querySelector(".piece-count");
  wrap.classList.toggle("over", total > MAX_PIECES);
  return total;
}

/* ---------- 表单收集与校验 ---------- */

function collectRequest() {
  const newLength = parseFloat(els.newLength.value);
  const kerf = parseFloat(els.kerf.value);

  if (!Number.isFinite(newLength) || newLength <= 0) {
    throw new Error("请填写有效的新料定长（大于 0）。");
  }
  if (!Number.isFinite(kerf) || kerf < 0) {
    throw new Error("锯缝宽度必须为不小于 0 的数字。");
  }

  const leftovers = [];
  els.leftoverList.querySelectorAll(".leftover-input").forEach((inp) => {
    const v = inp.value.trim();
    if (v === "") return;
    const n = parseFloat(v);
    if (!Number.isFinite(n) || n <= 0) {
      throw new Error("余料长度必须为大于 0 的数字（空行可不填或删除）。");
    }
    leftovers.push(n);
  });

  const pieces = [];
  els.pieceList.querySelectorAll(".piece-row").forEach((row) => {
    const len = parseFloat(row.querySelector(".piece-length").value);
    const qty = parseInt(row.querySelector(".piece-qty").value, 10);
    if (!Number.isFinite(len) || len <= 0) {
      throw new Error("每行裁件长度必须大于 0。");
    }
    if (!Number.isFinite(qty) || qty <= 0) {
      throw new Error("每行裁件数量必须为正整数。");
    }
    pieces.push({ length: len, qty });
  });

  if (pieces.length === 0) {
    throw new Error("请至少添加一种裁件。");
  }
  const total = pieces.reduce((s, p) => s + p.qty, 0);
  if (total > MAX_PIECES) {
    throw new Error(`裁件总计 ${total} 件，超过上限 ${MAX_PIECES} 件。`);
  }

  return { new_length: newLength, leftovers, kerf, pieces };
}

/* ---------- 渲染 ---------- */

function fmt(n) {
  if (typeof n !== "number") n = parseFloat(n);
  if (Math.abs(n - Math.round(n)) < 1e-6) return String(Math.round(n));
  return n.toFixed(3).replace(/\.?0+$/, "");
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function renderBar(bar) {
  const isNew = bar.bar_type === "new";
  const name = isNew ? `新料 #${bar.new_index}` : `余料 #${bar.bar_index}`;
  const tagClass = isNew ? "tag-new" : "tag-leftover";
  const tagText = isNew ? "新料" : "已有余料";

  // 各段宽度按真实长度比例；锯缝设最小可视宽度，整体由 flex 自动微缩
  const totalLen = bar.bar_length;
  // 实际锯缝数：exact 时 k-1，否则 k
  const kerfNum = bar.exact_last ? bar.pieces.length - 1 : bar.pieces.length;
  const kerfEach = kerfNum > 0 ? bar.kerf_loss / kerfNum : 0;
  const minKerfPct = 1.4;

  let railHtml = "";
  bar.pieces.forEach((p, idx) => {
    const w = (p.length / totalLen) * 100;
    railHtml += `<div class="seg-piece" style="flex:${w.toFixed(3)} 1 0"
      title="裁件 ${fmt(p.length)} mm">${escapeHtml(fmt(p.length))}</div>`;
    if (idx < kerfNum) {
      const kw = Math.max(minKerfPct, (kerfEach / totalLen) * 100);
      railHtml += `<div class="seg-kerf" style="flex:0 0 ${kw.toFixed(3)}%"
        title="锯缝 ${escapeHtml(fmt(kerfEach))} mm"></div>`;
    }
  });
  if (bar.tail > 1e-6) {
    const tw = (bar.tail / totalLen) * 100;
    railHtml += `<div class="seg-tail" style="flex:${tw.toFixed(3)} 1 0"
      title="尾料 ${fmt(bar.tail)} mm">尾料 ${escapeHtml(fmt(bar.tail))}</div>`;
  }

  const piecesDesc = bar.pieces.map((p) => `${fmt(p.length)}`).join(" + ");
  const exactTag = bar.exact_last
    ? `<span class="tag tag-exact">末段恰为裁件 · 免末道锯缝</span>` : "";

  return `
    <div class="bar-card ${isNew ? "is-new" : "is-leftover"}">
      <div class="bar-title">
        <span class="bar-name">${name}</span>
        <span class="tag ${tagClass}">${tagText}</span>
        ${exactTag}
        <span class="bar-len">料长 ${fmt(bar.bar_length)} mm</span>
        <span class="bar-meta">
          锯缝损耗 <b>${fmt(bar.kerf_loss)}</b> mm ·
          尾料 <b>${fmt(bar.tail)}</b> mm
        </span>
      </div>
      <div class="bar-rail">${railHtml}</div>
      <div class="piece-list-line">
        裁切顺序：${escapeHtml(piecesDesc)}
        （共 ${bar.pieces.length} 件，锯缝 ${kerfNum} 道）
      </div>
    </div>
  `;
}

function renderSummary(data) {
  const s = data.summary;
  const stats = [
    { k: "使用新料", v: `${s.new_bar_count} 根` },
    { k: "动用余料", v: `${s.used_leftover_count} 根` },
    { k: "动用原料合计", v: `${s.bar_count} 根` },
    { k: "裁件总长度", v: `${fmt(s.total_piece_length)} mm` },
    { k: "锯缝总损耗", v: `${fmt(s.total_kerf)} mm` },
    { k: "尾料总长", v: `${fmt(s.total_tail)} mm` },
  ];
  els.summaryRow.innerHTML = stats.map((st) =>
    `<div class="stat"><div class="v">${st.v}</div><div class="k">${st.k}</div></div>`
  ).join("");
}

function renderPrintHead(data) {
  const i = data.inputs;
  const now = new Date();
  const pad = (x) => String(x).padStart(2, "0");
  const ts = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ` +
             `${pad(now.getHours())}:${pad(now.getMinutes())}`;
  const piecesDesc = i.pieces.map((p) => `${fmt(p.length)}×${p.qty}`).join("，");
  const leftDesc = i.leftovers.length
    ? i.leftovers.map((l) => fmt(l)).join("、") : "无";
  els.printHead.innerHTML = `
    <h1>木作裁条裁切方案</h1>
    <div class="meta">
      生成时间：${ts} ｜ 新料定长：${fmt(i.new_length)} mm ｜
      锯缝：${fmt(i.kerf)} mm ｜ 余料：${escapeHtml(leftDesc)} ｜
      裁件：${escapeHtml(piecesDesc)}
    </div>
  `;
}

function renderError(data) {
  els.planPanel.hidden = true;
  els.errorPanel.hidden = false;
  els.errorText.textContent = data.message || "当前输入无法生成方案。";
  if (data.overlong && data.overlong.length) {
    const rows = data.overlong.map((o) =>
      `<tr><td>第 ${o.order} 行</td><td>${fmt(o.length)} mm</td></tr>`
    ).join("");
    els.overlongList.innerHTML = `
      <p>以下裁件比最长的原料还长（且未长到恰好等于料长），
      即使单放一根原料、只切一件也排不下：</p>
      <table class="overlong-table">
        <thead><tr><th>裁件输入行</th><th>裁件长度</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
      <p class="note">请更换更长的原料，或修改该裁件长度后再试。</p>
    `;
  } else {
    els.overlongList.innerHTML = "";
  }
}

function renderPlan(data) {
  els.errorPanel.hidden = true;
  els.planPanel.hidden = false;
  renderSummary(data);
  els.bars.innerHTML = data.bars.map(renderBar).join("");

  const unused = data.summary.unused_leftover_indices;
  if (unused && unused.length) {
    els.unusedPanel.hidden = false;
    els.unusedList.innerHTML = unused.map((idx) => {
      const len = data.inputs.leftovers[idx - 1];
      return `<span class="unused-chip">#${idx}（${fmt(len)} mm）</span>`;
    }).join("");
  } else {
    els.unusedPanel.hidden = true;
  }
}

/* ---------- 提交 ---------- */

async function onSolve() {
  els.formError.textContent = "";
  let payload;
  try {
    payload = collectRequest();
  } catch (e) {
    els.formError.textContent = e.message;
    return;
  }

  els.solveBtn.disabled = true;
  const oldText = els.solveBtn.textContent;
  els.solveBtn.textContent = "计算中…";

  try {
    const resp = await fetch("/api/solve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await resp.json();
    if (!resp.ok) {
      const detail = typeof data.detail === "string"
        ? data.detail
        : (data.detail && data.detail[0] && data.detail[0].msg) || "请求参数有误。";
      throw new Error(detail);
    }
    renderPrintHead(data);
    els.inputCard.hidden = true;
    els.resultArea.hidden = false;
    if (data.feasible) renderPlan(data);
    else renderError(data);
    window.scrollTo({ top: 0, behavior: "smooth" });
  } catch (e) {
    els.formError.textContent = e.message;
  } finally {
    els.solveBtn.disabled = false;
    els.solveBtn.textContent = oldText;
  }
}

/* ---------- 初始化 ---------- */

els.addLeftover.addEventListener("click", () => addLeftoverRow());
els.addPiece.addEventListener("click", () => addPieceRow());
els.solveBtn.addEventListener("click", onSolve);
els.backBtn.addEventListener("click", () => {
  els.resultArea.hidden = true;
  els.inputCard.hidden = false;
  window.scrollTo({ top: 0, behavior: "smooth" });
});
els.printBtn.addEventListener("click", () => window.print());

// 默认示例：2 根余料 + 2 种裁件
addLeftoverRow(1200);
addLeftoverRow(800);
addPieceRow(800, 2);
addPieceRow(600, 3);
updatePieceTotal();
