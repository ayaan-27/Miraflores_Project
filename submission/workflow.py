"""Self-contained, rules-based month-end review. Python standard library only."""
import csv, calendar, hashlib, json, re, sqlite3
from copy import deepcopy
from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path
if "DATA" not in globals():
    DATA = json.loads(Path(__file__).with_name("data.json").read_text())
CATALOG = DATA["catalog"]

def cents(value: str) -> int:
    if not re.fullmatch('\\d{1,9}(?:\\.\\d{1,2})?', value):
        raise ValueError('Amounts must be plain nonnegative USD numbers with at most two decimals.')
    return int(Decimal(value) * 100)

def dollars(value: int) -> str:
    return f'{Decimal(value) / 100:.2f}'

def parse_ledger(data: bytes) -> list[dict]:
    if len(data) > 1000000:
        raise ValueError('Keep the ledger under 1 MB.')
    try:
        reader = csv.DictReader(StringIO(data.decode('utf-8-sig')), strict=True)
        required = {'id', 'date', 'account', 'vendor', 'description', 'debit', 'credit', 'currency', 'document_id'}
        if set(reader.fieldnames or []) != required:
            raise ValueError("Use the sample ledger's nine column headers.")
        result, ids = ([], set())
        for number, raw in enumerate(reader, 2):
            if len(result) >= 2000:
                raise ValueError('Keep the ledger under 2,000 rows.')
            if None in raw or any((v is None or not v.strip() or len(v) > 300 for v in raw.values())):
                raise ValueError(f'Row {number}: missing, extra, or oversized field.')
            r = {k: v.strip() for k, v in raw.items()}
            if not re.fullmatch('[\\w-]{1,64}', r['id']) or r['id'] in ids:
                raise ValueError(f'Row {number}: duplicate or invalid transaction ID.')
            ids.add(r['id'])
            try:
                if date.fromisoformat(r['date']).isoformat() != r['date']:
                    raise ValueError()
            except ValueError:
                raise ValueError(f'Row {number}: use a valid YYYY-MM-DD date.') from None
            if r['date'][:7] not in {CATALOG['period'], CATALOG['previous_period']}:
                raise ValueError(f'Row {number}: this close compares September and October 2026 only.')
            if r['account'] not in CATALOG['accounts'] or r['currency'] != 'USD':
                raise ValueError(f'Row {number}: use a supplied expense account and USD.')
            debit, credit = (cents(r.pop('debit')), cents(r.pop('credit')))
            if bool(debit) == bool(credit):
                raise ValueError(f'Row {number}: enter either a debit or a credit, not both or neither.')
            r['amount_cents'] = debit - credit
            result.append(r)
    except (UnicodeDecodeError, csv.Error):
        raise ValueError('The ledger must be a readable UTF-8 CSV.') from None
    if not result or {r['date'][:7] for r in result} != {CATALOG['period'], CATALOG['previous_period']}:
        raise ValueError('Include expense transactions for both September and October 2026.')
    return result

def value(document: dict, key: str) -> str:
    try:
        return document['fields'][key]['value']
    except KeyError:
        raise ValueError(f"{document.get('id', 'Document')} is missing the {key} field.") from None

def month_index(d: date) -> int:
    return d.year * 12 + d.month - 1

def schedule(amount: int, start: str, end: str, period: str) -> dict:
    try:
        first, last, close = (date.fromisoformat(start), date.fromisoformat(end), date.fromisoformat(period + '-01'))
    except ValueError:
        raise ValueError('The service dates must be valid ISO dates.') from None
    if first > last or first.day != 1 or last.day != calendar.monthrange(last.year, last.month)[1]:
        raise ValueError('Partial-month or reversed service dates need manual review.')
    months = month_index(last) - month_index(first) + 1
    if not 1 <= months <= 60:
        raise ValueError('Service periods longer than 60 months need manual review.')
    base, remainder = divmod(amount, months)
    rows = []
    for i in range(months):
        index = month_index(first) + i
        rows.append({'period': f'{index // 12:04d}-{index % 12 + 1:02d}', 'expense_cents': base + int(i < remainder)})
    recognized = sum((r['expense_cents'] for r in rows if r['period'] <= period))
    current = sum((r['expense_cents'] for r in rows if r['period'] == period))
    return {'rows': rows, 'months': months, 'recognized_cents': recognized, 'current_expense_cents': current, 'future_cents': amount - recognized}

