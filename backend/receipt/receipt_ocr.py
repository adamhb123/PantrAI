import math
from typing import List
from PIL.Image import Image
import numpy as np
import cv2

class HashableNdArray:
    def __init__(self, arr: np.ndarray):
        self.arr = arr
    def __hash__(self):
        return hash(self.arr.tobytes())
    def __eq__(self, other):
        return np.array_equal(self.arr, other.arr)
    def to_image(self) -> Image:
        pass

def _frames_select(frames: List[Image], pct_output_frames: float = 0.5) -> List[Image]:
    """
    Filter images for quality using OpenCV:
        * Convert images to grayscale
        * Blur detection
        * Brightness/contrast checks
    
    :param frames: Frames to filter
    :type frames: List[Image]
    :return: Frames filtered for quality
    :rtype: List[Image]
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
    selected_frames = [f[0] for f in frames_scored[:_n_output_frames]]
    return selected_frames

def _frames_transform(frames: List[Image]) -> List[Image]:
    """
    Flatten frames by detecting largest rectangle (ROI),
    and perspective transform into a flat rectangle using OpenCV:
        * Contour detection
        * Find homography
    
    :param frames: Frames to be transformed
    :return: Flattened frames
    :type frames: List[Image]
    """
    pass

def _align_frames(frames: List[Image]) -> List[Image]:
    """
    Match features between frames, warp into same coordinate
    space using OpenCV:
        * ORB/SIFT feature matching
        * Homography alignment
    
    :param frames: Frames to be aligned
    :return: Aligned frames
    :type frames: List[Image]
    """
    pass

def _multi_frame_averaging(frames: List[Image]) -> Image:
    """
    Enhance final OCR image by aligning the frames and taking
    the pixel-wise average with OpenCV.
    
    :param frames: Frames to be averaged into one
    :type frames: List[Image]
    :return: Resulting Image from frame averaging
    :rtype: Image
    """
    
    pass

def _classic_ocr_preprocessing(frame: Image) -> Image:
    """
    Perform classical OCR preprocessing operations on the frame
    using OpenCV:
        * Grayscale
        * Adaptive threshold
        * Sharpen
    
    :param frame: Frame to apply preprocessing to
    :type frame: Image
    :return: Frame with preprocessing applied
    :rtype: Image
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
def _easyocr(frame: List[Image]) -> List[str]:
    """
    Perform OCR on frame.
    
    :param frame: Frame to be OCRed
    :type frame: List[Image]
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
    cv2.imshow('display', _frame_sel[0].arr)
    cv2.waitKey()
test()