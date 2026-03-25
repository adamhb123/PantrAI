import math
from typing import List, Union
from PIL import Image
import numpy as np
import cv2
import easyocr

_reader = easyocr.Reader(['en'], gpu=False)   # Set gpu=True if you have CUDA

class HashableNdArray:
    def __init__(self, arr: np.ndarray):
        self.arr = arr
    def __hash__(self):
        return hash(self.arr.tobytes())
    def __eq__(self, other):
        return np.array_equal(self.arr, other.arr)
    def to_image(self) -> Image.Image:
        pass


def _frames_select(frames: List[np.ndarray], pct_output_frames: float = 0.5) -> List[np.ndarray]:
    """
    Filter images for quality using OpenCV:
        * Convert images to grayscale
        * Blur detection
        * Brightness/contrast checks
    
    :param frames: Frames to filter
    :type frames: List[Image.Image]
    :return: Frames filtered for quality
    :rtype: List[Image.Image]
    """
    _n_output_frames = math.ceil(pct_output_frames*len(frames))
    print(f"_frames_select(): selecting {_n_output_frames} frames")
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

def _frames_transform(frames: Union[List[Image.Image], List[np.ndarray]]) -> List[np.ndarray]:
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
        # Convert PIL Image to OpenCV BGR format
        if isinstance(frame, Image.Image):
            np_frame = np.array(frame.convert('RGB'))
            frame_cv = cv2.cvtColor(np_frame, cv2.COLOR_RGB2BGR)
        else:
            frame_cv = frame.copy()
        
        orig_h, orig_w = frame_cv.shape[:2]
        
        # Preprocessing
        gray = cv2.cvtColor(frame_cv, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edged = cv2.Canny(blurred, 30, 200)
        
        # Morphological operations to close gaps in edges
        kernel = np.ones((3, 3), np.uint8)
        edged = cv2.dilate(edged, kernel, iterations=2)
        edged = cv2.erode(edged, kernel, iterations=1)
        
        # Find contours
        contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Sort by area (largest first)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)
        
        roi_contour = None
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < 0.05 * orig_h * orig_w:   # Skip tiny contours (<5% of image)
                continue
                
            # Approximate contour to polygon
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
            
            # Accept if it's approximately a quadrilateral
            if len(approx) == 4:
                roi_contour = approx
                break
        
        if roi_contour is None:
            # No good rectangle found → keep original
            transformed_frames.append(frame_cv)
            continue
        
        # Reshape to (4, 2) float32
        pts = roi_contour.reshape(4, 2).astype(np.float32)
        
        # Order points: top-left, top-right, bottom-right, bottom-left
        rect = np.zeros((4, 2), dtype="float32")
        s = pts.sum(axis=1)
        diff = np.diff(pts, axis=1)
        rect[0] = pts[np.argmin(s)]      # top-left
        rect[2] = pts[np.argmax(s)]      # bottom-right
        rect[1] = pts[np.argmin(diff)]   # top-right
        rect[3] = pts[np.argmax(diff)]   # bottom-left
        
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
        
        transformed_frames.append(warped)
    
    return transformed_frames

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

def _classic_ocr_preprocessing(frame: Image.Image) -> Image.Image:
    """
    Perform classical OCR preprocessing operations on the frame
    using OpenCV:
        * Grayscale
        * Adaptive threshold
        * Sharpen
    
    :param frame: Frame to apply preprocessing to
    :type frame: Image.Image
    :return: Frame with preprocessing applied
    :rtype: Image.Image
    """
    # Grayscale
    ppframe = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    _block_size = 3 # size of neighborhood; must be odd number
    _bias = 1 # subtracted from the mean/weighted mean to fine-tune
    # Adaptive thresholding (contrast)
    ppframe = cv2.adaptiveThreshold(ppframe,
                                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                    cv2.THRESH_BINARY,
                                    _block_size,
                                    _bias)
    # Sharpen
    _kc = 9 # kernel center
    _kernel = np.array([[-1,-1,-1],
                       [-1, _kc,-1],
                       [-1,-1,-1]])
    ppframe = cv2.filter2D(ppframe, -1, _kernel)
    return ppframe

def _easyocr(frames: List[Image.Image]) -> List[List[str]]:
    """
    Perform OCR on each frame using EasyOCR.
    
    Returns:
        List[List[str]]: For each input frame, a list of recognized text strings
                         (one string per detected text box, in reading order).
    
    Optimized for document-style text (after your perspective transform + averaging).
    """
    if not frames:
        return []

    results: List[List[str]] = []

    for frame in frames:
        gray = _classic_ocr_preprocessing(frame)
        # Mild contrast stretch (helps with faded text)
        gray = cv2.equalizeHist(gray) if np.std(gray) < 60 else gray

        # Run EasyOCR
        # detail=0 returns only the text strings (no bbox/confidence)
        # paragraph=True merges text into natural reading order (recommended for documents)
        text_list = _reader.readtext(
            gray,                   # or img if you want color
            detail=0,               # 0 = text only (fast & simple)
            paragraph=True,         # merges lines into coherent blocks
            text_threshold=0.6,
            low_text=0.3,
            width_ths=0.7,          # helps merge words in same line
            height_ths=0.7,
            min_size=10,
            rotation_info=None      # set to [90, 180, 270] if orientation unknown
        )

        # Fallback: if paragraph mode gives poor results, try without
        if not text_list and len(gray) > 100:
            text_list = _reader.readtext(
                gray, detail=0, paragraph=False,
                text_threshold=0.5
            )

        results.append(text_list)

    return results

def _load_images(path, file_type):
    import glob
    path = f"{path}/*.{file_type}"
    images = []
    for file in glob.glob(path):
        img = cv2.imread(file)
        if img is not None:
            images.append(img)
    return images

def test():
    frames = _load_images("./test_assets", "jpg")
    print(f"Loaded n={len(frames)} frames")
    _frame_sel = _frames_select(frames)
    print(f"_frames_select() got {len(_frame_sel)} images")
    cv2.imshow('best frame', _frame_sel[0])
    cv2.waitKey()
    _frames_flat = _frames_transform(_frame_sel)
    print(_frames_flat)
    cv2.imshow('flattened frame (roi)', _frames_flat[0])
    _frames_aligned = _align_frames(_frames_flat)
    cv2.imshow('flattened aligned frame', _frames_aligned[0])
    _frames_averaged = _multi_frame_averaging(_frames_aligned)
    cv2.imshow('flattened aligned averaged frame', _frames_averaged[0])
    cv2.waitKey()

test()