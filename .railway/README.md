# OpenMontage on Railway

This directory uses Railway Infrastructure as Code, the supported replacement
for deprecated `railway.toml` / `railway.json` service configuration.

The configuration is a named partial (`openmontage`). It owns only the
OpenMontage service and volume, so it cannot remove unrelated resources in the
same Railway project.

Before applying:

1. Set a workspace compute hard limit in Railway.
2. Confirm the plan supports a 5 GB volume. Railway Free currently permits only
   one 0.5 GB volume per project; the existing `pretty-youth` project already
   has the Hermes Agent volume. Use a separate project or a plan with enough
   volume capacity for rendered video.
3. Add `BACKLOT_AUTH_PASSWORD` as a sealed Railway variable. The container
   refuses to bind publicly without it.
4. Add only the provider credentials needed by the selected OpenMontage path.
5. Review the plan before applying it:

```powershell
railway link
railway config plan
railway config apply
```

After deployment, set `/api/health` as the Railway healthcheck and generate a
public domain for the OpenMontage service. The Dockerfile supplies the start
command and also contains a container healthcheck.

Upload source PDFs through authenticated `PUT /api/jobs/input/{filename}` and
queue reviewed JSON with `POST /api/jobs`. The persistent worker invokes
`tools.structure.educational_agent_cli`; it never bypasses the pipeline's
checkpoints or approval policy. See `docs/RAILWAY_DEPLOYMENT.md`.
