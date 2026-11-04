const $ = (selector) => document.querySelector(selector);
const escape = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (char) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        char
      ],
  );
const dollars = (value) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(
    Number(value),
  );
const initials = (value) =>
  String(value)
    .split(/\s+/)
    .slice(0, 2)
    .map((word) => word[0])
    .join("")
    .toUpperCase();
const labels = {
  lookup_purchase_order: "Read the approved purchase order",
  lookup_receiving: "Read receiving evidence",
  lookup_vendor: "Check the approved vendor master",
  search_prior_payments: "Search the payment register",
  search_policy: "Retrieve control policy",
};
let base = localStorage.getItem("ledgerlens-agent-server") || "";
let health = null,
  cases = [],
  selected = "partial-delivery",
  current = null,
  tab = "findings",
  source = null;
let eventStream = null,
  historyMode = false,
  history = [],
  working = false,
  refreshing = false;

function url(path) {
  return `${base}${path}`;
}
function notice(text) {
  $("#global-notice").textContent = text;
  $("#global-notice").hidden = !text;
}
function announce(text) {
  $("#announcer").textContent = text;
}
function badge(kind, text) {
  return `<span class="badge ${kind}">${escape(text)}</span>`;
}
function cited(ids) {
  return `<div class="citation-row">${ids.map((id) => `<button class="citation" data-source="${escape(id)}">${escape(id)}</button>`).join("")}</div>`;
}

async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(url(path), {
      ...options,
      signal: options.signal || AbortSignal.timeout(20000),
    });
  } catch {
    throw new Error(
      "The workspace server is not reachable. Check the connection and keep the agent server running.",
    );
  }
  const body = await response
    .json()
    .catch(() => ({ detail: "The server returned an unexpected response." }));
  if (!response.ok)
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : JSON.stringify(body.detail),
    );
  return body;
}
function post(path, data) {
  return api(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}
function download(name, text, type = "text/plain") {
  const object = URL.createObjectURL(new Blob([text], { type }));
  const link = document.createElement("a");
  link.href = object;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(object), 1000);
  announce(`Downloaded ${name}.`);
}
function selectedCase() {
  return cases.find((item) => item.id === selected) || cases[0];
}
function closeStream() {
  eventStream?.close();
  eventStream = null;
}

async function connect() {
  closeStream();
  try {
    health = await api("/api/health");
    cases = (await api("/api/cases")).cases;
    $("#connection-label").textContent =
      health.mode === "test_double"
        ? "Test harness connected"
        : health.model_ready
          ? "Local model connected"
          : "Local model unavailable";
    $("#connection-dot").classList.toggle("off", !health.model_ready);
    notice(
      health.mode === "test_double"
        ? "TEST HARNESS CONNECTED — model responses are fixtures. This session is for interface testing, not live inference."
        : health.model_ready
          ? ""
          : health.model_setup_message || "The workspace is connected. Install the local model to run investigations; no API key is required.",
    );
    $("#case-count").textContent = cases.length;
    historyMode = false;
    current = null;
    render();
  } catch (error) {
    health = null;
    $("#connection-label").textContent = "Connect an agent workspace";
    $("#connection-dot").classList.add("off");
    notice(error.message);
    render();
  }
}

function renderQueue() {
  $("#queue-title").textContent = historyMode
    ? "Persisted run history"
    : "Choose an investigation";
  $("#case-list").innerHTML = historyMode
    ? history.length
      ? history
          .map(
            (run) =>
              `<button class="case-card ${current?.id === run.id ? "selected" : ""}" data-run="${run.id}"><div class="card-top"><span>${escape(run.id.slice(0, 8))}</span><span>${new Date(run.created_at).toLocaleDateString()}</span></div><strong>${escape(cases.find((c) => c.id === run.case_id)?.title || "Imported invoice")}</strong><p>${escape((current?.id === run.id ? current.status : run.status).replaceAll("_", " "))}</p></button>`,
          )
          .join("")
      : '<div class="empty-state">No saved runs yet.</div>'
    : cases
        .map(
          (item) =>
            `<button class="case-card ${selected === item.id ? "selected" : ""}" data-case="${item.id}" aria-pressed="${selected === item.id}"><div class="card-top"><span>${escape(item.invoice_number)}</span><span>USD</span></div><strong>${escape(item.title)}</strong><p>${escape(item.subtitle)}</p><div class="card-bottom"><span class="case-amount">${dollars(item.amount)}</span>${badge("waiting", "Sample case")}</div></button>`,
        )
        .join("");
}

