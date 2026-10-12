# Educational setup, start and resume

Run from the OpenMontage repository root. All commands use
`python -m tools.structure.educational_agent_cli`.

The authoritative dependency profiles, platform prerequisites, OCR setup,
verification commands and installation ledger are documented in
[`INSTALLATION_GUIDE.md`](INSTALLATION_GUIDE.md). Every dependency install,
removal or upgrade must update that guide and the matching manifest.

- `setup`: read-only dependency report. Exit 2 means setup is incomplete.
- `setup --install-python`: Conda-first installation into `.conda-educational`
  when Conda is discoverable via CONDA_EXE or PATH, otherwise `.venv-educational`.
  Select explicitly with `--manager conda` or `--manager venv`. Existing Conda
  prefixes are checked, never updated or deleted. Existing active environments
  can be reused by running `setup` with their interpreter if checks pass.
  Conda includes FFmpeg and Node; HyperFrames/browser still need separate checks.
  Use `conda run --prefix .conda-educational python -m tools.structure.educational_agent_cli start`
  for the new environment. Neither definition is a tested platform lockfile.
- `start`: returns the missing PDF input request without executing production.
- `start chapter.pdf --project-id new-chapter --grade 1 --subject english`:
  guided production using the existing runner. `--dry-run` is a structural test,
  not a quality-approved video. Paid execution still requires approval gates.
- `resume projects/new-chapter`: read-only checkpoint recovery, returning the
  next stage, director skill and artifact directory to the coding agent. The
  agent must read that stage's checkpoint/partial outputs and skill, preserve
  approvals, and execute only unfinished work. This is NOT an unattended
  stage-execution scheduler. Do not rerun ingestion to resume an existing project.
- `references`: verify the lightweight screenshot package and any available
  reference MP4s. Full videos are optional on VMs; require them explicitly with
  `--require-full-video`. Do not silently rebaseline changed files.

## Reference contract

`config/educational-reference-lock.json` records approved English, EVS and Maths
video identities and presentation expectations. Original MP4s are not copied or
edited. Hash checking detects changed references; it does not establish visual
similarity of a new output. Follow its regression checklist on new encoded MP4s.
Newer user timing requirements override the older videos. The manifest records
these rules; it does not retrofit historical videos or replace chapter config.

## Agent onboarding

Conda specs: `environment.yml` for complete educational production and `environment-manim.yml`
for the optional isolated renderer. Create the latter explicitly with
`conda env create -f environment-manim.yml`; set `OPENMONTAGE_MANIM_PYTHON` to its
Python executable. Local speech/alignment models remain optional separate
installs. Windows/Linux environment solves and real renders must be validated
before claiming cloud portability. Conda mechanics follow
https://docs.conda.io/projects/conda/en/stable/commands/env/create.html.

A greeting is not installation or spending authorization. Offer setup, report
missing dependencies, and ask for a PDF. Never print keys. Resume existing work
before creating a replacement project. Only call videos final after encoded QA.
Provider-job receipts support restart-safe polling, while the encoded comparison
tool verifies deterministic technical/source/reference gates and emits a contact
sheet. Live provider entitlement and semantic/aesthetic pixel review are still
external gates; neither may be inferred from unit tests or hashes.

## Deployment without large media

Commit `tests/fixtures/educational-reference/` with the code, reference lock,
shared template and documentation. Its nine small JPEGs replace mandatory MP4
downloads for reference access. See the package README for the no-cost fixed
composer tests and required real-render review. Missing optional videos do not
block baseline integrity checks; this does not waive final video QA.
