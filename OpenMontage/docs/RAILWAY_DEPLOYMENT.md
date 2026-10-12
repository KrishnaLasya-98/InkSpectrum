# Railway deployment

OpenMontage can run on Railway as a persistent Linux service. Codex prepares,
reviews and maintains the system; Railway runs the deployed container after
Codex disconnects.

## What the service runs

The root `Dockerfile` installs Python, Node.js 22, Java 17, FFmpeg, Chromium,
fonts, libsndfile, the pinned HyperFrames runtime and the educational Python
profile. Its default command starts:

- Backlot on `BACKLOT_HOST` and Railway's `PORT`;
- one persistent file-queue worker using the canonical educational CLI.

The worker is intentionally not a replacement orchestration engine. It invokes
`python -m tools.structure.educational_agent_cli run`, preserves checkpoint and
approval behavior, and moves jobs requiring review into `jobs/attention`.

## Required Railway configuration

Use a dedicated Railway project for production when possible. The current
`pretty-youth` project already contains the Hermes Agent and a volume. Railway
Free permits one 0.5 GB volume per project, which is too small for sustained
video production. The included IaC requests a 5 GB volume and therefore needs a
compatible paid plan or a reviewed size change before apply.

Set a compute hard limit before creating resources. Then configure these sealed
variables in Railway:

- `BACKLOT_AUTH_PASSWORD` (required; public startup fails closed without it)
- only the media-provider credentials selected for the production path

The non-secret paths are defined by `.railway/railway.ts` and all live under the
single `/data` volume:

```text
/data/inbox       uploaded source PDFs
/data/jobs        durable pending/running/completed/attention/failed jobs
/data/projects    checkpoints, artifacts, generated assets and renders
/data/deliveries  final delivery copies
```

## Preview and apply infrastructure

From the repository root:

```powershell
railway login
railway link
railway config plan
```

Review every addition and cost-bearing resource. Apply only after approval:

```powershell
railway config apply
```

The Infrastructure as Code file is a named `openmontage` partial, so it does
not own or remove the Hermes Agent service.

After the service exists:

1. Set Railway's healthcheck path to `/api/health`.
2. Generate a public domain for the OpenMontage service.
3. Confirm `/api/health` returns HTTP 200.
4. Confirm all other Backlot routes prompt for the configured Basic credentials.
5. Inspect build/runtime logs and run a dry-run job before paid production.

## Queue a reviewed dry run

With the generated Railway domain in `$serviceUrl`, upload a PDF through the
authenticated API and then submit its reviewed job JSON:

```powershell
curl.exe -u "openmontage:$env:BACKLOT_AUTH_PASSWORD" `
  -X PUT --data-binary "@lesson-1.pdf" `
  "$serviceUrl/api/jobs/input/lesson-1.pdf"
```

POST the following body to `$serviceUrl/api/jobs` with the same Basic
credentials:

```json
{
  "version": 1,
  "id": "lesson-1",
  "approved": true,
  "command": "run",
  "source": "lesson-1.pdf",
  "project_id": "lesson-1",
  "subject": "english",
  "grade": 1,
  "dry_run": true
}
```

For a paid complete run, remove `dry_run` and add
`"full_run_preauthorized": true` only when the user has explicitly granted that
approval. Otherwise the canonical pipeline stops at its normal human gates and
the job result is stored under `jobs/attention`.

Each finished state contains the original job JSON and a matching
`<job-id>.result.json` with bounded stdout/stderr and the CLI result.

## Operational limits

- The service uses CPU rendering and cloud media providers; Railway does not
  provide this container with a local GPU.
- A single worker avoids concurrent writes to the same volume. Scale by moving
  queue/project state to a shared database/object store, not by adding replicas
  to a volume-backed service.
- A Railway healthcheck gates deployment activation; it is not continuous
  monitoring. Configure separate uptime monitoring if required.
- `.mp3` and `.mp4` remain excluded from Git. Generated media belongs on the
  Railway volume or external object storage.
