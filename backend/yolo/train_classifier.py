from ultralytics import YOLOWorld
import torch
import os
import random


'''

This involves manually training the model, rather than using a pre-trained set.
	It still needs the labels on the data in order to function, which appears to
	be a very manual process.


'''




def getClasses():
	classes = [
	"other",

	"apple", "banana", "orange","lemon","lime",
	"grapefruit","strawberry","blueberry","raspberry",
	"blackberry","grape","watermelon","cantaloupe",
	"honeydew","pineapple","mango","papaya","kiwi",
	"peach","nectarine","plum","cherry","pear",
	"pomegranate","fig","coconut","avocado",
	"dragon fruit","passion fruit","guava","lychee",
	"jackfruit","durian","persimmon","starfruit",

	"carrot","broccoli","cauliflower","spinach","lettuce",
	"kale","cabbage","brussels sprouts","asparagus",
	"zucchini","cucumber","eggplant","bell pepper","jalepeno",
	"chili pepper","onion","garlic","potato","sweet potato",
	"tomato","corn","peas","green beans","mushroom","raddish",
	"beet","radish","turnip","parsnip","leek","bok choy","ginger",
	"celery","artichoke","arugula","okra","pumpkin","squash",


	"chicken",
	"fried chicken",
	"beef","ground beef",
	"pork chop", "bacon", "ham", "sausage",
	"lamb chop", "turkey", "duck",
	"salmon","tuna","shrimp","crab","lobster",
	"egg","fried egg","boiled egg","scrambled egg",
	"tofu","tempeh","lentils","chickpeas","black beans",

	"bread","bagel","croissant",
	"rice","white rice","brown rice","fried rice",
	"pasta","spaghetti","macaroni","noodles","ramen",
	"quinoa","oats","oatmeal","cereal","granola",
	"tortilla","pizza",


	"milk","cheese",
	"butter","yogurt",
	"ice cream",
	"almond milk","soy milk","oat milk",

	"salad","sandwich","burger","cheeseburger",
	"hot dog","taco","burrito","quesadilla",
	"sushi","soup","stew","curry",
	"pancakes","waffles","french toast",
	"cake","chocolate cake","cheesecake",
	"donut","cookies","brownie","pie","pizza","lasagna"]

	return classes


def getModel(model="yolov8s-worldv2.pt"):
	
	model = YOLOWorld("backend/yolo/" + model)
	model.set_classes(getClasses())

	return model


def trainModel(model):
	
	epoch_count = 10
	device = 1 if torch.cuda.is_available() else 'cpu'

	# Missing labels -- errors
	results = model.train(data="data.yaml", optimizer="auto", epochs=epoch_count, imgsz=100, device=device)
	return results




if __name__ == "__main__":

	model = getModel()
	results = trainModel(model)