function render() {
  renderQueue();
  const item = selectedCase();
  const invoice = current?.invoice;
  const vendor =
    invoice?.vendor.value || item?.vendor || "Invoice investigation";
  const status = current
    ? current.status.replaceAll("_", " ")
    : "Ready to investigate";
  $("#case-header").innerHTML =
    `<div class="case-top"><div class="case-kicker"><span>${current ? "RUN " + current.id.slice(0, 8).toUpperCase() : "SYNTHETIC DEMONSTRATION"}</span><span>${current ? "ROUND " + current.round : "NO RUN STARTED"}</span></div><div class="case-title-line"><div class="vendor-title"><span class="vendor-avatar">${escape(initials(vendor))}</span><div><h2>${escape(vendor)}</h2><small>${escape(invoice?.invoice_number.value || item?.invoice_number || "Upload a supported PDF")}</small></div></div><div class="case-main-amount">${dollars(invoice?.total.value || item?.amount || 0)}<small>INVOICE TOTAL · USD</small></div></div><div class="case-subbar">${badge(current?.status === "failed" ? "error" : current?.controls?.recommendation === "hold" ? "hold" : current?.status === "running" ? "running" : "waiting", status)}<span class="meta-chip">${current?.synthetic === false ? "Imported PDF" : "Synthetic source records"}</span>${current ? `<span class="meta-chip">${escape(current.model)}</span>` : ""}${!current && item ? `<button class="button primary small" id="start-run" ${!health?.model_ready || working ? "disabled" : ""}>Start investigation →</button>` : ""}</div></div>`;
  const sources = current?.controls?.sources || {};
  $("#source-count").textContent = Object.keys(sources).length || "";
  document.querySelectorAll("[data-tab]").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === tab);
    button.setAttribute("aria-pressed", String(button.dataset.tab === tab));
  });
  $("#case-content").innerHTML =
    tab === "sources"
      ? sourceView(sources)
      : tab === "trace"
        ? traceView()
        : findingsView(item);
  renderProgress();
  renderActivity();
}

