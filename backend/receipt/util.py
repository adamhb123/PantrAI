import glob
import cv2
import numpy as np

from typing import List

def load_images(path: str, file_type: str) -> List[np.ndarray]:
    path = f"{path}/*.{file_type}"
    images = []
    for file in glob.glob(path):
        img = cv2.imread(file)
        if img is not None:
            images.append(img)
    return images