def validate_reply(workspace, state: dict, record: dict):
    expected = state['analysis'].get('missing_document_id')
    if not expected or record['id'] != expected:
        raise ValueError(f"This case is waiting for {expected or 'a different document'}.")
    if value(record, 'Entity') != CATALOG['entity']:
        raise ValueError('The document belongs to a different entity.')
    driver = state['analysis'].get('driver')
    if not driver:
        raise ValueError('The missing posting could not be identified; review this case manually.')
    if value(record, 'Vendor').casefold() != driver['vendor'].casefold():
        raise ValueError('The document vendor does not match the posting.')
    if value(record, 'Currency') != 'USD' or cents(value(record, 'Amount')) != driver['amount_cents']:
        raise ValueError('The document amount or currency does not match the posting.')
    if expected != driver['document_id']:
        if value(record, 'Document type') != 'Service agreement' or value(record, 'Invoice ID') != driver['document_id']:
            raise ValueError('The agreement does not refer to this invoice.')
        if value(record, 'Authorized').casefold() != 'yes':
            raise ValueError('The agreement does not contain the required authorization field.')
        schedule(driver['amount_cents'], value(record, 'Service start'), value(record, 'Service end'), CATALOG['period'])
    if workspace.document(record['id']):
        raise ValueError('This document is already present; it cannot replace previously used evidence.')

