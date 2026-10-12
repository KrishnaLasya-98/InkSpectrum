# Jev: optional advisory decision helper

This helper leaves the coding agent's current chat model unchanged. Jev is a
structured decision tool, not a chat/code generator. It is not wired into
automatic production approval, merging, deployment or command execution.

## Gateway contract

- POST only to `https://api.experientiallabs.ai/v1/systemone`.
- Read only `EXPERIENTIAL_API_KEY` from the process environment. No vendor key,
  dotenv loader, SDK, alternate endpoint or automatic redirect.
- Native JSON: `model`, `state` (text/object/array), and `questions` keyed by caller IDs.
- Default `jev-latest`; explicitly selected `jev-latest:free` is preserved unchanged.
- `choice` uses option-description mappings, `noul` judges a proposition with optional
  true/false descriptions, and `score` uses ordered level descriptions.
- The user-specified gateway admission bounds are 32 questions, 64 choice options,
  and 2-10 score levels. These are gateway bounds, not claims about provider limits.
- Plan for approximately 32,000 shared input tokens across state and question
  definitions, not a total context window or output budget. No exact Jev tokenizer
  is bundled. The 256 KiB local request guard is a byte safety guard, NOT a token estimate.
- One request only; no retries or Idempotency-Key. Timeouts/transport failures can
  leave a charged unknown outcome. HTTP errors are surfaced without unsafe raw bodies.
- Network timeout defaults to 30 seconds (maximum 60 seconds per socket operation).
  Response buffer is limited to 1 MiB. Connections close on success and failure.
- Non-streaming native endpoint only; no Chat Completions, Responses or Messages facade.

## Agent workflow

1. Build a concise sanitized diff summary and test summary. Never send the entire
   repository, secrets, or textbook PDF merely to ask about a small code change.
2. Ask small independent questions sharing that evidence. An answer must not be
   referenced as input to another question in the same request.
3. Validate locally, inspect the request, and ask the user for approval before
   each potentially charged live call. Scheduled video production permission does
   not authorize calls to this new decision service.
4. Read `answers[question_id]`, including `answers['review']`, and present it with
   `reported_usage`. Missing usage is unknown, not zero or free. Do not infer actual
   billing from token counts or a model alias.
5. Treat probabilities/confidence as advisory, not correctness guarantees. Never
   run a returned choice, merge a patch, or bypass deterministic/human review.

Offline validation (zero HTTP requests):

```powershell
python -m tools.analysis.jev_decision_helper config/jev-review.example.json
python -m pytest tests/tools/test_jev_decision_helper.py -q
```

The example contains illustrative evidence, not claims about current production.
Tests mock the network; they do not demonstrate gateway access or model quality.

Only after the user sets a rotated key locally AND approves the specific live call:

```powershell
python -m tools.analysis.jev_decision_helper path/to/reviewed-request.json --approve-live --timeout 30
```

`--approve-live` records the caller's assertion of permission; it is not permission
to be invented by an agent. If the key is missing, stop and request local setup;
never ask the user to paste it. The supplied Bash `export` command does not set
the variable in a Windows PowerShell/Codex process automatically. Restart or launch
the agent from the correctly configured environment as needed. No credentials are
saved by this helper.

## Where it helps this project

Optional triage of summarized patch risks, explicit coverage omissions and missing
QA evidence. It does not inspect an MP4 through this text/JSON helper, verify
pronunciation, generate assets or prove synchronization. Keep source coverage,
ffprobe, motion checks, subtitle alignment and encoded-frame review authoritative.

No packages or skills were installed: the helper uses Python's standard library.
Optional TypeSafe skill installation requires separate user approval and gateway
override; vendor examples using direct provider origins/keys do not apply here.

References consulted:
- https://docs.typesafe.ai/agent-skill
- https://docs.typesafe.ai/introduction/quickstart
- https://docs.typesafe.ai/primitives
- https://docs.typesafe.ai/primitives/noul

Status: mocked/offline validation only until a real, separately approved gateway
response is received. No live success is claimed.
