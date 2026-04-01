import cv2
import numpy as np

img = cv2.imread('test_assets/receipt.jpg')
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# Threshold on the bright white receipt against the dark background
_, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)

# Close small gaps from wrinkles/shadows
kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

# Find contours and pick the largest one
contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
contours = sorted(contours, key=cv2.contourArea, reverse=True)

if contours:
    # Use convex hull to smooth out wrinkle noise, then approximate to 4 corners
    hull = cv2.convexHull(contours[0])
    peri = cv2.arcLength(hull, True)
    approx = cv2.approxPolyDP(hull, 0.02 * peri, True)
    print(f"Approx corners: {len(approx)}")
    print(approx)

    if len(approx) == 4:
        cv2.drawContours(img, [approx], -1, (0, 255, 0), 3)
    else:
        # Fallback: minAreaRect if approx didn't give 4 points
        rect = cv2.minAreaRect(hull)
        box = cv2.boxPoints(rect).astype(int)
        print("Fallback minAreaRect corners:", box)
        cv2.drawContours(img, [box], -1, (0, 255, 0), 3)
else:
    print("No rectangle found")

cv2.namedWindow("Resized Window", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Resized Window", 800, 600)
cv2.imshow("Resized Window", img)
cv2.waitKey(0)
cv2.destroyAllWindows()
