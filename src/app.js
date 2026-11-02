import {
  importCSV,
  analyze,
  applyDecisions,
  summarize,
  money,
  reviewCSV,
  clientRequest,
  RULE_VERSION,
  MAX_BYTES,
} from "./engine.js";

const $ = (selector) => document.querySelector(selector);
const escape = (value) =>
  String(value).replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const labels = {
  ready: "Matched",
  review: "Needs review",
  missing: "Missing evidence",
  approved: "Confirmed",
  excluded: "Excluded",
  requested: "Evidence requested",
};
let state = {
  bank: [],
  receipts: [],
  analysis: [],
  decisions: {},
  selected: null,
  filter: "all",
  search: "",
  client: "Cedar & Finch Studio",
  demo: true,
  windowDays: 3,
};
let busy = false;
const badge = (status) =>
  `<span class="badge ${status}">${{ ready: "✓", approved: "✓", review: "◌", missing: "○", excluded: "–", requested: "→" }[status]} ${labels[status]}</span>`;
const dateLabel = (value) =>
  new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "2-digit",
    timeZone: "UTC",
  }).format(new Date(value + "T00:00:00Z"));
const initials = (value) =>
  value
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((x) => x[0])
    .join("")
    .toUpperCase();
function rows() {
  return applyDecisions(state.analysis, state.decisions);
}
function announce(text) {
  $("#status-message").textContent = text;
}
function openDialog(selector) {
  $(selector).showModal();
}
function download(filename, text, type = "text/plain") {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  announce(`Downloaded ${filename}.`);
}

function render() {
  const all = rows(),
    summary = summarize(all);
  $("#stats").innerHTML =
    `<div class="stat featured"><div class="stat-top">Evidence accounted for <span class="stat-symbol">◈</span></div><div class="stat-value">${summary.resolved}<small>/ ${summary.total}</small></div><div class="stat-bottom"><strong>${summary.ready} matched or confirmed</strong>${summary.excluded ? ` · ${summary.excluded} excluded` : " · No exclusions"}</div><div class="progress-track"><div class="progress-fill" style="width:${summary.total ? (summary.resolved / summary.total) * 100 : 0}%"></div></div></div><div class="stat"><div class="stat-top">Items needing attention <span class="stat-symbol">◌</span></div><div class="stat-value">${summary.outstanding.toString().padStart(2, "0")}</div><div class="stat-bottom">${summary.review} to review <span>·</span> ${summary.missing} missing / requested</div></div><div class="stat"><div class="stat-top">Outstanding evidence value <span class="stat-symbol">→</span></div><div class="stat-value">${money(summary.exposure)}</div><div class="stat-bottom">Absolute value of unresolved transactions</div></div>`;
  $("#total-count").textContent = summary.total;
  $("#nav-count").textContent = summary.total;
  $("#all-count").textContent = summary.total;
  $("#open-count").textContent = summary.outstanding;
  $("#resolved-count").textContent = summary.resolved;
  $("#client-name").textContent = state.client;
  $("#dataset-description").textContent = state.demo
    ? "September 2026 · USD · Synthetic sample data"
    : `${all.length} bank transactions · ${state.receipts.length} receipt records · USD`;
  $("#demo-tag").textContent = state.demo ? "DEMO DATA" : "IMPORTED DATA";
  document.querySelectorAll("[data-filter]").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.filter === state.filter);
    btn.setAttribute(
      "aria-pressed",
      String(btn.dataset.filter === state.filter),
    );
  });
  const visible = all.filter(
    (t) =>
      (state.filter === "all" ||
        (state.filter === "resolved") ===
          ["ready", "approved", "excluded"].includes(t.status)) &&
      `${t.merchant} ${t.id}`
        .toLowerCase()
        .includes(state.search.toLowerCase()),
  );
  if (!visible.some((t) => t.id === state.selected))
    state.selected = visible[0]?.id || null;
  $("#transaction-list").innerHTML = visible.length
    ? visible
        .map(
          (t) =>
            `<button class="transaction ${t.id === state.selected ? "selected" : ""}" data-id="${escape(t.id)}" aria-pressed="${t.id === state.selected}"><span class="merchant-icon" aria-hidden="true">${escape(initials(t.merchant))}</span><span class="merchant-info"><span class="merchant-name">${escape(t.merchant)}</span><span class="transaction-meta">${dateLabel(t.date)} · ${escape(t.id)}</span></span><span class="transaction-end"><span class="transaction-amount">${money(t.amount)}</span>${badge(t.status)}</span></button>`,
        )
        .join("")
    : '<div class="empty-state"><strong>No transactions here.</strong>Try a different filter or merchant search.</div>';
  $("#visible-count").textContent =
    `Showing ${visible.length} of ${all.length} transactions`;
  renderDetail(all.find((t) => t.id === state.selected));
}

