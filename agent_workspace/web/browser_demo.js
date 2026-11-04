import {getDocument, GlobalWorkerOptions} from "pdfjs-dist";
import {jsPDF} from "jspdf";
import {TOOL_NAMES, invoiceFromPages, executeDemoTool, evaluateDemoControls, receivingFromPages, reviewDecision} from "./browser_controls.js";

GlobalWorkerOptions.workerSrc = new URL("./pdf.worker.min.mjs", import.meta.url).href;
const now = () => new Date().toISOString();
const identifier = () => crypto.randomUUID().replaceAll("-", "");
const copy = (value) => structuredClone(value);

export class BrowserDemo {
  constructor() {
    this.urls = new Map();
    this.ready = this.initialize();
  }
  async initialize() {
    this.catalog = await (await fetch(new URL("./agent_samples/catalog.json", import.meta.url))).json();
    this.db = await new Promise((resolve, reject) => {
      const request = indexedDB.open("ledgerlens-public-workflow", 1);
      request.onupgradeneeded = () => request.result.createObjectStore("workspace");
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(new Error("Browser storage is unavailable. Use a browser with IndexedDB enabled."));
    });
    this.state = await new Promise((resolve, reject) => {
      const r = this.db.transaction("workspace").objectStore("workspace").get("state");
      r.onsuccess = () => resolve(r.result || {documents: {}, runs: {}});
      r.onerror = () => reject(r.error);
    });
    for (const run of Object.values(this.state.runs)) if (run.status === "running") {
      run.status = "stopped"; run.error = "This browser was closed during execution. Retry the saved case.";
    }
  }
  async save() {
    const snapshot = copy(this.state);
    await new Promise((resolve, reject) => {
      const transaction = this.db.transaction("workspace", "readwrite");
      transaction.objectStore("workspace").put(snapshot, "state");
      transaction.oncomplete = resolve;
      transaction.onerror = () => reject(transaction.error);
    });
  }
  emit(run, stage, kind, title, data = {}) {
    run.events.push({seq: run.events.length + 1, stage, kind, title, data, created_at: now()});
    run.updated_at = now();
  }
  async document(file) {
    if (!(file instanceof Blob) || file.size > 2_000_000) throw new Error("Provide a PDF file smaller than 2 MB.");
    const bytes = new Uint8Array(await file.arrayBuffer());
    if (new TextDecoder().decode(bytes.slice(0, 5)) !== "%PDF-") throw new Error("Provide a PDF file smaller than 2 MB.");
    let pdf;
    const loading = getDocument({data: bytes.slice(), isEvalSupported: false});
    try {pdf = await loading.promise;}
    catch {throw new Error("The PDF could not be read. Encrypted or malformed documents are not supported.");}
    const pages = [];
    try {
      if (pdf.numPages < 1 || pdf.numPages > 10) throw new Error("PDFs must contain 1–10 pages.");
      for (let i = 1; i <= pdf.numPages; i++) {
        const page = await pdf.getPage(i), content = await page.getTextContent();
        const lines = []; let line = [], y = null;
        for (const item of content.items) {
          if (!("str" in item)) continue;
          const nextY = item.transform[5];
          if (y !== null && Math.abs(y - nextY) > 2 && line.length) {lines.push(line.join(" ").trim()); line = [];}
          y = nextY; if (item.str) line.push(item.str);
          if (item.hasEOL && line.length) {lines.push(line.join(" ").trim()); line = []; y = null;}
        }
        if (line.length) lines.push(line.join(" ").trim());
        pages.push(lines.join("\n"));
      }
    } finally {await loading.destroy();}
    if (!pages.some(p => p.trim())) throw new Error("No readable text found. Scanned images need OCR, which is outside this version.");
    if (pages.join("").length > 12_000) throw new Error("Keep PDFs under 12,000 extracted characters.");
    const hash = [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))].map(n => n.toString(16).padStart(2, "0")).join("");
    const document = {id: identifier(), filename: file.name || "invoice.pdf", source_id: "INVOICE-" + hash.slice(0, 12), pages, bytes};
    this.state.documents[document.id] = document;
    await this.save();
    return document;
  }
  async investigate(run) {
    run.status = "running"; run.error = null;
    try {
      if (!run.invoice) {
        this.emit(run, 1, "started", "Read the actual PDF using the public demo's labeled-field rules", {execution_mode: "guided_demo", model_inference: false});
        run.invoice = invoiceFromPages(run.document.pages);
        this.emit(run, 1, "completed", "Template fields grounded in exact PDF source lines", {invoice: run.invoice, method: "Unique labeled fields; no model extraction"});
      }
      // This is deliberately a fixed checklist, not claimed to be model-selected.
      for (const name of TOOL_NAMES) {
        const result = executeDemoTool(name, run, this.catalog);
        this.emit(run, 2, "tool", name, {...result, round: run.round, routing: "Fixed public-demo checklist; no model planning"});
      }
      this.emit(run, 2, "completed", "The five read-only checklist queries completed", {action: "finish", round: run.round});
      run.controls = evaluateDemoControls(run, this.catalog);
      const failed = run.controls.findings.filter(f => f.result === "fail");
      const selected = failed.length ? failed : run.controls.findings.slice(0, 1);
      run.memo = {
        recommended_action: run.controls.recommendation,
        summary: failed.length ? `${failed.length} required control(s) need attention. Review the cited evidence before resolving this case.` : "The required controls pass. Review the sources before recording a release recommendation.",
        findings: selected.map(f => ({title: f.title, explanation: f.detail, source_ids: f.source_ids})),
        next_actions: ["Review the cited sources and record a human decision."],
        client_request: failed.length ? `Regarding invoice ${run.invoice.invoice_number.value}, please provide evidence resolving the following: ${failed.map(f => f.title + ": " + f.detail).join("\n\n")}\n\nPlease quote purchase order ${run.invoice.po_number.value}. Bank-detail changes require independent verification through an existing trusted contact.` : "No additional evidence requested. Human review is still required.",
      };
      this.emit(run, 3, "completed", "Exact-cent controls computed; a template review summary prepared", {recommendation: run.controls.recommendation, failed_controls: failed.length, unsupported_amount: run.controls.unsupported_amount, model_inference: false});
      run.status = "awaiting_review";
      this.emit(run, 4, "paused", "Case saved in this browser; waiting for a reviewer");
    } catch (error) {run.status = "failed"; run.error = error.message; this.emit(run, 0, "error", "Investigation stopped without a recommendation", {detail: error.message});}
    await this.save();
  }
  async api(path, options = {}) {
    await this.ready;
    const method = options.method || "GET";
    const value = typeof options.body === "string" ? JSON.parse(options.body) : options.body;
    if (path === "/api/health") return {status: "ok", mode: "guided_demo", model_ready: false, workflow_ready: true, model: "Browser rules · no LLM", framework: "Public workflow demo", model_api_key_required: false};
    if (path === "/api/cases") return {cases: copy(this.catalog.cases)};
    if (path === "/api/documents" && method === "POST") {
      const document = await this.document(value.get("file"));
      return {id: document.id, filename: document.filename, pages: document.pages.length};
    }
    if (path === "/api/runs" && method === "GET") return {runs: copy(Object.values(this.state.runs).reverse())};
    if (path === "/api/runs" && method === "POST") {
      if (!!value.case_id === !!value.document_id) throw new Error("Choose one sample or one uploaded invoice.");
      if (Object.values(this.state.runs).some(r => r.status === "running")) throw new Error("Wait for the current investigation to pause.");
      let document;
      if (value.case_id) {
        const c = this.catalog.cases.find(c => c.id === value.case_id);
        if (!c) throw new Error("Sample case not found.");
        const response = await fetch(this.url("/api/sample/" + c.file));
        if (!response.ok) throw new Error("The sample PDF could not be downloaded.");
        document = await this.document(new File([await response.blob()], c.file, {type: "application/pdf"}));
      } else document = this.state.documents[value.document_id];
      if (!document) throw new Error("Document not found.");
      const run = {id: identifier(), case_id: value.case_id || null, document, mode: "guided_demo", model: "Browser rules · no LLM", synthetic: !!value.case_id, status: "running", created_at: now(), updated_at: now(), round: 1, invoice: null, controls: null, memo: null, review_history: [], receiving_replies: [], events: []};
      this.state.runs[run.id] = run;
      await this.save();
      queueMicrotask(() => this.investigate(run));
      return {id: run.id};
    }
    const match = path.match(/^\/api\/runs\/([a-f0-9]{32})(?:\/(pack|review|evidence|retry))?$/);
    if (!match) throw new Error("This route is not available in the public demo.");
    const run = this.state.runs[match[1]];
    if (!run) throw new Error("Run not found in this browser.");
    if (method === "GET" && (!match[2] || match[2] === "pack")) return copy({...run, document: {...run.document, bytes: undefined}, notice: "Public browser demo: template PDF extraction and fixed tool routing, no live LLM or LangGraph execution. Controls and human actions execute in-browser. The local source implements LangGraph + Ollama."});
    if (match[2] === "review" && method === "POST") {
      const decision = reviewDecision(run, value);
      run.review_history.push(decision);
      this.emit(run, 4, "decision", "Reviewer decision recorded", decision);
      if (decision.action === "request_evidence") {run.status = "awaiting_evidence"; this.emit(run, 4, "paused", "Waiting for an additional receiving PDF; no request sent");}
      else {run.status = "completed"; run.completion = {result: decision.action === "approve" ? "release_recommended" : "held", notice: "No payment or message was initiated."};}
      await this.save(); return {id: run.id};
    }
    if (match[2] === "evidence" && method === "POST") {
      if (run.status !== "awaiting_evidence") throw new Error("This case is not waiting for evidence.");
      const document = this.state.documents[value.document_id];
      if (!document) throw new Error("Document not found.");
      try {
        const record = receivingFromPages(document, run, this.catalog);
        run.receiving_replies.push(record); run.round += 1; run.evidence_error = null;
        this.emit(run, 1, "evidence", "Additional receiving evidence validated; rerunning this case", {source_id: record.source_id, report_number: record.report_number});
        await this.investigate(run);
      } catch (error) {run.evidence_error = error.message; this.emit(run, 1, "rejected", "Reply rejected; prior case preserved", {detail: error.message}); await this.save();}
      return {id: run.id};
    }
    if (match[2] === "retry" && method === "POST" && ["failed", "stopped"].includes(run.status)) {await this.investigate(run); return {id: run.id};}
    throw new Error("This action is not allowed for the current case state.");
  }
  blobUrl(key, blob) {
    if (!this.urls.has(key)) this.urls.set(key, URL.createObjectURL(blob));
    return this.urls.get(key);
  }
  url(path) {
    if (path.startsWith("/api/sample/")) return new URL("./agent_samples/" + path.split("/").at(-1), import.meta.url).href;
    const doc = path.match(/^\/api\/documents\/([a-f0-9]{32})$/);
    if (doc) {const d = this.state.documents[doc[1]]; return this.blobUrl(d.id, new Blob([d.bytes], {type: "application/pdf"}));}
    const workpaper = path.match(/^\/api\/runs\/([a-f0-9]{32})\/workpaper.pdf$/);
    if (workpaper) return this.workpaper(this.state.runs[workpaper[1]]);
    return path;
  }
  workpaper(run) {
    if (!run.controls) return "#";
    const doc = new jsPDF({unit: "pt", format: "letter"}); let y = 48;
    const text = (value, bold = false) => {
      doc.setFont("helvetica", bold ? "bold" : "normal"); doc.setFontSize(bold ? 12 : 10);
      const lines = doc.splitTextToSize(String(value).replaceAll("·", "|").replaceAll("—", "-"), 516);
      for (const line of lines) {if (y > 740) {doc.addPage(); y = 48;} doc.text(line, 48, y); y += 14;}
      y += 8;
    };
    text("LedgerLens - Invoice Investigation Workpaper", true);
    text("PUBLIC WORKFLOW DEMO | Browser rules | No live model inference");
    text(`Vendor: ${run.invoice.vendor.value} | Invoice: ${run.invoice.invoice_number.value} | Round ${run.round}`);
    text(`Case ${run.id} | ${run.status} | Generated ${now()}`);
    text("Synthetic system records. Reviewer names are unverified. This is not a completed audit or a payment instruction.");
    text(`Recommendation: ${run.controls.recommendation} | Unsupported amount: USD ${run.controls.unsupported_amount}`, true);
    for (const f of run.controls.findings) {text(`${f.title}: ${f.result.toUpperCase()}`, true); text(f.detail); text("Sources: " + f.source_ids.join(", "));}
    text("Reviewer history", true);
    for (const d of run.review_history) text(`Round ${d.round}: ${d.reviewer} | ${d.action}\n${d.note}\n${d.at}`);
    text("Evidence request template (not sent)", true); text(run.memo.client_request);
    text("No payment, email, vendor update, or accounting posting was initiated.");
    return this.blobUrl(run.id + ":" + run.updated_at, doc.output("blob"));
  }
}
