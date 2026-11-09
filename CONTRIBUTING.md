# Contributing to MotionLab

Follow the macOS setup and model download instructions in README.md. Use Python 3.12 and Node 24 or later. The backend and frontend run in separate terminals. All processing is local.

Create a branch for a focused change. Run the backend tests, frontend tests, and frontend production build before opening a pull request. Include the problem, resulting behavior, validation, and material limitations in the PR description. GitHub Actions runs the automated suite on pushes and pull requests; real-model accuracy checks are a separate validation activity.

Keep API routes, ingestion, pose estimation, marker tracking, biomechanics, synchronization, and reconstruction separate. Use generated identifiers for files. Preserve original video bytes and timing metadata. Record method/version changes when changing measurements; do not silently compare incompatible conventions.

Do not commit personal recordings, generated analysis, model weights, credentials, virtual environments, or node_modules. Automated tests use generated FFmpeg fixtures and deterministic detector doubles. Share real recordings only through an explicitly agreed private channel with the subject's consent.

Bike-fit guidance requirements and the staged research/validation plan are in docs/BIKE_FIT_EVIDENCE.md. Angle estimates are not validated fit recommendations. Changes to measurement conventions or guidance must include source references and an explicit validation plan.

No open-source license has been selected yet. The repository owner must choose one before treating this as an openly licensed project.
