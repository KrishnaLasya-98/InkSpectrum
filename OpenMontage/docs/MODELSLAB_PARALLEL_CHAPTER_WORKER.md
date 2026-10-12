# Parallel cloud motion, sequential verified chapters

Implemented 2026-10-06. No dependency installation or provider change.

## Verified limits and execution policy

ModelsLab Open Source Unlimited documents 15 simultaneous generations,
18 video/3D starts per 30 minutes, and 35 per hour. Unlimited means no
monthly open-source generation total, not unlimited instantaneous throughput.
Source: https://modelslab.com/rate-limits (checked 2026-10-06).

`submit_educational_motion_batch` defaults to up to 15 **asynchronous** jobs.
HTTP submissions remain serialized behind the account admission lock; GPU jobs
then run concurrently at ModelsLab. It accounts for durable jobs in all local
projects and reserves capacity before HTTP. Finished jobs still consume the
submission-window allowance. Unknown outcomes retain their reservation and
must be reconciled rather than automatically retried. Legacy sidecars without
a submission timestamp use last-write time conservatively.

All workers using the same API account must share
`OPENMONTAGE_MODELSLAB_STATE_DIR` and the same projects root. This local ledger
cannot discover jobs from an unrelated machine/client, image/audio jobs outside
its sidecars, or provider-specific caps. Provider error bodies remain
authoritative: stop and reconcile; do not spin on rate-limit responses.

## Recover-and-refill worker

Run `python -m tools.video.educational_motion_worker --project <project>
--batch <approved-batch.json> [--batch <another.json>] --watch`.

It recovers all existing jobs in the selected chapter before submitting missing
shots, persists progress under `artifacts/cloud-motion-worker/status.json`,
holds one worker lock per chapter, and exits when downloads are complete or an
uncertain/failed recovery requires attention. Polling is at least 30 seconds.
It does not generate plans, approve media semantics, render locally, publish
videos, start another chapter, or send a future chat notification.

## Verified chapter advancement

The persistent educational job worker now stops if any queued predecessor has
failed or requires attention. A live `completed` result is accepted only with:

- a completed quality-assurance checkpoint;
- a passing final review naming this exact MP4;
- existing encoded contact sheets recorded as reviewed;
- a passing nonempty textbook/reference comparison gate set;
- a candidate SHA-256 matching the actual MP4.

Dry runs remain explicitly separate. These checks consume review evidence;
they do not invent visual approval or replace an actual semantic review.
Do not enqueue later chapters until the current externally running chapter has
completed and the approved chapter-specific production adapter is ready. The
generic CLI must not overwrite a curated chapter or substitute its template.

## Current Class 5 Social run

Chapter 3 has 29 existing completed Wan jobs, so the cloud worker smoke check
performed **zero new generation submissions** and exited with
`media_downloaded_qa_pending`. Its one-worker precision-animation process remains
active. Do not create a second local render. This change does not establish a
fully autonomous Chapter 3-to-13 source/planning/composition operator or a chat
notification service; those are still separate integration work.

Verification: 42 focused offline tests passed (budget/concurrency, submission
frames, queue, and process reliability). No paid concurrency test was necessary
because all approved Chapter 3 cloud media already existed.
