from tools.video.modelslab_video import ModelsLabVideo


def test_i2v_respects_live_maximum_120(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setenv('MODELSLAB_API_KEY', 'test-key')
    def submit(url, api_key, payload, *, timeout):
        captured.update(payload)
        return {'id':'mock-job', 'status':'processing'}
    monkeypatch.setattr('tools.video.modelslab_video.submit_modelslab', submit)
    result = ModelsLabVideo().execute({
        'model_id':'wan-2.2-i2v','operation':'image_to_video',
        'image_url':'https://example.test/reference.png', 'prompt':'Rotating globe',
        'num_frames':122,'fps':16,'submit_only':True,
        'output_path':str(tmp_path/'clip.mp4')})
    assert result.success, result.error
    assert captured['num_frames'] == 120
    assert captured['fps'] == 16