function findingsView(item) {
  if (!current)
    return `<div class="intro-state"><div class="eyebrow">A COMPLETE INVESTIGATION LOOP</div><h3>${escape(item?.title || "Connect your local agent")}</h3><p>The investigator reads the invoice, chooses evidence tools, and prepares a review pack. A separate control step challenges the result before an identified human can decide.</p><div class="intro-items"><div class="intro-item"><span class="intro-step">INPUT</span><strong>A real invoice PDF</strong><p>Readable text, extracted values, exact source quotes.</p></div><div class="intro-item"><span class="intro-step">INVESTIGATION</span><strong>Five read-only tools</strong><p>Orders, receiving, vendor master, payments, and policy.</p></div><div class="intro-item"><span class="intro-step">CONTROL</span><strong>Computed financial checks</strong><p>Exact arithmetic and explicit evidence requirements.</p></div><div class="intro-item"><span class="intro-step">OUTPUT</span><strong>An actionable review pack</strong><p>Findings, citations, a request draft, and a recorded decision.</p></div></div>${item ? `<a class="button secondary" href="${url("/api/sample/" + item.file)}" target="_blank" rel="noopener">Inspect sample invoice PDF →</a>` : ""}<div class="intro-notice" style="margin-top:20px">The model chooses investigation actions. Computed controls govern the recommendation. Human review is required before a release recommendation; no payment is initiated.</div></div>`;
  if (current.status === "failed" || current.status === "stopped")
    return `<div class="run-banner hold"><div><strong>Investigation stopped safely</strong><p>${escape(current.error)}</p></div></div><p class="small-note">The last graph checkpoint and prior events are retained. Fix the reported prerequisite, then retry.</p><button class="button secondary" id="retry-run">Retry from checkpoint →</button>`;
  if (!current.controls)
    return `<div class="run-banner"><span class="spinner" aria-hidden="true"></span><div><strong>${current.round > 1 ? "Reinvestigating with the new evidence" : "Investigation is running"}</strong><p>The local model may take a few minutes on CPU. Tool choices and results appear as they complete; this screen does not simulate progress.</p></div></div>${current.invoice ? extractedFields() : '<div class="empty-state">Reading and grounding the invoice fields…</div>'}`;
  const controls = current.controls;
  const ready = controls.recommendation === "ready_for_review";
  const banner =
    current.status === "completed"
      ? current.completion.result === "release_recommended"
        ? "Release recommended after human review"
        : "Invoice held by reviewer"
      : ready
        ? "Evidence is consistent. A human decision is still required."
        : `${controls.failed_controls} control${controls.failed_controls !== 1 ? "s" : ""} require attention`;
  let content = `<div class="run-banner ${ready ? "ready" : "hold"}"><div><strong>${escape(banner)}</strong><p>${current.status === "completed" ? "The review pack is finalized. No payment or message has been initiated." : escape(controls.notice)}</p></div></div><div class="metrics"><div class="metric"><small>Receiving-supported value</small><strong>${dollars(controls.receiving_supported_amount)}</strong><span>Support for the invoiced quantities and prices</span></div><div class="metric"><small>Value missing receiving support</small><strong>${dollars(controls.unsupported_amount)}</strong><span>A control measure, not a payment authorization or loss estimate</span></div></div><div class="mini-heading">REQUIRED FINANCIAL CONTROLS</div><div class="control-list">${controls.findings.map((f) => `<div class="control"><div class="control-heading"><h3>${escape(f.title)}</h3>${badge(f.result, f.result === "pass" ? "✓ Consistent" : "Needs attention")}</div><p>${escape(f.detail)}</p>${cited(f.source_ids)}</div>`).join("")}</div>`;
  if (current.memo)
    content += `<div class="memo-box"><h3>Verifier's review summary</h3><p>${escape(current.memo.summary)}</p>${current.memo.findings.map((f) => `<div style="margin-top:10px"><strong style="font-size:10px">${escape(f.title)}</strong><p>${escape(f.explanation)}</p>${cited(f.source_ids)}</div>`).join("")}<small>Model-drafted narrative · Source IDs and recommendation checked · Reviewer should verify the interpretation</small></div>`;
  if (current.status === "awaiting_review")
    content += `<form class="review-box" id="review-form"><h3>Your decision closes the loop.</h3><p>${ready ? "All required checks passed. Review the cited evidence before recommending release." : "Resolve the missing evidence or record a hold. Approval is blocked while a required control fails."}</p><label>Reviewer name<input id="reviewer-name" required minlength="2" maxlength="80" placeholder="Your name"></label><label>Decision note<textarea id="review-note" required minlength="5" maxlength="1000" placeholder="What did you verify, or what evidence is still needed?"></textarea></label><div class="review-buttons"><button class="button primary" type="submit" name="action" value="approve" ${!ready ? "disabled" : ""}>Recommend release ✓</button><button class="button secondary" type="submit" name="action" value="request_evidence" ${current.round >= 3 ? "disabled" : ""}>Request more evidence →</button><button class="button danger" type="submit" name="action" value="hold">Record hold</button></div><div id="review-error" class="error" role="alert" hidden></div><p class="review-note">A reviewer cannot override a failed control. The reviewer name is entered for this demonstration; user authentication is not implemented.</p></form>`;
  if (current.status === "awaiting_evidence")
    content += `<div class="evidence-drop"><strong>The case is waiting for additional evidence.</strong><p>The checkpoint is saved. Add the new receiving report to resume this investigation and rerun the checks. No request has been sent automatically.</p>${current.evidence_error ? `<div class="error" role="alert">${escape(current.evidence_error)}</div>` : ""}${item?.follow_up ? `<a class="button secondary small" href="${url("/api/sample/" + item.follow_up)}" target="_blank" rel="noopener">Get the additional sample receiving report ↓</a>` : ""}<form id="evidence-form" style="margin-top:13px"><label>Additional receiving PDF<input type="file" id="evidence-file" accept="application/pdf,.pdf" required></label><button class="button primary small" type="submit">Add evidence & resume →</button><div id="evidence-error" class="error" role="alert" hidden></div></form></div>`;
  if (current.review_history.length)
    content += `<div class="mini-heading">PRESERVED REVIEW HISTORY</div>${current.review_history.map((d) => `<div class="history-card"><strong>${escape(d.reviewer)} · ${escape(d.action.replaceAll("_", " "))} · Round ${d.round}</strong>${escape(d.note)}<small>${new Date(d.at).toLocaleString()}</small></div>`).join("")}`;
  content += `<div class="export-actions"><button class="button secondary" id="open-request">Evidence-request draft →</button><a class="button secondary" href="${url(`/api/runs/${current.id}/workpaper.pdf`)}" download>Workpaper PDF ↓</a><button class="button secondary" id="download-pack">Full JSON review pack ↓</button></div>`;
  return content;
}

