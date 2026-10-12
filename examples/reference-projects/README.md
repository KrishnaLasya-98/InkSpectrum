# Portable reference project bundles

These ZIP archives contain the portable authoring files behind the educational
reference videos. They preserve project-relative structure and include source
code, HyperFrames HTML/CSS/JavaScript, configuration, manifests, narration and
timing metadata, subtitles, prompts, and QA reports where available.

The public bundles intentionally exclude:

- rendered video, audio, and generated image binaries;
- source textbook PDFs and other original book files;
- API credentials, `.env` files, browser profiles, provider caches, and job
  authentication data;
- local Python/Conda environments, `node_modules`, frame caches, snapshots, and
  temporary render output.

Rendered examples are stored separately in `../reference-videos/` through Git
LFS. After cloning, run `git lfs pull` before extracting those video archives.

Included portable project bundles:

- `english-class1-lesson1-at-the-beach.zip`
- `evs-lesson-8.zip`
- `maths-class1-chapter8-two-digit-numbers.zip`
- `class-5-social-part-0-chapter-1-latitudes-and-longitudes.zip`
- `class-5-social-part-0-chapter-2-earth-movement.zip`
- `class-5-social-part-0-chapter-3-worlds-weather-and-climate.zip`
