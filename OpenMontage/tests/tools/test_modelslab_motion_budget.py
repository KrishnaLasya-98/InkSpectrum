import json
from types import SimpleNamespace

import pytest

from tools.video.modelslab_motion_budget import MotionBudget
from tools.video import educational_motion_worker as cloud
from tools.video import submit_educational_motion_batch as submit
from tools.video.recover_educational_motion_batch import terminal_disposition
from tools.structure import educational_job_worker as queue
from tools.video import _modelslab_shared as shared


def seed(root, number, *, now=10000, age=100, status="submitted"):
    root.mkdir(parents=True, exist_ok=True)
    for index in range(number):
        output = root / f"clip-{index}.mp4"
        (root / f"clip-{index}.mp4.modelslab-job.json").write_text(json.dumps({
            "provider": "modelslab", "status": status, "output_path": str(output.resolve()),
            "submitted_at_unix": now-age, "request_id": str(index+1)}))


def budget(tmp_path):
    return MotionBudget(tmp_path/'budget', tmp_path/'projects', clock=lambda: 10000)


def test_fifteen_async_slots_shared_across_projects(tmp_path):
    b = budget(tmp_path)
    seed(b.projects/'chapter-1', 10)
    seed(b.projects/'chapter-2', 5)
    assert b.snapshot()['active'] == 15
    assert b.reserve(tmp_path/'next.mp4') is None


def test_reservation_counts_before_http_and_survives_restart(tmp_path):
    b = budget(tmp_path)
    output = tmp_path/'new.mp4'
    assert b.reserve(output)
    assert budget(tmp_path).snapshot()['active'] == 1
    with pytest.raises(RuntimeError, match='reconcile'):
        budget(tmp_path).reserve(output)


@pytest.mark.parametrize('number,age,wait', [(18,100,1700),(35,1900,1700)])
def test_completed_jobs_still_count_against_submission_windows(tmp_path, number, age, wait):
    b = budget(tmp_path)
    seed(b.projects, number, age=age, status='success')
    assert b.snapshot()['active'] == 0
    assert b.snapshot()['available'] == 0
    assert b.snapshot()['retry_after_seconds'] == wait


def test_windows_expire_but_uncertain_job_keeps_slot(tmp_path):
    b = budget(tmp_path)
    seed(b.projects, 1, age=4000, status='timed_out')
    assert b.snapshot()['available'] == 14
    assert b.snapshot()['started_last_hour'] == 0


def test_sidecar_replaces_reservation_not_double_counted(tmp_path):
    b = budget(tmp_path)
    output = b.projects/'clip-0.mp4'
    b.reserve(output)
    seed(b.projects, 1)
    assert b.snapshot()['active'] == 1


def test_account_admission_lock_cannot_be_owned_twice(tmp_path):
    b = budget(tmp_path)
    with b.locked() as acquired:
        assert acquired
        with budget(tmp_path).locked() as second:
            assert not second


def test_corrupt_job_fails_closed(tmp_path):
    b = budget(tmp_path)
    b.projects.mkdir()
    (b.projects/'invalid.modelslab-job.json').write_text('{')
    with pytest.raises(ValueError):
        b.reserve(tmp_path/'new.mp4')