function renderDetail(tx) {
  if (!tx) {
    $("#detail").innerHTML =
      '<div class="empty-state">Select a transaction to inspect its evidence.</div>';
    return;
  }
  const decision = tx.decision;
  const evidence = tx.candidates
    .map(
      (r) =>
        `<div class="evidence-card"><span class="doc-icon" aria-hidden="true">▤</span><div class="evidence-info"><strong>${escape(r.reference)}</strong><small>${escape(r.id)} · Receipts CSV row ${r.row} · ${escape(r.merchant)}</small><small>${dateLabel(r.date)} · ${r.daysApart} day${r.daysApart !== 1 ? "s" : ""} apart · ${r.exact ? "Exact merchant" : "Partial merchant"}</small></div><span class="evidence-amount">${money(r.amount)}<small>${tx.matchedId === r.id ? "✓ Allocated" : "Candidate"}</small></span></div>`,
    )
    .join("");
  $("#detail").innerHTML =
    `<div class="detail-kicker"><span>TRANSACTION DETAILS</span><span>${escape(tx.id)}</span></div><div class="detail-heading"><span class="merchant-icon" aria-hidden="true">${escape(initials(tx.merchant))}</span><div><h3>${escape(tx.merchant)}</h3><small>${escape(tx.date)} · Bank CSV row ${tx.row}</small></div><div class="detail-amount">${money(tx.amount)}<small>${tx.amount < 0 ? "REFUND" : "EXPENSE"} · USD</small></div></div><div class="reason-box ${tx.status}">${badge(tx.status)}<p>${escape(tx.reason)}</p></div><div class="mini-title">MATCHING RULES · V${RULE_VERSION}</div><div class="rule-list"><span class="rule-pill">Exact signed amount</span><span class="rule-pill">± ${state.windowDays} day${state.windowDays !== 1 ? "s" : ""}</span><span class="rule-pill">Merchant overlap ≥ 50%</span></div><div class="mini-title">${tx.candidates.length ? `SUPPORTING EVIDENCE · ${tx.candidates.length} CANDIDATE${tx.candidates.length !== 1 ? "S" : ""}` : "SUPPORTING EVIDENCE"}</div>${evidence || '<div class="no-evidence"><span>▤</span>No receipt meets all matching rules.</div>'}<p class="reference-note">References point to imported metadata. Documents have not been uploaded or verified.</p>${decision ? `<div class="decision-note"><strong>${labels[tx.status]} by reviewer${decision.receiptId ? ` · ${escape(decision.receiptId)}` : ""}</strong>${escape(decision.note)}<small>${escape(new Date(decision.at).toLocaleString())} · This browser session</small><button class="text-button" id="undo-decision">↶ Undo reviewer decision</button></div>` : `<form class="review-form" id="decision-form"><div class="mini-title">REVIEWER DECISION</div>${tx.candidates.length ? `<label>Receipt to confirm<select id="candidate-id">${tx.candidates.map((r) => `<option value="${escape(r.id)}">${escape(r.id)} — ${escape(r.reference)}</option>`).join("")}</select></label>` : ""}<label>Reviewer note <textarea id="review-note" maxlength="1000" minlength="5" placeholder="What did you verify, or what should happen next?" required></textarea></label><div class="review-actions">${tx.candidates.length ? '<button class="button primary" type="submit" name="action" value="approve">Confirm receipt ✓</button>' : ""}<button class="button secondary" type="submit" name="action" value="request">Mark requested →</button><button class="button secondary" type="submit" name="action" value="exclude">Exclude with reason</button></div><div class="error-box" id="decision-error" role="alert" hidden></div><p class="mini-notice">${tx.status === "ready" ? "Matched by rules; confirm after inspecting the underlying document. " : ""}Exclusions require your judgment. Requesting evidence keeps the item open.</p></form>`}`;
  $("#decision-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    const error = $("#decision-error");
    error.hidden = true;
    try {
      const next = {
        ...state.decisions,
        [tx.id]: {
          action: event.submitter.value,
          note: $("#review-note").value.trim(),
          receiptId:
            event.submitter.value === "approve"
              ? $("#candidate-id").value
              : null,
          at: new Date().toISOString(),
        },
      };
      applyDecisions(state.analysis, next);
      state.decisions = next;
      render();
      announce(`Decision recorded for ${tx.id}.`);
    } catch (e) {
      error.textContent = e.message;
      error.hidden = false;
    }
  });
  $("#undo-decision")?.addEventListener("click", () => {
    delete state.decisions[tx.id];
    render();
    announce(`Decision undone for ${tx.id}.`);
  });
}

