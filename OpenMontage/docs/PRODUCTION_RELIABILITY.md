# Production reliability and recovery

## Runtime contract

- One worker owns a queue volume at a time through an OS advisory lock.
  Use a filesystem supporting Windows byte locks/POSIX flock; do not assume
  arbitrary network/object storage provides these semantics.
- `OPENMONTAGE_RESULT_PATH` is an internal CLI-to-worker JSON result channel.
  Stage progress goes to stderr; stdout remains readable JSON for normal CLI use.
  Logs are never parsed to infer successful completion.
- A real job needs explicit `completed` status and a nonempty final-video file.
  The pipeline's existing coverage and encoded-QA gates remain authoritative.
  `dry_run_complete` is accepted only for explicitly dry-run jobs.
- Each active job writes `logs/<job-id>/heartbeat.json` every five seconds.
  stdout/stderr each have a bounded 100 KB in-memory tail and two rotating
  4 MB log files. Older log content is discarded; canonical artifacts persist.

## Interrupted jobs

On obtaining the queue lock, the worker moves abandoned `running` jobs to
`attention` with `recovery_required`. It does **not** automatically resubmit
paid work or claim the chapter is finished. Inspect the heartbeat, logs,
project checkpoints and provider job sidecars first. Reconcile any surviving
child processes and pending provider jobs before a deliberate retry.

Timeouts, Python cancellation and SIGTERM attempt cleanup of the owned process
tree (Windows taskkill / POSIX process group). A host crash, SIGKILL, or a process
that detaches from its group cannot be guaranteed clean by this mechanism.
Use the deployment supervisor/container to terminate remaining descendants.
Unattended reconciliation of these ambiguous states is not yet implemented.

## Rendering

- Default: one worker, low-memory mode. Explicit settings are preserved.
- `OPENMONTAGE_RENDER_TIMEOUT_SECONDS` defaults to 43200 (12 hours).
  Per-call `render_timeout_seconds` overrides it. The whole worker job deadline
  is separately controlled by `OPENMONTAGE_JOB_TIMEOUT_SECONDS` (also 43200).
  Allow headroom for ingestion/generation when configuring the whole-job limit.
- Preflight estimates output and temporary storage from HTML dimensions,
  duration and frame rate. Multiple workers are conservatively budgeted as
  screenshot capture because streaming support varies. This is an estimate,
  not a storage reservation or proof that the renderer will fit.
- Render logs reside under the workspace's `render-logs` directory.

## Narration and media

- Downloads stream to unique `.part` files, verify nonempty/advertised length,
  and atomically replace the destination. Failed downloads preserve existing media.
- TTS persists a sanitized request fingerprint and provider recovery fields per
  attempt before continuing. An interrupted initial POST stays `submitting`:
  do not delete that sidecar to force a retry without reconciling the provider.
  Known submitted responses are reused instead of resubmitting on restart.
- Completed narration segments checkpoint atomically after each segment.
  Validation-version fingerprints invalidate older ambiguous QA cache entries.
- Failed STT is not a zero-error result; it blocks that provider segment.
  Disabled STT and local Kokoro synthesis are explicitly `unverified`, not QA
  passes. Speech alignment and encoded-output review are still required.
- Kokoro loads lazily once per synthesizer instance, shared through recursive
  exercise processing and the reviewed-plan runner. WhisperX holds one cached
  transcription model and one language aligner per process. These bounded caches
  intentionally retain model memory; they are not evidence of a leak.
- Audio assembly streams blocks and silence to an atomic WAV rather than
  concatenating all parts in RAM.

## Validation scope

Regression tests inject timeout, missing result, restart, lock contention,
download truncation, ambiguous TTS submission, STT failure and partial-batch
failure. They do not certify provider availability or visual quality.

Before 24/7 production, run a full chapter and a multi-chapter soak test with
RSS, descendant count, free disk, queue age and generation IDs monitored. Verify
the final encoded MP4 against the textbook and approved visual references.

No additional packages were installed for these changes. Runtime utilities use
the standard library plus the project's existing requests/soundfile/numpy.
