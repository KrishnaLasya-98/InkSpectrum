import json
import hashlib
from types import SimpleNamespace
import pytest
from tools.video import submit_educational_motion_batch as module
from tools.video.modelslab_motion_budget import MotionBudget

def inputs(tmp_path,frames=None):
 project=tmp_path/'chapter';(project/'artifacts').mkdir(parents=True)
 (project/'chapter_config.json').write_text(json.dumps({'providers':{'video':{'provider':'modelslab','model_id':'wan2.2'}},'approval_policy':'full-run-preauthorized'}))
 (project/'artifacts/educational_plan.json').write_text(json.dumps({'sections':[{'section_id':'s1','source_block_ids':['b1']}]}))
 shot={'shot_id':'new-rain','section_id':'s1','prompt':'A fresh child-friendly three dimensional rainforest with rain visibly falling on moving green foliage, no text or logos.'}
 if frames is not None:shot['num_frames']=frames
 batch=project/'motion-batch-01.json';batch.write_text(json.dumps({'provider':'modelslab','model_id':'wan2.2','operation':'text_to_video','shots':[shot]}))
 (project/'artifacts/motion-batch-01-pre-generation-review.json').write_text(json.dumps({
  'version':'1.1','status':'approved_exact_batch_not_submitted','batch_path':str(batch.resolve()),
  'batch_sha256':hashlib.sha256(batch.read_bytes()).hexdigest(),
  'approved_shots':[{'shot_id':'new-rain','section_id':'s1','source_block_ids':['b1']}],
  'checks':{key:True for key in ('two_visual_review_rounds','unique_shot_ids','unique_reference_hashes',
   'source_matched_sections','generated_text_forbidden','authored_labels_retained')}
 }))
 return project,batch

@pytest.mark.parametrize('frames,expected',[(None,81),(120,120)])
def test_durable_request_keeps_default_and_explicit_frame_budget(tmp_path,monkeypatch,frames,expected):
 calls=[]
 class Tool:
  def execute(self,request):calls.append(request);return SimpleNamespace(success=True,data={'request_id':'mock'},error=None)
 monkeypatch.setattr(module,'ModelsLabVideo',Tool)
 project,batch=inputs(tmp_path,frames);module.submit_batch(project,batch,budget=MotionBudget(tmp_path/'budget',tmp_path))
 assert len(calls)==1 and calls[0]['num_frames']==expected
 assert calls[0]['fps']==16 and calls[0]['generate_audio'] is False

@pytest.mark.parametrize('frames',[80,121,True,100.5])
def test_invalid_frames_stop_before_provider_call(tmp_path,monkeypatch,frames):
 monkeypatch.setattr(module,'ModelsLabVideo',lambda:pytest.fail('Provider must not be constructed'))
 project,batch=inputs(tmp_path,frames)
 with pytest.raises(ValueError,match='num_frames'):module.submit_batch(project,batch)
