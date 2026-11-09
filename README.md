# MotionLab — video ingestion and joint tracking preview

Local-first cycling video ingestion and a bounded 2D joint-tracking preview. Upload Side and Front recordings independently; Rear is optional. Run a 1–30 second clip to see a MediaPipe skeleton, confidence-gated hip/knee/ankle estimates, and an angle timeline. Colored-dot tracking, camera synchronization, calibration, 3D reconstruction, and bike-fit recommendations are **not implemented**.

## macOS setup

From the project root in VS Code's terminal:

```sh
brew install uv ffmpeg node
uv python install 3.12
uv venv --python 3.12 .venv
# Check MediaPipe compatibility before the full install:
uv pip install --python .venv/bin/python --dry-run mediapipe==0.10.21
uv pip install --python .venv/bin/python -r backend/requirements.lock.txt
.venv/bin/python -c 'from mediapipe.tasks.python.vision import PoseLandmarker; print("PoseLandmarker import OK")'
npm ci --prefix frontend
mkdir -p models
curl -fL --output models/pose_landmarker_lite.task https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task
shasum -a 256 models/pose_landmarker_lite.task
# Expected: 59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a
```

Select `.venv/bin/python` using VS Code's **Python: Select Interpreter**. Python 3.12 is explicitly selected; do not use the system Python 3.14 for this environment. `requirements.txt` pins direct backend dependencies; `requirements.lock.txt` records the complete tested environment. `package-lock.json` pins frontend dependencies. OpenCV is supplied by `opencv-contrib-python`; do not install a second OpenCV distribution alongside it. The setup downloads the version-1 Pose Landmarker Lite model from Google. The model is ignored by Git; after setup, inference and video processing run locally without network access. You may override the model path with `MOTIONLAB_POSE_MODEL`.

## Start the app

Terminal 1, from the project root:

```sh
source .venv/bin/activate
cd backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2, from the project root:

```sh
npm run dev --prefix frontend -- --port 5173 --strictPort
```

Open http://127.0.0.1:5173. API documentation: http://127.0.0.1:8000/docs. Health: http://127.0.0.1:8000/health. Stop either server with Ctrl+C. Both servers bind to the local loopback interface. Vite proxies `/api` and `/health` to FastAPI; run both servers for uploads. `npm run build` produces static assets but does not deploy the app.

## Recording and upload contract

- Use MP4 or MOV containing exactly one real video stream, encoded as H.264 or HEVC (H.265). HEVC and H.264 color formats outside 8-bit 4:2:0 receive a separate, silent H.264/yuv420p MP4 preview for browser compatibility. Originals remain unchanged. Unsupported-codec errors include the detected codec and pixel format.
- Defaults: 500 MiB (524,288,000 bytes) per file, 300 seconds, and no dimension above 4096 pixels. Audio is preserved in the original but is not analyzed; browser support for its codec can vary.
- The server checks file extension, actual container, codec, dimensions, duration and frame rate with ffprobe, then decodes the entire video with FFmpeg. Validation has timeouts (30 seconds probe, 180 seconds decode); large files may need shorter recordings. Preview conversion runs locally with a 180-second timeout; a timeout removes partial files and rejects the upload. Source metadata always describes the original, not the preview. Preview conversion is not calibrated color processing or HDR tone mapping: HDR footage may look different in the preview, so future colored-marker analysis must use the original and explicit color handling.
- Upload fields: `POST /api/videos`, multipart `view` (`side`, `front`, `rear`) and `file`. Returns HTTP 201 with video ID, view, dimensions, duration, frame rate, codec, size, timestamps, and content URL. Errors use `detail` and HTTP 413/415/422; missing FFmpeg returns 503. Media-tool failures identify metadata inspection, frame decoding, or preview conversion and include a bounded FFmpeg diagnostic with local storage paths redacted. The backend also logs these diagnostics.
- `GET /api/videos/{id}` reads metadata; `GET /api/videos/{id}/content` serves the original video. When `preview_url` is present, the UI plays `GET /api/videos/{id}/preview` instead. Invalid or unknown IDs return 404.
- Original bytes, a JSON sidecar, and a compatible preview when needed are stored in `data/` by default, named with generated UUIDs. User filenames are never used for storage. Failed uploads are removed. A streaming request limit bounds multipart spooling, with 64 KiB of multipart overhead allowed; the exact file limit is checked separately.
- Uploaded files persist across backend restarts. The dashboard restores the latest upload for each view and that video’s latest tracking result after refresh. Replacing a view uploads another original and retains the prior file on disk. There is no session grouping or delete API. The latest uploads are selected by view, not assumed to be the same recording session. Files can be removed from the data directory with the servers stopped.

To change the storage path or limits, set environment variables before starting the backend:

```sh
export MOTIONLAB_DATA_DIR="$PWD/local-data"
export MOTIONLAB_MAX_BYTES=524288000
export MOTIONLAB_MAX_DURATION=300
```

If changing limits, update the dashboard's displayed guidance too. Use an absolute data path. Custom data directories should also be excluded from Git.

## Architecture and timing

```text
backend/
  app/
    api/                 HTTP routes
    ingestion/           Validation, metadata schema, local video store
    config.py            Storage and limits
    main.py              Application factory and request-size guard
    pose/                MediaPipe adapter, bounded background clip jobs
    markers/             Reserved: physical marker tracking
    biomechanics/        Confidence-gated image-plane interior angles
    synchronization/     Reserved: explicit offsets and timestamp alignment
    reconstruction/      Reserved: camera calibration and 3D reconstruction
  tests/                 Real FFmpeg fixture integration tests
