"""Local CPU MediaPipe adapter. Models are loaded only when a job starts."""
from pathlib import Path

class PoseTracker:
    def __init__(self, model_path: Path):
        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision
        self.mp = mp
        self.detector = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=str(model_path), delegate=python.BaseOptions.Delegate.CPU),
            running_mode=vision.RunningMode.VIDEO, num_poses=1,
            min_pose_detection_confidence=0.5, min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5))

    def detect(self, rgb, timestamp_ms):
        result = self.detector.detect_for_video(self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb), timestamp_ms)
        if not result.pose_landmarks:
            return None
        return [{"x": float(p.x), "y": float(p.y), "visibility": float(p.visibility or 0), "presence": float(p.presence or 0)} for p in result.pose_landmarks[0]]

    def close(self):
        self.detector.close()
