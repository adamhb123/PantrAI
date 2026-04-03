import base64
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

def image_to_b64(image: str | np.ndarray):
    if type(image) == str:
        with open(image, "rb") as f:
            _b64 = base64.b64encode(f.read()).decode("utf-8")
    elif type(image) == np.ndarray:
        _, buffer = cv2.imencode('.jpg', image)
        _b64 = base64.b64encode(buffer).decode('utf-8')
    else:
        raise TypeError("Invalid type for argument : 'image'")
    return _b64