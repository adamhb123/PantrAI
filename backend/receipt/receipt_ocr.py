import math
from typing import List, Union
from PIL import Image
import numpy as np
import cv2

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

def _align_frames(frames: List[Image.Image]) -> List[Image.Image]:
    """
    Match features between frames, warp into same coordinate
    space using OpenCV:
        * ORB/SIFT feature matching
        * Homography alignment
    
    :param frames: Frames to be aligned
    :return: Aligned frames
    :type frames: List[Image.Image]
    """
    pass

def _multi_frame_averaging(frames: List[Image.Image]) -> Image.Image:
    """
    Enhance final OCR image by aligning the frames and taking
    the pixel-wise average with OpenCV.
    
    :param frames: Frames to be averaged into one
    :type frames: List[Image.Image]
    :return: Resulting Image.Image from frame averaging
    :rtype: Image.Image
    """
    
    pass

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
def _easyocr(frame: List[Image.Image]) -> List[str]:
    """
    Perform OCR on frame.
    
        orig_h, orig_w = frame.shape
    :param frame: Frame to be OCRed
    :type frame: List[Image.Image]
    :return: Tuple[List of text strings from OCR processing, confidence]
    :rtype: List[str]
    """
    pass

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
    cv2.imshow('flattened best frame (roi)', _frames_flat[0])
    cv2.waitKey()

test()