async function loadDemo() {
  if (busy) return;
  busy = true;
  try {
    const responses = await Promise.all(
      ["bank", "receipts"].map((x) => fetch(`./samples/${x}.csv`)),
    );
    if (responses.some((r) => !r.ok))
      throw new Error(
        "The sample files could not be loaded. Start the app with npm start, or import your own CSVs.",
      );
    const texts = await Promise.all(responses.map((r) => r.text()));
    const bank = importCSV(texts[0], "bank"),
      receipts = importCSV(texts[1], "receipts");
    state = {
      bank,
      receipts,
      analysis: analyze(bank, receipts),
      decisions: {},
      selected: "B004",
      filter: "all",
      search: "",
      client: "Cedar & Finch Studio",
      demo: true,
      windowDays: 3,
    };
    $("#search").value = "";
    render();
    announce("Loaded synthetic demo: 12 transactions and 10 receipt records.");
  } catch (e) {
    $("#transaction-list").innerHTML =
      `<div class="error-box" role="alert">${escape(e.message)}</div>`;
    $("#detail").innerHTML =
      '<div class="empty-state">Import CSVs to start a review.</div>';
  } finally {
    busy = false;
  }
}

$("#transaction-list").addEventListener("click", (event) => {
  const button = event.target.closest("[data-id]");
  if (button) {
    state.selected = button.dataset.id;
    render();
  }
});
document.querySelectorAll("[data-filter]").forEach((button) =>
  button.addEventListener("click", () => {
    state.filter = button.dataset.filter;
    render();
  }),
);
$("#search").addEventListener("input", (event) => {
  state.search = event.target.value;
  render();
});
$("#import-open").addEventListener("click", () => {
  if (busy) return;
  $("#import-error").hidden = true;
  openDialog("#import-dialog");
});
$("#export-open").addEventListener("click", () => openDialog("#export-dialog"));
$("#nav-guide").addEventListener("click", () => openDialog("#guide-dialog"));
$("#nav-review").addEventListener("click", () => {
  state.filter = "all";
  state.search = "";
  $("#search").value = "";
  render();
});
$("#reset-demo").addEventListener("click", () => {
  if (busy) return;
  if (
    (!state.demo || Object.keys(state.decisions).length) &&
    !confirm(
      "Reset to synthetic demo data? This clears the current imports and reviewer decisions. Download your review first if needed.",
    )
  )
    return;
  loadDemo();
});
document.querySelectorAll(".close-dialog").forEach((button) =>
  button.addEventListener("click", () => {
    if (!busy) button.closest("dialog").close();
  }),
);
document.querySelectorAll("dialog").forEach((dialog) =>
  dialog.addEventListener("cancel", (event) => {
    if (busy) event.preventDefault();
  }),
);
$("#request-open").addEventListener("click", () => {
  $("#request-text").value = clientRequest(rows(), state.client);
  openDialog("#request-dialog");
});
$("#download-request").addEventListener("click", () =>
  download("ledgerlens-client-request.txt", $("#request-text").value),
);
$("#download-csv").addEventListener("click", () =>
  download(
    "ledgerlens-review.csv",
    reviewCSV(rows()),
    "text/csv;charset=utf-8",
  ),
);
$("#download-json").addEventListener("click", () =>
  download(
    "ledgerlens-review.json",
    JSON.stringify(
      {
        schemaVersion: 1,
        ruleVersion: RULE_VERSION,
        generatedAt: new Date().toISOString(),
        client: state.client,
        synthetic: state.demo,
        settings: { currency: "USD", dateToleranceDays: state.windowDays },
        sources: { bank: state.bank, receipts: state.receipts },
        decisions: state.decisions,
        summary: summarize(rows()),
        results: rows(),
      },
      null,
      2,
    ),
    "application/json",
  ),
);
$("#import-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (busy) return;
  const error = $("#import-error"),
    button = $("#import-submit");
  error.hidden = true;
  busy = true;
  button.disabled = true;
  button.textContent = "Validating…";
  try {
    const bankFile = $("#bank-file").files[0],
      receiptFile = $("#receipt-file").files[0];
    if (!bankFile || !receiptFile) throw new Error("Choose both CSV files.");
    if (bankFile.size > MAX_BYTES || receiptFile.size > MAX_BYTES)
      throw new Error("Each CSV must be 500 KB or smaller.");
    const texts = await Promise.all([bankFile.text(), receiptFile.text()]);
    const bank = importCSV(texts[0], "bank"),
      receipts = importCSV(texts[1], "receipts"),
      windowDays = Number($("#tolerance").value);
    const analysis = analyze(bank, receipts, windowDays);
    state = {
      bank,
      receipts,
      analysis,
      decisions: {},
      selected: bank[0].id,
      filter: "all",
      search: "",
      client: $("#workspace-name").value.trim() || "Imported review",
      demo: false,
      windowDays,
    };
    $("#search").value = "";
    render();
    $("#import-dialog").close();
    announce(`Imported ${bank.length} transactions. Previous review replaced.`);
  } catch (e) {
    error.textContent = e.message;
    error.hidden = false;
  } finally {
    busy = false;
    button.disabled = false;
    button.textContent = "Validate & review →";
  }
});
$("#transaction-list").innerHTML =
  '<div class="loading">Loading your evidence workspace…</div>';
loadDemo();