function extractedFields() {
  const inv = current.invoice;
  return `<div class="mini-heading">EXTRACTED FROM THE ACTUAL PDF</div><div class="extracted-fields">${[
    ["vendor", "Vendor"],
    ["invoice_number", "Invoice number"],
    ["po_number", "Purchase order"],
    ["invoice_date", "Invoice date"],
    ["total", "Invoice total"],
    ["bank_last4", "Bank account suffix"],
  ]
    .map(
      ([key, label]) =>
        `<div class="field"><small>${label}</small><strong>${escape(inv[key].value)}</strong><button data-field="${key}">Inspect page ${inv[key].citation.page} source quote →</button></div>`,
    )
    .join("")}</div>`;
}

function sourceView(sources) {
  if (!current?.invoice)
    return '<div class="empty-state"><strong>The evidence trail starts with a run.</strong>Start an investigation to inspect extracted fields and source records.</div>';
  return (
    extractedFields() +
    Object.values(sources)
      .map(
        (s) =>
          `<div class="source-card"><h3>${escape(s.title)}</h3><p>${escape(s.kind.replaceAll("_", " "))} · ${escape(s.source_id)}</p><button class="button secondary" data-source="${escape(s.source_id)}">Inspect source →</button></div>`,
      )
      .join("")
  );
}

function traceView() {
  if (!current?.events.length)
    return '<div class="empty-state"><strong>No execution has started.</strong>The trace will contain actual model task choices, tool inputs and outputs, validation returns, and reviewer decisions.</div>';
  return current.events
    .map(
      (event) =>
        `<details class="trace-entry"><summary>${event.stage ? "Stage " + event.stage + " · " : ""}${escape(event.kind)} · ${escape(event.title)}</summary><pre>${escape(JSON.stringify({ at: event.created_at, ...event.data }, null, 2))}</pre></details>`,
    )
    .join("");
}

function renderProgress() {
  const allEvents = current?.events || [];
  const start =
    current?.round > 1
      ? allEvents.findLastIndex((e) => e.kind === "evidence")
      : 0;
  const events = allEvents.slice(Math.max(0, start));
  const last = events.filter((e) => e.stage > 0).at(-1);
  document.querySelectorAll("[data-stage]").forEach((element) => {
    const number = Number(element.dataset.stage);
    const complete =
      events.some((e) => e.stage === number && e.kind === "completed") ||
      (number === 1 && events.some((e) => e.kind === "evidence")) ||
      (number === 2 &&
        events.some((e) => e.kind === "plan" && e.data.action === "finish")) ||
      (number < 4 && current?.controls);
    const active =
      !!current &&
      (current.status === "running"
        ? number === (last?.stage || 1)
        : ["awaiting_review", "awaiting_evidence"].includes(current.status) &&
          number === 4);
    element.classList.toggle("complete", !!complete);
    element.classList.toggle("active", active);
    element.querySelector(".stage-check").textContent = complete
      ? "✓"
      : active
        ? "•"
        : "";
  });
}