def evaluate(workspace, account_code: str) -> dict:
    account = workspace.account(account_code)
    result = {'outcome': 'hold', 'approval_allowed': False, 'account': account, 'findings': [], 'journal': [], 'allocation': [], 'adjustment_cents': 0, 'adjusted_cents': account['current_cents'], 'missing_document_id': None, 'driver': None}
    ledger = workspace.ledger_source(account_code)
    sources = {ledger['id']: ledger}
    result['sources'] = sources

    def finding(name, ok, detail, ids):
        result['findings'].append({'name': name, 'passed': bool(ok), 'detail': detail, 'source_ids': ids})
    rows = workspace.ledger_rows(account_code, CATALOG['period'])
    duplicates = [r['document_id'] for r in rows if sum((s['document_id'] == r['document_id'] for s in rows)) > 1]
    finding('Posting uniqueness', not duplicates, 'No repeated document reference in the selected period.' if not duplicates else 'A document is referenced by multiple postings: ' + ', '.join(sorted(set(duplicates))), [ledger['id']])
    if duplicates:
        return result
    drivers = workspace.drivers(account_code)
    clear_driver = len(drivers) == 1 and drivers[0]['amount_cents'] == account['change_cents'] and (drivers[0]['amount_cents'] > 0)
    finding('Variance bridge', clear_driver, 'One additional posting reconciles the full account movement.' if clear_driver else 'The movement has multiple or changing components; automatic treatment is withheld.', [ledger['id']])
    if not clear_driver:
        return result
    driver = drivers[0]
    result['driver'] = driver
    invoice = workspace.document(driver['document_id'])
    if not invoice:
        result.update(outcome='evidence_needed', missing_document_id=driver['document_id'])
        finding('Posting support', False, "The posting's source document is missing.", [ledger['id']])
        return result
    sources[invoice['id']] = invoice
    supported = value(invoice, 'Entity') == CATALOG['entity'] and value(invoice, 'Vendor').casefold() == driver['vendor'].casefold() and (value(invoice, 'Currency') == 'USD') and (cents(value(invoice, 'Amount')) == driver['amount_cents'])
    finding('Posting support', supported, 'Source entity, vendor, currency, and amount agree with the posting.' if supported else 'The source does not agree with the posting.', [ledger['id'], invoice['id']])
    if not supported:
        return result
    policy = workspace.document('POL-CLOSE')
    if not policy or value(policy, 'Basis') != 'Accrual' or value(policy, 'Allocation') != 'Equal monthly allocation over full calendar months':
        finding('Accounting policy', False, 'The supported accrual and full-month allocation policy is unavailable.', [ledger['id']])
        return result
    sources[policy['id']] = policy
    if invoice['kind'] == 'Payroll memo':
        ok = value(invoice, 'Earned period') == CATALOG['period'] and value(invoice, 'Approval') == 'Approved' and (value(policy, 'Bonuses') == 'Expense in the earned period with approval')
        finding('Earned-period support', ok, 'The approved one-time bonus was earned in October.' if ok else 'Bonus approval or earned period does not support this close.', [invoice['id'], policy['id']])
        if ok:
            result.update(outcome='explained', approval_allowed=True)
        return result
    if invoice['kind'] != 'Invoice':
        finding('Document type', False, 'This source type needs manual review.', [invoice['id']])
        return result
    agreement_id = value(invoice, 'Agreement ID')
    contract = workspace.document(agreement_id)
    if not contract:
        result.update(outcome='evidence_needed', missing_document_id=agreement_id)
        finding('Service-period support', False, f'{agreement_id} is missing. Service dates are needed before proposing a treatment.', [invoice['id'], policy['id']])
        return result
    sources[contract['id']] = contract
    match = value(contract, 'Entity') == CATALOG['entity'] and value(contract, 'Vendor').casefold() == driver['vendor'].casefold() and (value(contract, 'Invoice ID') == driver['document_id']) and (value(contract, 'Currency') == 'USD') and (cents(value(contract, 'Amount')) == driver['amount_cents']) and (value(contract, 'Authorized') == 'Yes')
    finding('Agreement match', match, 'The agreement matches the posting and contains the sample authorization field.' if match else 'The agreement does not match the posting or required authorization field.', [contract['id'], invoice['id']])
    if not match:
        return result
    try:
        allocation = schedule(driver['amount_cents'], value(contract, 'Service start'), value(contract, 'Service end'), CATALOG['period'])
    except ValueError as error:
        finding('Service allocation', False, str(error), [contract['id'], policy['id']])
        return result
    if allocation['recognized_cents'] != allocation['current_expense_cents']:
        finding('Prior-period effects', False, 'This agreement spans an earlier close; retrospective allocation needs manual review.', [contract['id'], policy['id']])
        return result
    future = allocation['future_cents']
    above_threshold = driver['amount_cents'] >= cents(value(policy, 'Prepaid threshold'))
    adjustment = future if above_threshold else 0
    finding('Service allocation', True, f"{allocation['months']} full calendar month(s); USD {dollars(allocation['current_expense_cents'])} relates to October and USD {dollars(future)} to later periods. The supplied policy threshold is USD {value(policy, 'Prepaid threshold')}.", [contract['id'], policy['id']])
    result.update(outcome='adjustment_proposed' if adjustment else 'explained', approval_allowed=True, adjustment_cents=adjustment, adjusted_cents=account['current_cents'] - adjustment, allocation=allocation['rows'])
    if adjustment:
        result['journal'] = [{'account': '1500', 'name': 'Prepaid services', 'debit_cents': adjustment, 'credit_cents': 0}, {'account': account_code, 'name': account['name'], 'debit_cents': 0, 'credit_cents': adjustment}]
    if sum((r['debit_cents'] for r in result['journal'])) != sum((r['credit_cents'] for r in result['journal'])):
        raise ValueError('The proposed journal does not balance.')
    return result

