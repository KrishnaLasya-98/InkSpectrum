"""Offline regression coverage for saved-job polling at the deadline."""
from unittest.mock import Mock, patch

import pytest
import requests

from tools.video._modelslab_shared import poll_modelslab


def test_first_transport_failure_at_deadline_is_resumable_timeout():
    with patch('tools.video._modelslab_shared.time.time', side_effect=[0, 0, 2]), \
         patch('requests.post', side_effect=requests.Timeout('transport failed')) as post:
        with pytest.raises(TimeoutError, match='12345 timed out after 1s'):
            poll_modelslab('12345', 'mock-key', endpoint='video', timeout=1)
        assert post.call_count == 1


def test_later_transport_failure_does_not_reuse_old_processing_response():
    response = Mock()
    response.json.return_value = {'status': 'processing'}
    with patch('tools.video._modelslab_shared.time.time', side_effect=[0, 0, .1, .2, 2]), \
         patch('tools.video._modelslab_shared.time.sleep'), \
         patch('requests.post', side_effect=[response, requests.Timeout('transport failed')]) as post:
        with pytest.raises(TimeoutError, match='12345 timed out after 1s'):
            poll_modelslab('12345', 'mock-key', endpoint='video', timeout=1)
        assert post.call_count == 2


def test_transient_fetch_error_can_still_recover_same_job():
    response = Mock()
    response.json.return_value = {'status': 'success', 'output': ['https://example.invalid/clip.mp4']}
    with patch('tools.video._modelslab_shared.time.time', return_value=0), \
         patch('tools.video._modelslab_shared.time.sleep'), \
         patch('requests.post', side_effect=[requests.Timeout('temporary'), response]) as post:
        result = poll_modelslab('12345', 'mock-key', endpoint='video', timeout=30)
        assert result['status'] == 'success'
        assert post.call_count == 2
        assert all(call.args[0].endswith('/fetch/12345') for call in post.call_args_list)


def test_exhausted_fetch_retries_remain_bounded():
    with patch('tools.video._modelslab_shared.time.time', return_value=0), \
         patch('tools.video._modelslab_shared.time.sleep'), \
         patch('requests.post', side_effect=requests.Timeout('temporary')) as post:
        with pytest.raises(RuntimeError, match='5 consecutive errors'):
            poll_modelslab('12345', 'mock-key', endpoint='video', timeout=30)
        assert post.call_count == 5
