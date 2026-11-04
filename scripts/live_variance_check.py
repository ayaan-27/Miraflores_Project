"""Actual model + graph + SQLite + PDF evidence loop. No test planner."""
from pathlib import Path
import json
import resource
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from variance_workspace.data import Workspace, SAMPLES
from variance_workspace.model import Model, download_model
from variance_workspace.workflow import Service


def report(title, message):
    message = message.replace('%', '%25').replace('\n', '%0A')
    print(f"::notice title={title}::{message}", flush=True)


def main():
    path = download_model()
    print(json.dumps({"phase": "model_verified", "bytes": path.stat().st_size}), flush=True)
    model = Model()
    started = time.monotonic()
    out = Path("artifacts/variance-live"); out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        service = Service(Workspace(Path(directory)), model)
        def callback(update):
            for name, data in update.items():
                if name != '__interrupt__':
                    print(json.dumps({"node": name, "action": data.get('action'), "events": [e['title'] for e in data.get('trace',[])]}), flush=True)
        run = service.start("6100", callback)
        first = service.view(run)
        assert first['analysis']['outcome'] == 'evidence_needed'
        assert first['next_nodes'] == ['review']
        (out/'initial.json').write_text(json.dumps(first, indent=2))
        decision = {'action':'request_evidence', 'reviewer':'Automated integration check', 'note':'Test action requesting the service dates. Not an actual human sign-off.'}
        service.review(run, decision)
        result = service.reply(run, (SAMPLES/'software-contract.pdf').read_bytes(), 'software-contract.pdf', callback)
        assert result['analysis']['adjustment_cents'] == 2200000
        assert result['analysis']['adjusted_cents'] == 400000
        assert result['round'] == 2 and len(result['history']) == 1
        decision.update(action='approve', note='Test action after all required checks pass. Not an actual human sign-off.')
        final = service.review(run, decision)
        assert final['completion']['journal_posted'] is False
        assert model.calls >= 10
        (out/'completed.json').write_text(json.dumps(final,indent=2))
        payroll = service.view(service.start('6200', callback))
        assert payroll['analysis']['outcome'] == 'explained'
        (out/'payroll.json').write_text(json.dumps(payroll,indent=2))
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        details = {'seconds':round(time.monotonic()-started,1),'peak_rss_mib':round(peak,1),'model_calls':model.calls,'software_adjustment':'22000.00','software_after_adjustment':'4000.00','payroll_adjustment':'0.00'}
        (out/'metrics.json').write_text(json.dumps(details,indent=2))
        report('Real variance workflow passed',json.dumps(details))


if __name__ == '__main__':
    main()