function renderActivity() {
  $("#activity-state").textContent =
    current?.status === "running"
      ? "● Running"
      : current?.status === "awaiting_evidence"
        ? "Waiting for evidence"
        : current?.status === "awaiting_review"
          ? "Human review"
          : current?.status === "completed"
            ? "Complete"
            : "Ready";
  $("#activity").innerHTML = current?.events.length
    ? current.events
        .map(
          (event) =>
            `<div class="activity-event ${event.kind === "error" ? "error" : ""}"><time>${new Date(event.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}${event.stage ? " · STAGE " + event.stage : ""}</time><strong>${escape(labels[event.title] || event.title)}</strong>${event.kind === "tool" ? `<small>${escape((event.data.result?.source_ids || []).join(" · ") || "Query result recorded")}</small>` : event.data.action ? `<small>${escape(event.data.action)}</small>` : ""}</div>`,
        )
        .join("")
    : '<div class="activity-empty"><span style="font-size:25px">◇</span><strong>Every step leaves a trace.</strong>Start an investigation to follow tool calls, computed checks, and review decisions as they happen.</div>';
  if (current?.status === "running")
    $("#activity").scrollTop = $("#activity").scrollHeight;
}

async function loadRun(id, watch = true) {
  if (refreshing) return;
  refreshing = true;
  try {
    current = await api("/api/runs/" + id);
    selected = current.case_id || selected;
    render();
    if (watch && current.status === "running") watchRun(id);
  } catch (error) {
    notice(error.message);
  } finally {
    refreshing = false;
  }
}

function watchRun(id) {
  closeStream();
  const after = current?.events.at(-1)?.seq || 0;
  eventStream = new EventSource(url(`/api/runs/${id}/events?after=${after}`));
  eventStream.onmessage = () => loadRun(id, false);
  eventStream.addEventListener("state", () => {
    closeStream();
    loadRun(id, false);
  });
  eventStream.onerror = () => {
    closeStream();
    setTimeout(() => {
      if (current?.id === id) loadRun(id, true);
    }, 1500);
  };
}

async function startCase() {
  if (working) return;
  working = true;
  render();
  try {
    const result = await post("/api/runs", { case_id: selected });
    await loadRun(result.id);
    announce("Investigation started.");
  } catch (error) {
    notice(error.message);
  } finally {
    working = false;
    render();
  }
}

function showSource(id, field = null) {
  const record =
    current?.controls?.sources[id] ||
    (id === current?.document?.source_id
      ? {
          ...current.document,
          title: current.document.filename,
          kind: "invoice_pdf",
          document_id: current.document.id,
        }
      : null);
  if (!record) return;
  $("#source-title").textContent = record.title || id;
  let body = `<p class="small-note">${escape(record.kind.replaceAll("_", " "))} · ${escape(id)}</p>`;
  if (field)
    body += `<div class="notice">Extracted value: <strong>${escape(field.value)}</strong><br>Exact source quote, page ${field.citation.page}: “${escape(field.citation.quote)}”</div>`;
  if (record.pages)
    body += record.pages
      .map(
        (page, i) =>
          `<div class="mini-heading">PAGE ${i + 1}</div><div class="source-page">${field && i + 1 === field.citation.page ? escape(page).replace(escape(field.citation.quote), "<mark>" + escape(field.citation.quote) + "</mark>") : escape(page)}</div>`,
      )
      .join("");
  else
    body += `<pre class="source-json">${escape(JSON.stringify(record, null, 2))}</pre>`;
  if (record.document_id)
    body += `<a class="button secondary" href="${url("/api/documents/" + record.document_id)}" target="_blank" rel="noopener">Open the original PDF →</a>`;
  $("#source-body").innerHTML = body;
  $("#source-dialog").showModal();
}

