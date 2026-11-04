// Public-demo rules. No model inference or agent-selected tool calls occur here.
export const TOOL_NAMES = ["lookup_purchase_order", "lookup_receiving", "lookup_vendor", "search_prior_payments", "search_policy"];
export const normalize = (s) => String(s).toLowerCase().replace(/[^a-z0-9]/g, "");
export function cents(s) {
  if (!/^\d{1,9}(?:\.\d{1,2})?$/.test(String(s))) throw new Error("Use nonnegative USD amounts with at most two decimals.");
  const [whole, fraction = ""] = String(s).split(".");
  return Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
}
export function quantity(s) {
  if (!/^[1-9]\d{0,5}$/.test(String(s))) throw new Error("Use whole-item quantities from 1 to 999999.");
  return Number(s);
}
const money = (n) => (n / 100).toFixed(2);
const usd = (n) => new Intl.NumberFormat("en-US", {style: "currency", currency: "USD"}).format(n / 100);
function multiply(a, b) {
  const n = a * b;
  if (!Number.isSafeInteger(n)) throw new Error("The amount exceeds the supported exact arithmetic range.");
  return n;
}
export function field(pages, label) {
  const found = [];
  pages.forEach((page, i) => page.split("\n").forEach((line) => {
    if (line.startsWith(label + ": ") && line.slice(label.length + 2).trim()) {
      found.push({value: line.slice(label.length + 2).trim(), citation: {page: i + 1, quote: line}});
    }
  }));
  if (found.length !== 1) throw new Error(`The public demo needs one unambiguous “${label}: value” line. Use a supplied text-based sample PDF, or run the Ollama version for model-based extraction.`);
  return found[0];
}
export function invoiceFromPages(pages) {
  const f = (label) => field(pages, label);
  const invoice = {vendor: f("Vendor"), invoice_number: f("Invoice number"), po_number: f("Purchase order"), invoice_date: f("Invoice date"), currency: f("Currency"), total: f("Invoice total"), bank_last4: f("Bank account ending"), lines: [{sku: f("SKU"), quantity: f("Quantity"), unit_price: f("Unit price"), line_total: f("Line total")}]};
  if (invoice.currency.value !== "USD") throw new Error("This prototype supports USD only.");
  if (!/^\d{4}$/.test(invoice.bank_last4.value)) throw new Error("The bank suffix must contain four digits.");
  const date = invoice.invoice_date.value;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || new Date(date + "T00:00:00Z").toISOString().slice(0, 10) !== date) throw new Error("Use a valid YYYY-MM-DD invoice date.");
  cents(invoice.total.value);
  for (const line of invoice.lines) {quantity(line.quantity.value); cents(line.unit_price.value); cents(line.line_total.value);}
  return invoice;
}
export function sourceRegistry(run, catalog) {
  const inv = run.invoice, vendor = normalize(inv.vendor.value), po = inv.po_number.value;
  const doc = run.document;
  const result = {[doc.source_id]: {source_id: doc.source_id, document_id: doc.id, kind: "invoice_pdf", title: doc.filename, pages: doc.pages}};
  for (const [group, kind] of [["purchase_orders", "purchase_order"], ["receiving_reports", "receiving_report"], ["vendors", "vendor_master"], ["payments", "payment_record"], ["policies", "policy"]]) {
    for (const r of catalog[group]) {
      if (kind === "policy" || kind === "purchase_order" && r.id === po || kind === "receiving_report" && r.po_number === po || kind === "vendor_master" && normalize(r.name) === vendor || kind === "payment_record" && normalize(r.vendor) === vendor) {
        result[r.source_id] = {...r, kind, title: r.title || r.source_id};
      }
    }
  }
  for (const r of run.receiving_replies || []) result[r.source_id] = {...r, kind: "receiving_report", title: r.report_number};
  return result;
}
export function executeDemoTool(name, run, catalog) {
  const inv = run.invoice, sources = Object.values(sourceRegistry(run, catalog));
  let args, records;
  if (name === "lookup_purchase_order") {args = {order_number: inv.po_number.value}; records = sources.filter(s => s.kind === "purchase_order");}
  else if (name === "lookup_receiving") {args = {order_number: inv.po_number.value}; records = sources.filter(s => s.kind === "receiving_report");}
  else if (name === "lookup_vendor") {args = {name: inv.vendor.value}; records = sources.filter(s => s.kind === "vendor_master");}
  else if (name === "search_prior_payments") {args = {name: inv.vendor.value, number: inv.invoice_number.value}; records = sources.filter(s => s.kind === "payment_record" && normalize(s.invoice_number) === normalize(inv.invoice_number.value));}
  else if (name === "search_policy") {args = {query: "receiving bank duplicate payment"}; records = sources.filter(s => s.kind === "policy");}
  else throw new Error("Unknown or non-read-only tool.");
  return {tool: name, arguments: args, result: {records, source_ids: records.map(s => s.source_id), synthetic: true, scope: "Synthetic demonstration catalog"}};
}
export function evaluateDemoControls(run, catalog) {
  const inv = run.invoice, total = cents(inv.total.value), sources = sourceRegistry(run, catalog);
  const vendorKey = normalize(inv.vendor.value);
  const po = catalog.purchase_orders.find(r => r.id === inv.po_number.value);
  const vendor = catalog.vendors.find(r => normalize(r.name) === vendorKey);
  const receiving = Object.values(sources).filter(r => r.kind === "receiving_report");
  const paid = catalog.payments.filter(r => normalize(r.vendor) === vendorKey && normalize(r.invoice_number) === normalize(inv.invoice_number.value) && ["paid", "pending"].includes(r.status));
  const findings = [];
  const add = (code, title, pass, detail, ids, policy) => findings.push({code, title, result: pass ? "pass" : "fail", detail, source_ids: [...new Set([run.document.source_id, ...ids, policy])]});
  const calculated = inv.lines.reduce((sum, line) => sum + multiply(quantity(line.quantity.value), cents(line.unit_price.value)), 0);
  if (!Number.isSafeInteger(calculated)) throw new Error("Invoice total exceeds the exact arithmetic range.");
  const lineSums = inv.lines.every(line => multiply(quantity(line.quantity.value), cents(line.unit_price.value)) === cents(line.line_total.value));
  add("INVOICE_ARITHMETIC", "Invoice arithmetic", lineSums && calculated === total, `Calculated line total ${usd(calculated)}; stated invoice total ${usd(total)}. Taxes, discounts, and shipping adjustments are outside this prototype.`, [], "POL-01");
  const poValid = po && po.status === "approved" && normalize(po.vendor) === vendorKey && po.currency === inv.currency.value;
  add("APPROVED_PO", "Approved purchase order", poValid, poValid ? `${po.id} is approved for the same vendor and currency.` : "No approved order for this vendor and currency was found.", po ? [po.source_id] : [], "POL-01");
  let supported = 0;
  for (const line of inv.lines) {
    const sku = line.sku.value, qty = quantity(line.quantity.value), price = cents(line.unit_price.value);
    const orderLine = poValid && po.lines.find(r => r.sku === sku);
    const priceOk = orderLine && price === cents(orderLine.unit_price);
    add("PO_LINE:" + sku, "Order match · " + sku, priceOk && qty <= orderLine.quantity, `Invoice: ${qty} units at ${usd(price)}. ` + (orderLine ? `Approved order: ${orderLine.quantity} units at ${usd(cents(orderLine.unit_price))}.` : "No approved order line found."), po ? [po.source_id] : [], "POL-01");
    const reports = receiving.filter(r => r.sku === sku && r.po_number === inv.po_number.value);
    const received = reports.reduce((sum, r) => sum + r.received_quantity, 0);
    add("RECEIVING:" + sku, "Receiving evidence · " + sku, received >= qty, `Billed ${qty} units; receiving reports support ${received} units. ` + (received >= qty ? "The billed quantity is supported." : `Evidence for ${qty - received} units is still missing.`), reports.map(r => r.source_id), "POL-01");
    if (priceOk) supported += multiply(Math.min(qty, received, orderLine.quantity), price);
  }
  const bankOk = vendor && vendor.status === "active" && vendor.approved_bank_last4 === inv.bank_last4.value;
  add("VENDOR_BANK", "Vendor payment details", bankOk, `Invoice account ending ${inv.bank_last4.value}; ` + (vendor ? `approved vendor account ending ${vendor.approved_bank_last4}.` : "no approved vendor found.") + (bankOk ? "" : " Independent verification through an existing trusted contact is required."), vendor ? [vendor.source_id] : [], "POL-02");
  const searchId = "PAYMENT-SEARCH-" + normalize(inv.invoice_number.value);
  if (!paid.length) sources[searchId] = {source_id: searchId, kind: "query_result", title: "Payment register query", vendor: inv.vendor.value, invoice_number: inv.invoice_number.value, matches: [], scope: "Synthetic demonstration register only"};
  add("DUPLICATE_PAYMENT", "Prior payment check", !paid.length, paid.length ? "A matching vendor invoice already appears as paid or pending. Hold for review; this is not a fraud determination." : "No matching paid or pending invoice was found in the synthetic register.", paid.length ? paid.map(r => r.source_id) : [searchId], "POL-03");
  const failed = findings.filter(f => f.result === "fail");
  return {findings, recommendation: failed.length ? "hold" : "ready_for_review", failed_controls: failed.length, invoice_amount: money(total), receiving_supported_amount: money(Math.min(total, supported)), unsupported_amount: money(Math.max(0, total - supported)), sources, notice: "Receiving support is not a payment authorization. No payment is initiated."};
}
export function receivingFromPages(document, run, catalog) {
  const f = (label) => field(document.pages, label);
  const reply = {report_number: f("Report number"), po_number: f("Purchase order"), sku: f("SKU"), received_quantity: f("Additional quantity received")};
  if (reply.po_number.value !== run.invoice.po_number.value) throw new Error("The reply refers to a different purchase order.");
  if (!run.invoice.lines.some(l => l.sku.value === reply.sku.value)) throw new Error("The reply refers to a SKU outside this invoice.");
  const reports = Object.values(sourceRegistry(run, catalog));
  if (reports.some(s => normalize(s.report_number || s.source_id) === normalize(reply.report_number.value)) || run.receiving_replies.some(s => s.document_hash === document.source_id)) throw new Error("This receiving report already exists. It cannot be counted twice.");
  return {source_id: "RECEIVING-" + document.id.slice(0, 12), report_number: reply.report_number.value, po_number: reply.po_number.value, sku: reply.sku.value, received_quantity: quantity(reply.received_quantity.value), document_id: document.id, document_hash: document.source_id, pages: document.pages, extraction: reply};
}
export function reviewDecision(run, value) {
  if (run.status !== "awaiting_review") throw new Error("This run is not awaiting a review decision.");
  if (!["approve", "hold", "request_evidence"].includes(value.action) || !value.reviewer || value.reviewer.trim().length < 2 || value.reviewer.length > 80 || !value.note || value.note.trim().length < 5 || value.note.length > 1000) throw new Error("Provide a valid decision, reviewer name, and decision note.");
  if (value.action === "approve" && run.controls.failed_controls) throw new Error("Approval is blocked while required financial controls fail.");
  if (value.action === "request_evidence" && run.round >= 3) throw new Error("The three-round evidence limit was reached; record a hold.");
  return {...value, reviewer: value.reviewer.trim(), note: value.note.trim(), at: new Date().toISOString(), round: run.round};
}
