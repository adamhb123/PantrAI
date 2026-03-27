from utility import load_image
from ultralytics import YOLO

img = input("Which image would you like to load? ")
path = f"img/{img}"



'''

model = YOLO('yolov8s-world.pt')
model.set_classes(["apple", "other"])

results = model.predict(path)
results[0].show()
'''

from ultralytics import YOLOWorld

model = YOLOWorld("yolov8s-worldv2.pt") # small model

classes = ["bread", "butter", "knife", "cutting board"] 
model.set_classes(classes)

results = model.predict(path)
results[0].show() 	