document.addEventListener("click", async (event) => {
  const caseButton = event.target.closest("[data-case]");
  if (caseButton) {
    closeStream();
    selected = caseButton.dataset.case;
    current = null;
    tab = "findings";
    historyMode = false;
    render();
    return;
  }
  const runButton = event.target.closest("[data-run]");
  if (runButton) {
    closeStream();
    tab = "findings";
    await loadRun(runButton.dataset.run);
    return;
  }
  const tabButton = event.target.closest("[data-tab]");
  if (tabButton) {
    tab = tabButton.dataset.tab;
    render();
    return;
  }
  const sourceButton = event.target.closest("[data-source]");
  if (sourceButton) {
    showSource(sourceButton.dataset.source);
    return;
  }
  const fieldButton = event.target.closest("[data-field]");
  if (fieldButton) {
    showSource(
      current.document.source_id,
      current.invoice[fieldButton.dataset.field],
    );
    return;
  }
  if (event.target.closest("#start-run")) startCase();
  if (event.target.closest("#open-request")) {
    $("#request-text").value = current.memo.client_request;
    $("#request-dialog").showModal();
  }
  if (event.target.closest("#download-pack")) {
    try {
      const pack = await api(`/api/runs/${current.id}/pack`);
      download(
        "ledgerlens-investigation.json",
        JSON.stringify(pack, null, 2),
        "application/json",
      );
    } catch (error) {
      notice(error.message);
    }
  }
  if (event.target.closest("#retry-run")) {
    try {
      await post(`/api/runs/${current.id}/retry`, {});
      await loadRun(current.id);
    } catch (error) {
      notice(error.message);
    }
  }
});

document.addEventListener("submit", async (event) => {
  if (event.target.id === "review-form") {
    event.preventDefault();
    if (working) return;
    working = true;
    try {
      await post(`/api/runs/${current.id}/review`, {
        action: event.submitter.value,
        reviewer: $("#reviewer-name").value.trim(),
        note: $("#review-note").value.trim(),
      });
      await loadRun(current.id);
    } catch (error) {
      $("#review-error").textContent = error.message;
      $("#review-error").hidden = false;
    } finally {
      working = false;
    }
  }
  if (event.target.id === "evidence-form") {
    event.preventDefault();
    if (working) return;
    working = true;
    try {
      const form = new FormData();
      form.append("file", $("#evidence-file").files[0]);
      const document = await api("/api/documents", {
        method: "POST",
        body: form,
      });
      await post(`/api/runs/${current.id}/evidence`, {
        document_id: document.id,
      });
      await loadRun(current.id);
    } catch (error) {
      $("#evidence-error").textContent = error.message;
      $("#evidence-error").hidden = false;
    } finally {
      working = false;
    }
  }
});

$("#connection-open").addEventListener("click", () => {
  $("#server-url").value = base;
  $("#connection-dialog").showModal();
});
$("#connection-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const value = $("#server-url").value.trim().replace(/\/$/, "");
  if (value) {
    const parsed = new URL(value);
    if (
      !["http:", "https:"].includes(parsed.protocol) ||
      parsed.username ||
      parsed.password
    ) {
      notice("Use a plain HTTP or HTTPS server URL without credentials.");
      return;
    }
  }
  base = value;
  localStorage.setItem("ledgerlens-agent-server", base);
  $("#connection-dialog").close();
  await connect();
});
$("#architecture-open").addEventListener("click", () =>
  $("#architecture-dialog").showModal(),
);
$("#upload-open").addEventListener("click", () => {
  $("#upload-error").hidden = true;
  $("#upload-dialog").showModal();
});
$("#upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (working) return;
  working = true;
  try {
    const form = new FormData();
    form.append("file", $("#invoice-file").files[0]);
    const document = await api("/api/documents", {
      method: "POST",
      body: form,
    });
    const result = await post("/api/runs", { document_id: document.id });
    $("#upload-dialog").close();
    current = null;
    tab = "findings";
    await loadRun(result.id);
  } catch (error) {
    $("#upload-error").textContent = error.message;
    $("#upload-error").hidden = false;
  } finally {
    working = false;
  }
});
$("#request-download").addEventListener("click", () =>
  download("ledgerlens-evidence-request.txt", $("#request-text").value),
);
$("#history-nav").addEventListener("click", async () => {
  try {
    history = (await api("/api/runs")).runs;
    historyMode = true;
    renderQueue();
  } catch (error) {
    notice(error.message);
  }
});
$("#cases-nav").addEventListener("click", () => {
  historyMode = false;
  renderQueue();
});
document
  .querySelectorAll(".close-dialog")
  .forEach((button) =>
    button.addEventListener("click", () => button.closest("dialog").close()),
  );
connect();
