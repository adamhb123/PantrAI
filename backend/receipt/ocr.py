import math
import os
from typing import Dict, List, Union
from PIL import Image
import numpy as np
import cv2
import easyocr # type: ignore

_reader = easyocr.Reader(['en'], gpu=False)   # type: ignore # Set gpu=True if you have CUDA

class HashableNdArray:
    def __init__(self, arr: np.ndarray):
        self.arr = arr
    def __hash__(self):
        return hash(self.arr.tobytes())
    def __eq__(self, other):
        return np.array_equal(self.arr, other.arr)


def frames_to_grayscale(frames: List[Union[np.ndarray, Image.Image]]) -> List[np.ndarray]:
    grays = []
    for frame in frames:
        grays.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)) # type: ignore
    return grays

def frames_select(frames: List[np.ndarray], pct_output_frames: float = 0.5) -> List[np.ndarray]:
    """
    Filter images for quality using OpenCV:
        * Convert images to grayscale
        * Blur detection
        * Brightness/contrast checks
    
    :param frames: Grayscaled frames to filter
    :type frames: List[np.ndarray]]
    :return: Frames filtered for quality
    :rtype: List[Image.Image]
    """
    _n_output_frames = math.ceil(pct_output_frames*len(frames))
    print(f"frames_select(): selecting {_n_output_frames} frames")
    frames_metadata = {}
    for frame in frames:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blur_variance = cv2.Laplacian(gray, cv2.CV_64F).var() # higher = less blurry
        contrast_score = gray.std() # higher = more contrast
        brightness_score = cv2.mean(gray)[0] # higher = brighter
        frames_metadata[HashableNdArray(frame)] = [blur_variance,contrast_score,brightness_score]

    # Rate frame suitability
    _blur_weight, _contrast_weight, _brightness_weight = 1,1,1
    # normalize
    _blurs = [m[0] for _,m in frames_metadata.items()]
    _contrasts = [m[1] for _,m in frames_metadata.items()]
    _brightnesses = [m[2] for _,m in frames_metadata.items()]
    _max_blur, _max_contrast, _max_brightness = (max(_blurs),
                                                 max(_contrasts),
                                                 max(_brightnesses))
    print(frames_metadata.items())
    normalized_fm = {frame: [metadata[0]/_max_blur,
                               metadata[1] / _max_contrast,
                               metadata[2] / _max_brightness
                               ] for frame, metadata in frames_metadata.items()}
    # Calculate overall quality scores
    frames_scored = [(frame, _blur_weight*m[0]+\
                      _contrast_weight*m[1]+\
                        _brightness_weight*m[2]) for frame, m in normalized_fm.items()]
    # Sort by score, descending
    frames_scored.sort(key=lambda frame_scored: frame_scored[1],reverse=True)
    print(f"frames and scores: {[(i,fs[1]) for i,fs in enumerate(frames_scored)]}")
    selected_frames = [f[0].arr for f in frames_scored[:_n_output_frames]]
    return selected_frames

