"""Real local-model integration check. No API credentials or fixture model.

This can run on a normal CI runner with public model-download access. The
programmatically entered reviewer actions are labeled integration-test actions.
"""
from pathlib import Path
import asyncio
import json
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from agent_workspace.evidence import SAMPLES
from agent_workspace.model import configured_model, model_ready
from agent_workspace.models import ReviewerDecision
from agent_workspace.service import RunService
from agent_workspace.store import Store
from agent_workspace.workpaper import render_workpaper


def annotation(level, title, value):
    value = str(value).replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
    print(f'::{level} title={title}::{value}', flush=True)


async def wait(service, identifier, desired, timeout=900):
    started = time.monotonic()
    last_event = 0
    while time.monotonic() - started < timeout:
        view = await service.view(identifier)
        for event in view['events']:
            if event['seq'] > last_event:
                print(json.dumps({'stage':event['stage'],'kind':event['kind'],'title':event['title'],'data':event['data']}),flush=True)
                last_event = event['seq']
        if view['status'] == desired:
            return view
        if view['status'] == 'failed':
            raise AssertionError(view['error'])
        await asyncio.sleep(1)
    raise AssertionError(f'Real-model run did not reach {desired} in {timeout} seconds.')


async def main():
    model = configured_model()
    if not await model_ready(model):
        raise AssertionError(getattr(model, 'readiness_error', '') or 'Install the native runtime and verified official model weights first.')
    directory = Path('artifacts/live-agent')
    directory.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='ledgerlens-live-') as temp:
        async with aiosqlite.connect(str(Path(temp)/'store.db')) as connection:
            store = Store(connection)
            await store.initialize()
            async with AsyncSqliteSaver.from_conn_string(str(Path(temp)/'checkpoints.db')) as checkpointer:
                service = RunService(model, store, checkpointer)
                try:
                    document = await store.document((SAMPLES/'partial-delivery.pdf').read_bytes(),'partial-delivery.pdf')
                    run = await service.start(document,'partial-delivery',synthetic=True)
                    first = await wait(service,run,'awaiting_review')
                    assert first['controls']['unsupported_amount']=='2000.00'
                    assert first['controls']['recommendation']=='hold'
                    assert len([e for e in first['events'] if e['kind']=='tool'])==5
                    (directory/'initial-hold.json').write_text(json.dumps(first,indent=2))
                    annotation('notice','Real-model initial investigation passed','PDF extraction and source quotes validated; five actual tools executed; hold with USD 2000.00 unsupported; human-review interrupt reached.')
                    await service.review(run,ReviewerDecision(action='request_evidence',reviewer='Automated integration test',note='Integration-test action: request evidence for the remaining 20 units. This is not an actual human sign-off.'))
                    await wait(service,run,'awaiting_evidence')
                    reply = await store.document((SAMPLES/'remaining-delivery.pdf').read_bytes(),'remaining-delivery.pdf')
                    await service.reply(run,reply)
                    second = await wait(service,run,'awaiting_review')
                    assert second['round']==2
                    assert second['controls']['unsupported_amount']=='0.00'
                    assert second['controls']['failed_controls']==0
                    assert len([e for e in second['events'] if e['kind']=='tool'])==10
                    annotation('notice','Real-model resumed investigation passed','New receiving PDF parsed and quoted; same graph thread resumed; all five tools reran; control result changed from hold to ready_for_review.')
                    await service.review(run,ReviewerDecision(action='approve',reviewer='Automated integration test',note='Integration-test action: exercise the approval gate after all checks pass. This is not an actual human sign-off.'))
                    final = await wait(service,run,'completed')
                    assert final['completion']['result']=='release_recommended'
                    assert final['mode'] in {'local_llm', 'ollama_local'}
                    (directory/'completed-review.json').write_text(json.dumps(final,indent=2))
                    (directory/'workpaper.pdf').write_bytes(render_workpaper(final))
                    annotation('notice','Real-model workflow passed',f'Actual open-weight CPU inference, LangGraph tool/evidence loops, and both review gates completed in {time.monotonic()-started:.1f}s. Reviewer actions were automated test inputs. No payment was initiated.')
                finally:
                    await service.close()


if __name__=='__main__':
    try:
        asyncio.run(main())
    except Exception as error:
        annotation('error','Real-model smoke test failed',f'{type(error).__name__}: {error}')
        raise