frontend/
  src/                   React UI, API client, styles and UI tests
data/                     Ignored originals, previews, metadata, analysis results
models/                   Ignored downloaded Pose Landmarker model
```

Schema version 1 preserves rational average and nominal frame rates, stream time base, start PTS, duration ticks, frame count when available, source creation time, rotation, and UTC upload time. Duration and dimensions describe the encoded stream; rotation is stored separately. Missing source metadata remains null. Decoding and preview encoding explicitly use the source time base with timestamp passthrough, avoiding frame timestamp collisions when variable-rate phone video is rounded to nominal FPS. Average FPS is **not** a per-frame timeline, and variable-frame-rate sources require future per-frame PTS extraction. Source creation time and simultaneous recording do not establish synchronized clocks. Include a visible sync cue in all recordings; future alignment will require explicit offsets. Accurate 3D reconstruction requires calibration and validation, not merely three camera views.

## Tests and build

```sh
(cd backend && ../.venv/bin/python -m pytest -q)
npm test --prefix frontend
npm run build --prefix frontend
```

Backend tests generate small real MP4/MOV videos using FFmpeg. They cover health, three view labels, stored bytes and metadata, restart persistence, invalid uploads, codec/duration rejection, file/request limits, cleanup, unknown IDs and missing media tools. Frontend tests exercise the UI with a mocked network boundary. Manual browser playback remains a useful check with your own phone recordings.

## Verified development environment

macOS ARM64: system Python 3.14.10; selected Python 3.12.15; Node.js 26.13.0; npm 11.20.0; Git 2.56.0; FFmpeg/ffprobe 9.0.2 (installed during setup). MediaPipe 0.10.21 and PoseLandmarker import verified; OpenCV 4.11.0, NumPy 1.26.4, SciPy 1.15.3. The MediaPipe wheel dependency check succeeded before installing the full backend set. Local Pose Landmarker inference was verified on the uploaded Side and Front recordings. macOS MediaPipe may initialize graphics services even when CPU inference is selected; run normally in your local VS Code terminal rather than a restricted headless sandbox.

Latest verification: **40 backend tests passed; 12 frontend tests passed; production build passed.** Live health checks, an upload through the frontend proxy, and preview HTTP byte ranges passed. npm audit reported zero known vulnerabilities. Backend tests emit one upstream Starlette/AnyIO deprecation warning. Browser playback and visual layout were not manually verified in this environment.

A full 213.77-second iPhone HEVC/HDR variable-frame-rate recording (12,821 frames) also passed the updated ingestion pipeline and preview generation. The original was left unchanged; this check used temporary storage.

## Use the joint-tracking preview

1. Open the dashboard. Previously uploaded videos restore automatically; a rear recording is optional.
2. Under a view, set **Start (s)** and **Length (s)** (1–30 seconds), then choose **Run joint tracking**. Processing runs in the background, one clip at a time.
3. Play the tracking video to see the skeleton, choose anatomical Left or Right, and inspect hip, knee, and ankle angles and their timeline. Green skeleton edges represent anatomical left; pink represent right. These colors do not label the physical marker colors. The initial side selector chooses the side with more valid knee samples.
4. Results are saved under `data/analyses/{analysis_id}/`. Refresh restores the latest result for each selected video. A server restart marks interrupted jobs failed; rerun those jobs.

The current two recordings are separate sessions. The application does not align their claps, share timestamps between them, or fuse their landmarks. A sync cue is only useful for recordings of the same event. The initial local verification processed seconds **10–20** independently from each uploaded view, detecting a pose in **150/150 samples** from each. Right-side knee estimates passed the threshold in all Side samples; the occluded left knee passed in none. Both knees passed in the Front samples. Detection coverage is not a measurement-accuracy claim.

Tracking uses the original video. FFmpeg applies display rotation, samples at 15 Hz, and scales to fit 960×960 pixels while preserving aspect ratio. Samples are indexed on this regular playback-time grid; they are not a preserved per-frame source PTS table, and individual displayed samples can differ by a sampling interval. MediaPipe runs locally in VIDEO mode, with increasing millisecond timestamps. All 33 normalized 2D landmarks, presence/visibility scores, nullable angle estimates, clip offsets, and method information are saved. Missing poses remain missing; there is no invented interpolation. Temporary sampled JPEGs are removed after processing.

Angles use pixel coordinates corrected for frame aspect ratio and the interior angle at the middle point: hip = shoulder–hip–knee; knee = hip–knee–ankle; ankle = knee–ankle–toe. Values range from 0 to 180 degrees; 180 is straight. They are not automatically converted to a clinical flexion convention. Each constituent landmark must have both visibility and presence of at least 0.6 and lie inside the frame. Degenerate geometry returns null. Hidden/occluded joints and off-axis camera placement limit estimates. Front-view projected angles do not measure sagittal flexion reliably. No physical marker association, calibrated accuracy, 3D measurement, or clinical interpretation is claimed.

Analysis API: `GET /api/videos` lists saved uploads; `POST /api/videos/{id}/analyses` accepts `start_seconds` and `duration_seconds` and returns a job (202). `GET /api/analyses/{id}` reports status/progress/error; `GET /api/analyses/{id}/result` returns completed data; `GET /api/videos/{id}/analyses/latest` restores the latest job. A second job while processing receives 409. Missing model weights receive 503. Analysis tests use a deterministic detector double and real FFmpeg frame extraction; real-model checks on the two local recordings are performed separately from the automated suite.

Implementation follows the [official MediaPipe Pose Landmarker Python guide](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker/python).

## Compare a new bike position

Upload the raised-seatpost recording using **Upload another video** under Side. The original stays on disk and remains available in **Saved side recording**. Save distinct labels using **Save setup details**; optionally enter `20` for a self-reported seatpost-extension change in millimeters. This annotation is relative to your intended baseline, not an absolute saddle-height measurement.

Run tracking on a comparable steady-pedaling clip in both recordings, using the same visible anatomical side. Under **Compare two bike positions**, refresh tracking results, choose baseline and candidate, and compare. A rear recording and camera synchronization are not required. The comparison reports interior-angle medians, percentile ranges, and valid-sample counts. Positive changes mean candidate minus baseline, not better fit. Samples are not aligned by crank phase, and uncertainty has not been validated. An increase in seatpost extension is not assumed to cause a fixed angular change.

Setup annotations persist via `PATCH /api/videos/{id}/setup` with `label` and nullable `seatpost_extension_change_mm`. `GET /api/comparisons` accepts `baseline_analysis_id`, `candidate_analysis_id`, and `side` (`left`/`right`). Both analyses must be complete and from different side-view recordings. Method/convention/model mismatches are rejected when both results carry those fields. Legacy results without full provenance are explicitly flagged. New tracking results include model SHA-256, tracking version, angle convention, and confidence threshold. No fit recommendation is returned.

Read [CONTRIBUTING.md](CONTRIBUTING.md) for collaboration and [the evidence/validation plan](docs/BIKE_FIT_EVIDENCE.md) for the path to professional bike-fit insight. No open-source license has been chosen. The GitHub Actions workflow runs backend tests and frontend tests/build on pushes and pull requests; its remote run must be checked after publishing.