def frames_transform(frames: Union[List[np.ndarray], List[np.ndarray]], debug: bool = False) -> List[np.ndarray]:
    """
    Flatten frames by detecting the largest rectangular ROI and applying
    perspective transform to make it perfectly rectangular.
    
    Key improvements:
    - Correctly detects portrait vs landscape orientation (no more squished vertical images)
    - Better contour filtering (minimum area check)
    - More robust side length calculation using averages
    - Returns list of numpy arrays (OpenCV BGR format) for easier further processing
    - Includes fallback to original frame if no good rectangle is found
    """
    transformed_frames: List[np.ndarray] = []
    
    for frame in frames:
        frame_cv = frame.copy()
        orig_h, orig_w = frame_cv.shape[:2]

        # Threshold on bright receipt against dark background
        gray = cv2.cvtColor(frame_cv, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)

        # Close gaps from wrinkles/shadows
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

        # Find contours, pick largest
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)

        roi_contour = None
        if contours:
            hull = cv2.convexHull(contours[0])
            peri = cv2.arcLength(hull, True)
            approx = cv2.approxPolyDP(hull, 0.02 * peri, True)
            if len(approx) == 4:
                roi_contour = approx
            else:
                # Fallback: minAreaRect if approxPolyDP didn't yield 4 points
                rect = cv2.minAreaRect(hull)
                box = cv2.boxPoints(rect).astype(np.float32)
                roi_contour = box.reshape(4, 1, 2).astype(np.int32)
        
        if roi_contour is None:
            # No good rectangle found → keep original
            transformed_frames.append(frame_cv)
            continue
        
        # Reshape to (4, 2) float32
        pts = roi_contour.reshape(4, 2).astype(np.float32)

        # Order points: top-left, top-right, bottom-right, bottom-left
        # Sort by y first to split top/bottom pair, then by x within each pair.
        # This is robust to any rotation of the receipt.
        pts_sorted_y = pts[np.argsort(pts[:, 1])]   # sort all 4 by y
        top_two = pts_sorted_y[:2]                   # two smallest y = top edge
        bot_two = pts_sorted_y[2:]                   # two largest  y = bottom edge
        tl, tr = top_two[np.argsort(top_two[:, 0])]   # left=smaller x, right=larger x
        bl, br = bot_two[np.argsort(bot_two[:, 0])]
        rect = np.array([tl, tr, br, bl], dtype="float32")
        
        # Calculate average side lengths (more robust than single sides)
        width_top = np.linalg.norm(rect[1] - rect[0])
        width_bottom = np.linalg.norm(rect[2] - rect[3])
        height_left = np.linalg.norm(rect[3] - rect[0])
        height_right = np.linalg.norm(rect[2] - rect[1])
        
        avg_width = (width_top + width_bottom) / 2.0
        avg_height = (height_left + height_right) / 2.0
        
        # Decide orientation: prefer portrait if it looks taller
        if avg_height > avg_width * 0.95:   # 0.95 gives tolerance for near-square cases
            final_width = int(avg_width + 0.5)
            final_height = int(avg_height + 0.5)
        else:
            final_width = int(avg_width + 0.5)
            final_height = int(avg_height + 0.5)
        
        # Minimum size check to avoid tiny/bad warps
        if final_width < 200 or final_height < 200:
            transformed_frames.append(frame_cv)
            continue
        
        # Destination rectangle (perfect flat rectangle)
        dst = np.array([
            [0, 0],
            [final_width - 1, 0],
            [final_width - 1, final_height - 1],
            [0, final_height - 1]
        ], dtype="float32")
        
        # Compute and apply perspective transform
        M = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(frame_cv, M, (final_width, final_height))

        if debug:
            os.makedirs("./debug_images", exist_ok=True)
            out_path = f"./debug_images/frame_{len(transformed_frames):03d}.jpg"
            cv2.imwrite(out_path, warped)
            print(f"[debug] saved {out_path}")
        transformed_frames.append(warped)
    
    return transformed_frames

'''
PSA: due to many papers claiming that this in fact does nothing to improve OCR results,
we will instead perform OCR on the best images from the feed and determine the final
prediction based on the results.

def _align_frames(frames: List[np.ndarray]) -> List[np.ndarray]:
    """
    Aligns a list of frames to the first frame using feature matching and homography.
    
    Uses ORB (fast + good enough for most cases) with RANSAC homography.
    Returns all frames warped into the coordinate space of the first frame.
    
    Good for stabilizing video frames, aligning scanned pages, or multi-shot document photos.
    """
    if not frames:
        return []
    if len(frames) == 1:
        return frames[:]

    # Convert first frame (reference) to grayscale
    ref = frames[0]
    ref_gray = cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY)

    # Initialize ORB detector + Brute Force matcher
    orb = cv2.ORB_create(nfeatures=2000, scaleFactor=1.2, nlevels=8)
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

    aligned_frames: List[Image.Image] = [frames[0]]  # first frame stays unchanged

    for i in range(1, len(frames)):
        curr_pil = frames[i].convert('RGB')
        curr_cv = cv2.cvtColor(np.array(curr_pil), cv2.COLOR_RGB2BGR)
        curr_gray = cv2.cvtColor(curr_cv, cv2.COLOR_BGR2GRAY)

        # Detect keypoints and descriptors
        kp1, des1 = orb.detectAndCompute(ref_gray, None)
        kp2, des2 = orb.detectAndCompute(curr_gray, None)

        if des1 is None or des2 is None or len(des1) < 10 or len(des2) < 10:
            # Not enough features → keep original frame
            aligned_frames.append(frames[i])
            continue

        # Match descriptors
        matches = bf.match(des1, des2)
        matches = sorted(matches, key=lambda x: x.distance)

        # Keep only good matches (top 20% or at least 50)
        good_matches = matches[:max(50, len(matches) // 5)]

        if len(good_matches) < 20:   # minimum reliable matches
            aligned_frames.append(frames[i])
            continue

        # Extract matched point coordinates
        src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)

        # Find homography (RANSAC is very important for robustness)
        H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, ransacReprojThreshold=5.0)

        if H is None:
            aligned_frames.append(frames[i])
            continue

        # Warp current frame to reference frame's coordinate space
        height, width = ref_gray.shape
        aligned_cv = cv2.warpPerspective(curr_cv, H, (width, height))

        aligned_frames.append(aligned_cv)

    return aligned_frames

def _multi_frame_averaging(frames: List[np.ndarray]) -> Image.Image:
    """
    Enhances the final image by:
      1. Aligning all frames to the first frame (using feature matching + homography)
      2. Taking the pixel-wise average (reduces noise, improves clarity for OCR)
    
    This is especially powerful for scanned documents, photos of text taken with a phone,
    or any situation with slight movement/shake between frames.

    [NEEDS VERIFICATION]
    """
    if not frames:
        raise ValueError("No frames provided for averaging")
    if len(frames) == 1:
        return frames[0].copy()

    # Step 1: Align all frames to the first one
    aligned_frames = _align_frames(frames)   # Reuse the function you already have

    # Step 2: Convert all aligned frames to numpy arrays (float32 for averaging)
    np_frames = frames

    # Step 3: Compute pixel-wise average
    avg_float = np.mean(np_frames, axis=0).astype(np.uint8)

    # Convert back to PIL Image
    avg_bgr = avg_float
    avg_rgb = cv2.cvtColor(avg_bgr, cv2.COLOR_BGR2RGB)
    result_pil = Image.fromarray(avg_rgb)
    return result_pil
'''

