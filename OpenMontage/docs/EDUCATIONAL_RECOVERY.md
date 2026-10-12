# Educational dependency and recovery contract

The shared tracker is used by the educational runner and portable agents.

- Begin a stage before work. Existing artifacts and partial progress remain
  available for inspection; they are not proof that a new attempt succeeded.
- While an upstream stage is unfinished, downstream status is blocked.
- Finishing with changed JSON artifacts invalidates every later checkpoint.
  Failure also invalidates later checkpoints. Old artifacts remain on disk and
  superseded checkpoints remain in history; no media is deleted.
- An unchanged rerun can retain content-bound approval. Legacy checkpoints
  without approval hashes require review. Never bypass a failed checkpoint just
  because an old MP4 still exists.
- Use `tracker.progress(stage, partial_progress=...)` after durable item updates.
  Record completed scene IDs, provider job IDs, and validated output locations;
  never record API keys. Progress must be written during an in-progress stage.
- `resume` returns the next unfinished stage, artifacts and partial progress.
  Query pending provider jobs before submitting replacements. Resume itself
  does not generate media, approve content or promise exactly-once API calls.

Boundaries: JSON fingerprints do not hash arbitrary referenced files. This
contract assumes one writer per project. Provider timeout reconciliation,
multi-process leases and live PDF-to-encoded-video QA remain separate work.
Local regression tests simulate interruptions; they do not certify narration,
visual fidelity, textbook coverage or provider billing behavior.