def test_cloud_tick_recovers_before_submitting_and_never_calls_completed(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(cloud, 'recover', lambda p,b: calls.append('recover') or {
        'downloaded': 1, 'total': 1, 'jobs': [{'status': 'downloaded'}]})
    monkeypatch.setattr(cloud, 'submit_batch', lambda *a,**k: pytest.fail('Must not resubmit'))
    result = cloud.tick(tmp_path, [tmp_path/'batch.json'], budget=budget(tmp_path))
    assert result['status'] == 'media_downloaded_qa_pending'
    assert calls == ['recover']


def test_cloud_tick_defers_transient_recovery_without_submitting(tmp_path, monkeypatch):
    monkeypatch.setattr(cloud, 'recover', lambda p,b: {
        'downloaded': 0, 'total': 1, 'jobs': [{'status': 'check_error'}]})
    monkeypatch.setattr(cloud, 'submit_batch', lambda *a,**k: pytest.fail('Uncertain recovery'))
    result = cloud.tick(tmp_path, [tmp_path/'batch.json'], budget=budget(tmp_path))
    assert result['status'] == 'recovery_check_deferred'
    assert result['new_submissions'] == 0


def test_recovery_retry_delay_is_exponential_and_bounded():
    assert [cloud.recovery_retry_delay(30, n) for n in range(1, 6)] == [30, 60, 120, 240, 300]
    with pytest.raises(ValueError):
        cloud.recovery_retry_delay(29, 1)


def test_approved_batches_loads_durable_queue_and_deduplicates(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    first = project / "batch-1.json"
    second = project / "batch-2.json"
    first.write_text("{}", encoding="utf-8")
    second.write_text("{}", encoding="utf-8")
    queue = project / "queue.json"
    queue.write_text(json.dumps({
        "version": "1.1", "project_path": str(project.resolve()), "admission": "enabled",
        "batches": [
            {"path": str(first.resolve()), "state": "approved"},
            {"path": str(second.resolve()), "state": "approved"},
        ],
    }), encoding="utf-8")

    assert cloud.approved_batches(project, [first], queue) == [first.resolve(), second.resolve()]


def test_approved_batches_rejects_outside_project(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        cloud.approved_batches(project, [outside], None)


def test_durable_queue_rejects_relative_batch_paths(tmp_path):
    project = tmp_path / "project"; project.mkdir()
    batch = project / "batch.json"; batch.write_text("{}")
    queue_file = project / "queue.json"
    queue_file.write_text(json.dumps({
        "version": "1.1", "project_path": str(project.resolve()), "admission": "enabled",
        "batches": [{"path": "batch.json", "state": "approved"}],
    }))
    with pytest.raises(ValueError, match="absolute"):
        cloud.approved_batches(project, [], queue_file)


def test_cloud_tick_refills_from_next_approved_batch_while_prior_job_processes(tmp_path, monkeypatch):
    first, second = tmp_path / "batch-1.json", tmp_path / "batch-2.json"
    recovered = {
        first: {"downloaded": 0, "total": 1, "jobs": [{"status": "processing"}]},
        second: {"downloaded": 0, "total": 1, "jobs": [{"status": "not_submitted"}]},
    }
    monkeypatch.setattr(cloud, "recover", lambda p, b: recovered[b])
    calls = []
    monkeypatch.setattr(cloud, "submit_batch", lambda p, b, **k: calls.append(b) or {
        "status": "submitted", "new_submissions": 0 if b == first else 1,
    })
    result = cloud.tick(tmp_path, [first, second], budget=budget(tmp_path))
    assert calls == [first, second]
    assert result["new_submissions"] == 1


def test_recover_only_never_refills_queue(tmp_path, monkeypatch):
    batch = tmp_path / "batch.json"
    monkeypatch.setattr(cloud, "recover", lambda p, b: {
        "downloaded": 0, "total": 1, "jobs": [{"status": "not_submitted"}]})
    monkeypatch.setattr(cloud, "submit_batch", lambda *a, **k: pytest.fail("paid submission forbidden"))
    result = cloud.tick(tmp_path, [batch], budget=budget(tmp_path), allow_submissions=False)
    assert result["status"] == "recovery_only" and result["new_submissions"] == 0


def test_request_not_found_needs_repeated_spaced_confirmation():
    initial = {"provider":"modelslab", "status":"submitted", "request_id":"123"}
    status, first = terminal_disposition(initial, {"status":"failed", "message":"Request not found"}, now=1000)
    assert status == "suspect_terminal" and first["suspect_terminal"]["confirmation_count"] == 1
    status, second = terminal_disposition(first, {"status":"failed", "message":"Request not found"}, now=1200)
    assert status == "suspect_terminal"
    status, final = terminal_disposition(second, {"status":"failed", "message":"Request not found"}, now=1700)
    assert status == "terminal_failed" and final["terminal_confirmation_count"] == 3


def test_explicit_provider_failure_is_terminal_without_not_found_ambiguity():
    status, state = terminal_disposition(
        {"status":"submitted", "request_id":"123"},
        {"status":"failed", "message":"content safety rejection"}, now=1000,
    )
    assert status == "terminal_failed" and state["provider_status"] == "failed"


def test_http_200_rate_limit_body_sets_authoritative_throttle(tmp_path, monkeypatch):
    class Response:
        headers = {}
        def raise_for_status(self):
            return None
        def json(self):
            return {"status": "error", "code": "rate_limited", "retry_after": 77}

    monkeypatch.setattr("requests.post", lambda *args, **kwargs: Response())
    monkeypatch.setattr(shared, "REPO_ROOT", tmp_path)
    result = shared.submit_modelslab("https://example.invalid", "secret", {})
    throttle = json.loads((tmp_path / "work/modelslab-motion-budget/provider-throttle.json").read_text())
    assert result["_rate_limit"]["source"] == "body"
    assert throttle["retry_after_seconds"] == 77
    assert throttle["source"] == "authoritative_provider_response_body"


def test_queue_is_reread_for_dynamic_approved_addition(tmp_path):
    project = tmp_path / "project"; project.mkdir()
    first = project / "first.json"; first.write_text("{}")
    second = project / "second.json"; second.write_text("{}")
    queue_file = project / "queue.json"
    base = {"version":"1.1", "project_path":str(project.resolve()), "admission":"enabled"}
    queue_file.write_text(json.dumps({**base, "batches":[{"path":str(first.resolve()), "state":"approved"}]}))
    assert cloud.approved_batches(project, [], queue_file) == [first.resolve()]
    queue_file.write_text(json.dumps({**base, "batches":[
        {"path":str(first.resolve()), "state":"approved"},
        {"path":str(second.resolve()), "state":"approved"},
        {"path":str(first.resolve()), "state":"approved"},
    ]}))
    assert cloud.approved_batches(project, [], queue_file) == [first.resolve(), second.resolve()]


def test_submission_can_fill_fifteen_slots_not_sixteen(tmp_path, monkeypatch):
    project=tmp_path/'projects'/'chapter'; (project/'artifacts').mkdir(parents=True)
    (project/'chapter_config.json').write_text(json.dumps({'providers':{'video':{
        'provider':'modelslab','model_id':'wan2.2'}},'approval_policy':'full-run-preauthorized'}))
    (project/'artifacts/educational_plan.json').write_text(json.dumps({'sections':[{'section_id':'s1','source_block_ids':['b1']}]}))
    shots=[{'shot_id':f'rain-{i}','section_id':'s1','prompt':
        'Fresh child-friendly three dimensional forest with falling rain and moving foliage, no text or logos.'} for i in range(16)]
    batch=project/'motion-batch-0.json';batch.write_text(json.dumps({'provider':'modelslab','model_id':'wan2.2',
        'operation':'text_to_video','shots':shots}))
    import hashlib
    (project/'artifacts/motion-batch-00-pre-generation-review.json').write_text(json.dumps({
        'version':'1.1','status':'approved_exact_batch_not_submitted','batch_path':str(batch.resolve()),
        'batch_sha256':hashlib.sha256(batch.read_bytes()).hexdigest(),
        'approved_shots':[{'shot_id':row['shot_id'],'section_id':'s1','source_block_ids':['b1']} for row in shots],
        'checks':{'two_visual_review_rounds':True,'unique_shot_ids':True,'unique_reference_hashes':True,
                  'source_matched_sections':True,'generated_text_forbidden':True,'authored_labels_retained':True},
    }))
    calls=[]
    class Tool:
        def execute(self,request):
            calls.append(request)
            return SimpleNamespace(success=True,data={'request_id':str(len(calls))},error=None)
    monkeypatch.setattr(submit,'ModelsLabVideo',Tool)
    b=budget(tmp_path)
    result=submit.submit_batch(project,batch,budget=b)
    assert result['new_submissions']==15 and len(calls)==15
    assert b.snapshot()['active']==15


@pytest.mark.parametrize('state', ['failed','attention'])
def test_chapter_queue_does_not_skip_blocked_chapter(tmp_path,monkeypatch,state):
    monkeypatch.setattr(queue,'input_root',lambda:tmp_path/'inbox')
    root=queue.ensure_queue(tmp_path/'queue')
    (root/state/'chapter-03.json').write_text('{}')
    (root/'pending'/'chapter-04.json').write_text('{}')
    monkeypatch.setattr(queue,'_run_claimed',lambda root:pytest.fail('Must not advance'))
    assert queue.run_once(root) is False
    assert (root/'pending'/'chapter-04.json').exists()
    assert json.loads((root/'worker_status.json').read_text())['status']=='attention'


def test_nonempty_mp4_without_qa_is_rejected(tmp_path):
    video=tmp_path/'video.mp4';video.write_bytes(b'not QA')
    with pytest.raises(FileNotFoundError):
        queue.verify_encoded_completion({'final_video':str(video),
            'chapter_config':str(tmp_path/'chapter_config.json')}, {})