def classic_ocr_preprocessing(frames: List[np.ndarray]) -> List[np.ndarray]:
    """
    Perform classical OCR preprocessing operations on each frame
    using OpenCV:
        * Adaptive threshold
        * Sharpen
    
    :param frame: Frame to apply preprocessing to
    :type frame: Image.Image
    :return: Frame with preprocessing applied
    :rtype: List[Image.Image]
    """
    ppframes = []
    for frame in frames:
        # Sharpen before thresholding (on grayscale)
        _kc = 9 # kernel center
        _kernel = np.array([[-1,-1,-1],
                        [-1, _kc,-1],
                        [-1,-1,-1]])
        ppframe = cv2.filter2D(frame, -1, _kernel)
        # Adaptive thresholding — block size must be large enough to cover a character
        _block_size = 15 # size of neighborhood; must be odd number
        _bias: float = 10 # subtracted from the mean/weighted mean to fine-tune (=C)
        ppframe = cv2.adaptiveThreshold(ppframe,
                                        255,
                                        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                        cv2.THRESH_BINARY,
                                        _block_size,
                                        _bias)
        ppframes.append(ppframe)
    return ppframes

def make_label(n: int) -> str:
    """Convert 0-based index to spreadsheet-style label: 0→A, 25→Z, 26→AA, ..."""
    label = ""
    n += 1
    while n > 0:
        n, rem = divmod(n - 1, 26)
        label = chr(65 + rem) + label
    return label


class OCRResult:
    def __init__(self, text: str, confidence: float, bbox: list, label: str = ""):
        self.text = text
        self.confidence = confidence
        self.bbox = bbox  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
        self.label = label

    def __repr__(self):
        return f"[{self.label}] ({self.confidence:.2f}) {self.text}"

class FrameResult:
    def __init__(self, label: Union[str,int], ocr_results: List[OCRResult]):
        self.label = label
        self.ocr_results = ocr_results

    def __repr__(self):
        _n = 6
        s = ''
        s += f"{'-'*_n} Frame {self.label} - Avg confidence {self.get_rank()} {'-'*_n}\n"
        for ocr in self.ocr_results:
            s += f'  {ocr}\n'
            
        return s

    def get_rank(self):
        return sum([ocrres.confidence for ocrres in self.ocr_results])/len(self.ocr_results)



"""def rank_ocr_results(results: List[List[OCRResult]])-> Dict[str,float]:
    rankings = {}
    for frame_result in results:
        #net_confidence = frame_
        pass"""



def bbox_angle(bbox) -> float:
    """Return the angle of a bbox's top edge from horizontal, in degrees."""
    (x0, y0), (x1, y1) = bbox[0], bbox[1]
    return math.degrees(math.atan2(y1 - y0, x1 - x0))

