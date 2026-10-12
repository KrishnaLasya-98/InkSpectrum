# Structured answer and diagram review

Non-arithmetic derived answers and sample responses can now use an explicit
review record. This verifies record completeness and content binding, not the
truth of the reviewer identity or the answer itself. A real teacher or a
separate reviewing agent must inspect the source and reasoning; do not create
an approval merely to pass the gate.

## Author the question

Keep the original question in `teaching_contract.questions`. Supply ordered
`source_block_ids` (or legacy `source_block_id`). For diagrams, add separate
`visual_source_block_ids` pointing to figure, table, or equation blocks. Include
all referenced blocks in the section's `source_block_ids`. Do not concatenate
figure alt text into the spoken question.

Set `answer_kind` to `derived` or `sample_response` and use:

```json
"answer_evidence": {"method": "reviewed", "review_id": "review-question-1"}
```

Printed answers still use the exact-text source check; a review does not turn
a derived answer into a printed textbook answer.

## Record the independent review

The runner reads a list from `artifacts/exercise_reviews.json`. Get the current
`review_content_sha256` from `exercise_resolution.json`. A review template is:

```json
[
  {
    "review_id": "review-question-1",
    "content_sha256": "COPY_CURRENT_FINGERPRINT",
    "decision": "pending",
    "reviewer": {"type": "human", "id": "REVIEWER_ID"},
    "reviewed_at": "ISO_TIMESTAMP_WITH_TIMEZONE",
    "rationale": "",
    "checks": {
      "textbook_fidelity": false,
      "answer_correctness": false,
      "grade_appropriate": false,
      "diagram_accuracy": false
    },
    "visual_observations": []
  }
]
```

`reviewer.type` may be `human` or `agent`. If `author_id` is supplied on the
question, the reviewer ID must differ. IDs are recorded declarations, not
authenticated identities. Approval requires a timezone-aware timestamp,
nonempty rationale, and true fidelity/correctness/grade checks. Visual questions
also require `diagram_accuracy: true` and a nonempty observation per visual:

```json
{"source_block_id": "figure-1", "observation": "Describe the inspected label, arrow, shape, or relation supporting the answer."}
```

Only change `decision` to `approved` after actually reviewing. Pending, rejected,
missing, duplicate, or stale reviews block strict production. Changes to the
question, answer, answer kind, solution steps, or referenced source blocks
(including diagram geometry/media metadata) invalidate the review fingerprint.
Changing image bytes without updating source metadata is not detected by this
fingerprint; media integrity/encoded visual QA remains a separate requirement.

## Boundaries

- No paid generation, automatic approval, or arbitrary code execution.
- Reviews do not implement diagram animation, labels, or interaction rendering.
- Final authored coverage and encoded-output QA remain mandatory.
- Legacy projects report findings; projects requiring the teaching contract
  stop before paid generation when exercise resolution is blocked.
