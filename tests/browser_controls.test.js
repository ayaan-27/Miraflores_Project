import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {invoiceFromPages, evaluateDemoControls, receivingFromPages, reviewDecision, cents} from "../agent_workspace/web/browser_controls.js";
const catalog = JSON.parse(readFileSync(new URL("../agent_samples/catalog.json", import.meta.url)));
const values = [["Marigold Office LLC", "INV-2048", "PO-7710", "LAMP-01", "100", "100.00", "10000.00", "8842"], ["Northstar Services LLC", "INV-3092", "PO-8840", "SUPPORT-OCT", "1", "4800.00", "4800.00", "7821"], ["Harbor Print LLC", "INV-9042", "PO-9901", "PRINT-01", "1", "1550.00", "1550.00", "2209"], ["Cedar Supply LLC", "INV-5001", "PO-6650", "CHAIR-02", "12", "200.00", "2400.00", "1182"]];
function run(i = 0) {
  const [vendor, number, po, sku, qty, price, total, bank] = values[i];
  const pages = [`Vendor: ${vendor}\nInvoice number: ${number}\nInvoice date: 2026-10-14\nPurchase order: ${po}\nCurrency: USD\nSKU: ${sku}\nQuantity: ${qty}\nUnit price: ${price}\nLine total: ${total}\nInvoice total: ${total}\nBank account ending: ${bank}`];
  return {invoice: invoiceFromPages(pages), document: {id: "document", source_id: "INVOICE-TEST", filename: "invoice.pdf", pages}, receiving_replies: [], round: 1, status: "awaiting_review"};
}
const reply = {id: "reply-document", source_id: "INVOICE-REPLY", pages: ["Report number: GRN-7731\nPurchase order: PO-7710\nSKU: LAMP-01\nAdditional quantity received: 20"]};
test("public controls distinguish receiving, bank-change, duplicate, and clean cases", () => {
  for (const [i, code] of [[0, "RECEIVING:LAMP-01"], [1, "VENDOR_BANK"], [2, "DUPLICATE_PAYMENT"], [3, null]]) {
    const result = evaluateDemoControls(run(i), catalog);
    assert.equal(result.recommendation, code ? "hold" : "ready_for_review");
    assert.deepEqual(result.findings.filter(f => f.result === "fail").map(f => f.code), code ? [code] : []);
    assert.equal(result.unsupported_amount, i === 0 ? "2000.00" : "0.00");
    for (const finding of result.findings) for (const id of finding.source_ids) assert.ok(result.sources[id], id);
  }
});
test("additional evidence closes the receiving gap but still requires a reviewer", () => {
  const r = run(); r.controls = evaluateDemoControls(r, catalog);
  const decision = {action: "approve", reviewer: "Demo reviewer", note: "Checked all required sources."};
  assert.throws(() => reviewDecision(r, decision), /blocked/);
  r.receiving_replies.push(receivingFromPages(reply, r, catalog)); r.round = 2;
  r.controls = evaluateDemoControls(r, catalog);
  assert.equal(r.controls.unsupported_amount, "0.00");
  assert.equal(r.controls.failed_controls, 0);
  assert.equal(reviewDecision(r, decision).round, 2);
});
test("reply validation rejects wrong orders, wrong SKUs, and double-counting", () => {
  const r = run();
  for (const [from, to, expected] of [["PO-7710", "PO-9999", /different purchase order/], ["LAMP-01", "OTHER", /outside this invoice/]]) {
    assert.throws(() => receivingFromPages({...reply, pages: [reply.pages[0].replace(from, to)]}, r, catalog), expected);
  }
  r.receiving_replies.push(receivingFromPages(reply, r, catalog));
  assert.throws(() => receivingFromPages(reply, r, catalog), /counted twice/);
});
test("template extraction refuses ambiguous or absent evidence and unsupported amounts", () => {
  const r = run();
  assert.throws(() => invoiceFromPages([r.document.pages[0] + "\nVendor: Different LLC"]), /unambiguous/);
  assert.throws(() => invoiceFromPages([r.document.pages[0].replace("Vendor:", "Supplier:")]), /unambiguous/);
  assert.throws(() => cents("1e6"), /amounts/);
  assert.equal(cents("1.1"), 110);
});
test("invoice arithmetic failure is held independently of receiving support", () => {
  const r = run(3); r.invoice.total.value = "2399.99";
  assert.ok(evaluateDemoControls(r, catalog).findings.some(f => f.code === "INVOICE_ARITHMETIC" && f.result === "fail"));
});