def deskew_frame(frame: np.ndarray, angle_deg: float) -> np.ndarray:
    """Rotate frame by angle_deg, expanding canvas to avoid clipping."""
    h, w = frame.shape[:2]
    cx, cy = w / 2.0, h / 2.0
    R = cv2.getRotationMatrix2D((cx, cy), angle_deg, 1.0)
    cos_a, sin_a = abs(R[0, 0]), abs(R[0, 1])
    new_w = int(h * sin_a + w * cos_a)
    new_h = int(h * cos_a + w * sin_a)
    R[0, 2] += (new_w - w) / 2.0
    R[1, 2] += (new_h - h) / 2.0
    return cv2.warpAffine(frame, R, (new_w, new_h),
                          flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_REPLICATE)

def easyocr(frames: List[np.ndarray]) -> tuple:
    """
    Two-stage OCR:
      Stage 1: OCR to measure average bounding-box skew from horizontal.
      Stage 2: Rotate frame to correct that skew, then re-run OCR.
    """

    if not frames:
        return [], []

    results: List[FrameResult] = []
    deskewed_frames: List[np.ndarray] = []

    for i, frame in enumerate(frames):
        # --- Stage 1: detect skew ---
        stage1 = _reader.readtext(
            frame,
            detail=1,
            paragraph=False,
            text_threshold=0.6,
            low_text=0.3,
            width_ths=0.7,
            height_ths=0.7,
            min_size=10,
            rotation_info=None
        )
        angles = [bbox_angle(bbox) for bbox, _, conf in stage1 if conf > 0.5]
        skew = float(np.median(angles)) if angles else 0.0
        print(f"Frame {i}: stage1 detections={len(stage1)}, median skew={skew:.2f}°")

        # --- Stage 2: deskew then re-run OCR ---
        if abs(skew) > 0.5:
            frame = deskew_frame(frame, skew)

        detections = _reader.readtext(
            frame,
            detail=1,
            paragraph=False,
            text_threshold=0.6,
            low_text=0.3,
            width_ths=0.7,
            height_ths=0.7,
            min_size=10,
            rotation_info=None
        )

        if not detections and frame.shape[0] > 100:
            detections = _reader.readtext(
                frame, detail=1, paragraph=False,
                text_threshold=0.5
            )

        deskewed_frames.append(frame)
        results.append(FrameResult(i, [
            OCRResult(text, conf, bbox, label=make_label(j))
            for j, (bbox, text, conf) in enumerate(detections)
        ]))

    return deskewed_frames, results

def visualize_ocr(frames: List[np.ndarray], frame_results: List[FrameResult],
                   output_dir: str = "./ocr_viz") -> None:
    import os
    os.makedirs(output_dir, exist_ok=True)
    for i, (frame, frame_result) in enumerate(zip(frames, frame_results)):
        vis = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR) if frame.ndim == 2 else frame.copy()
        for r in frame_result.ocr_results:
            pts = np.array(r.bbox, dtype=np.int32)
            cv2.polylines(vis, [pts], isClosed=True, color=(0, 0, 0), thickness=2)
            label = f"{r.label} {r.confidence:.2f}"
            x, y = pts[0]
            (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(vis, (x, y - lh - 8), (x + lw, y), (0, 0, 0), -1)
            cv2.putText(vis, label, (x, y - 4), cv2.FONT_HERSHEY_SIMPLEX,
                        0.5, (255, 255, 255), 1, cv2.LINE_AA)
        out_path = os.path.join(output_dir, f"frame_{i:03d}.jpg")
        cv2.imwrite(out_path, vis)
        print(f"Saved {out_path}")
    
def load_images(path, file_type):
    import glob
    path = f"{path}/*.{file_type}"
    images = []
    for file in glob.glob(path):
        img = cv2.imread(file)
        if img is not None:
            images.append(img)
    return images

def test():
    frames = load_images("./test_assets", "jpg")
    print(f"Loaded n={len(frames)} frames")
    _frame_sel = frames_select(frames)
    print(f"frames_select() got {len(_frame_sel)} image(s)")
    #cv2.imshow('best frame', _frame_sel[0])
    #cv2.waitKey()
    _frames_flat = frames_transform(_frame_sel)
    #cv2.imshow('flattened frame (roi)', _frames_flat[0])
    #cv2.waitKey()
    deskewed, results = easyocr(_frames_flat)
    for frame_result in results:
        print(frame_result)
    visualize_ocr(deskewed, results)

if __name__=="__main__":
    test()