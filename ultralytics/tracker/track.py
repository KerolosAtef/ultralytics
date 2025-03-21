# Ultralytics YOLO 🚀, AGPL-3.0 license

from functools import partial

import torch

from ultralytics.yolo.utils import IterableSimpleNamespace, yaml_load
from ultralytics.yolo.utils.checks import check_yaml

from .trackers import BOTSORT, BYTETracker

TRACKER_MAP = {'bytetrack': BYTETracker, 'botsort': BOTSORT}


def on_predict_start(predictor, persist=False, multiple_videos=False):
    """
    Initialize trackers for object tracking during prediction.

    Args:
        predictor (object): The predictor object to initialize trackers for.
        persist (bool, optional): Whether to persist the trackers if they already exist. Defaults to False.
        multiple_videos (bool, optional): Whether input frames of the same video or different. Defaults to False.
    Raises:
        AssertionError: If the tracker_type is not 'bytetrack' or 'botsort'.
    """
    if hasattr(predictor, 'trackers') and persist:
        return
    tracker = check_yaml(predictor.args.tracker)
    cfg = IterableSimpleNamespace(**yaml_load(tracker))
    assert cfg.tracker_type in ['bytetrack', 'botsort'], \
        f"Only support 'bytetrack' and 'botsort' for now, but got '{cfg.tracker_type}'"
    trackers = []
    # for batch of frames of the same video, only use one tracker
    if predictor.source_type.from_img and predictor.dataset.bs >= 1 and not multiple_videos:
        trackers.append(TRACKER_MAP[cfg.tracker_type](args=cfg, frame_rate=30))
    else:
        for _ in range(predictor.dataset.bs):
            tracker = TRACKER_MAP[cfg.tracker_type](args=cfg, frame_rate=30)
            trackers.append(tracker)
    predictor.trackers = trackers


def on_predict_postprocess_end(predictor, multiple_videos=False):
    """Postprocess detected boxes and update with object tracking."""
    """
        Args:
        predictor (object): The predictor object to initialize trackers for.
        multiple_videos (bool, optional): Whether input frames of the same video or different. Defaults to False.
    """
    bs = predictor.dataset.bs
    im0s = predictor.batch[2]
    im0s = im0s if isinstance(im0s, list) else [im0s]
    batch_of_frames = predictor.source_type.from_img and bs >= 1 and not multiple_videos
    for i in range(bs):
        det = predictor.results[i].boxes.cpu().numpy()
        if len(det) == 0:
            continue
        # for batch of frames of the same video, only use one tracker
        if batch_of_frames:
            tracks = predictor.trackers[0].update(det, im0s[i])
        else:
            tracks = predictor.trackers[i].update(det, im0s[i])
        if len(tracks) == 0:
            continue
        idx = tracks[:, -1].tolist()
        predictor.results[i] = predictor.results[i][idx]
        predictor.results[i].update(boxes=torch.as_tensor(tracks[:, :-1]))


def register_tracker(model, persist, multiple_videos=False):
    """
    Register tracking callbacks to the model for object tracking during prediction.

    Args:
        model (object): The model object to register tracking callbacks for.
        persist (bool): Whether to persist the trackers if they already exist.
        multiple_videos (bool, optional): Whether input frames of the same video or different. Defaults to False.

    """
    model.add_callback('on_predict_start', partial(on_predict_start, persist=persist, multiple_videos=multiple_videos))
    model.add_callback('on_predict_postprocess_end', partial(on_predict_postprocess_end,
                                                             multiple_videos=multiple_videos))
