import { defineRailway, github, project, service, volume } from "railway/iac";

// This named partial owns only OpenMontage. Applying it cannot delete or alter
// unrelated services such as the existing Hermes Agent in the same project.
export const partial = "openmontage";

export default defineRailway(() => {
  const data = volume("openmontage-data", {
    alerts: { usage: { "80": {}, "95": {}, "100": {} } },
    allowOnlineResize: true,
    region: "asia-southeast1-eqsg3a",
    sizeMB: 5120,
  });

  const app = service("OpenMontage", {
    source: github("KrishnaLasya-98/InkSpectrum", {
      branch: "video-dev",
      upstreamUrl: "https://github.com/KrishnaLasya-98/InkSpectrum",
    }),
    replicas: { "asia-southeast1-eqsg3a": 1 },
    networking: { privateNetworkEndpoint: "openmontage" },
    volumeMounts: { "/data": data },
    env: {
      BACKLOT_AUTH_USERNAME: "openmontage",
      BACKLOT_HOST: "0.0.0.0",
      OPENMONTAGE_DELIVERY_DIR: "/data/deliveries",
      OPENMONTAGE_JOB_INPUT_DIR: "/data/inbox",
      OPENMONTAGE_JOB_QUEUE_DIR: "/data/jobs",
      OPENMONTAGE_PROJECTS_DIR: "/data/projects",
      OPENMONTAGE_WORKER_ENABLED: "1",
    },
  });

  return project("pretty-youth", {
    resources: [app, data],
  });
});