class Workspace:
    def __init__(self, ledger=None):
        raw = ledger if ledger is not None else DATA["ledger_csv"].encode()
        records = parse_ledger(raw)
        self.ledger_hash = hashlib.sha256(raw).hexdigest()
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("CREATE TABLE transactions(id TEXT PRIMARY KEY,date TEXT,account TEXT,vendor TEXT,description TEXT,currency TEXT,document_id TEXT,amount_cents INTEGER)")
        self.conn.executemany("INSERT INTO transactions VALUES (:id,:date,:account,:vendor,:description,:currency,:document_id,:amount_cents)",records)
        self.documents = {key:deepcopy(record) for key,record in DATA["documents"].items() if CATALOG["documents"][key]["available"]}
    def document(self, key):
        return deepcopy(self.documents.get(key))

    def query(self, sql: str, args=()) -> list[dict]:
        if not sql.lstrip().upper().startswith('SELECT '):
            raise ValueError('Only scoped read queries are permitted.')
        return [dict(row) for row in self.conn.execute(sql, args).fetchall()]

    def accounts(self) -> list[dict]:
        rows = self.query('SELECT account, substr(date,1,7) period, SUM(amount_cents) total FROM transactions GROUP BY account, period')
        result = []
        for code, name in CATALOG['accounts'].items():
            totals = {r['period']: r['total'] for r in rows if r['account'] == code}
            previous, current = (totals.get(CATALOG['previous_period'], 0), totals.get(CATALOG['period'], 0))
            delta = current - previous
            ratio = abs(Decimal(delta) / previous) if previous else None
            material = abs(delta) >= cents(CATALOG['materiality']) and (ratio is None or ratio >= Decimal(CATALOG['percentage_threshold']))
            result.append({'code': code, 'name': name, 'previous_cents': previous, 'current_cents': current, 'change_cents': delta, 'change_ratio': float(ratio) if ratio is not None else None, 'material': material})
        return result

    def account(self, code):
        try:
            return next((r for r in self.accounts() if r['code'] == code))
        except StopIteration:
            raise ValueError('Unknown account.') from None

    def ledger_rows(self, account, period):
        if account not in CATALOG['accounts'] or period not in {CATALOG['period'], CATALOG['previous_period']}:
            raise ValueError('The ledger query is outside this close.')
        return self.query('SELECT * FROM transactions WHERE account=? AND substr(date,1,7)=? ORDER BY ABS(amount_cents) DESC,id', (account, period))

    def drivers(self, account):
        current = self.ledger_rows(account, CATALOG['period'])
        previous = self.ledger_rows(account, CATALOG['previous_period'])
        baseline = {(r['vendor'], r['description'], r['amount_cents']) for r in previous}
        return [r for r in current if (r['vendor'], r['description'], r['amount_cents']) not in baseline]

    def ledger_source(self, account):
        return {'id': 'LEDGER-' + self.ledger_hash[:10] + '-' + account, 'kind': 'Ledger query', 'title': 'September and October expense entries', 'ledger_sha256': self.ledger_hash, 'rows': self.ledger_rows(account, CATALOG['previous_period']) + self.ledger_rows(account, CATALOG['period'])}

class Review:
    def __init__(self, ledger=None):
        self.workspace=Workspace(ledger)
        self.state=None
    def investigate(self, account="6100"):
        if not self.workspace.account(account)["material"]:
            raise ValueError("This movement is below the review threshold.")
        self.state={"account_code":account,"status":"awaiting_review","round":1,"history":[],"analysis":evaluate(self.workspace,account),"journal_posted":False}
        return deepcopy(self.state)
    def decide(self, action, reviewer, note):
        s=self.state
        if s is None or s["status"]!="awaiting_review": raise ValueError("The case is not waiting for review.")
        if action not in {"approve","hold","request_evidence"}: raise ValueError("Invalid action.")
        if len(reviewer.strip())<2 or len(note.strip())<8: raise ValueError("Enter a reviewer and a meaningful note.")
        if action=="approve" and (not s["analysis"]["approval_allowed"] or any(not f["passed"] for f in s["analysis"]["findings"])): raise ValueError("Approval blocked: required support is unresolved.")
        if action=="request_evidence" and not s["analysis"].get("missing_document_id"): raise ValueError("There is no missing document request.")
        s["history"].append({"action":action,"reviewer":reviewer,"note":note,"round":s["round"]})
        s["status"]="awaiting_evidence" if action=="request_evidence" else "approved" if action=="approve" else "held"
        return deepcopy(s)
    def add_evidence(self, record):
        s=self.state
        if s is None or s["status"]!="awaiting_evidence": raise ValueError("Request evidence before adding a document.")
        validate_reply(self.workspace,s,record)
        original=self.workspace.documents
        self.workspace.documents={**original,record["id"]:deepcopy(record)}
        try:
            analysis=evaluate(self.workspace,s["account_code"])
        except Exception:
            self.workspace.documents=original
            raise
        s["round"]+=1
        s["analysis"]=analysis
        s["status"]="awaiting_review"
        return deepcopy(s)
