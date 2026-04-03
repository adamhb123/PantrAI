from utility import load_image
from ultralytics import YOLOWorld
import os

# img = input("Which image would you like to load? ")
# path = f"img/{img}"




def classifyItem(path="img/apple.png", model="yolov8s-worldv2.pt"):

	model = YOLOWorld(model) # small model

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
	"tofu","tempeh","lentils","chickpeas","black beans","soy beans",

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

	model.set_classes(classes)
	results = model.predict(path)
	# results[0].show()
	predicted = {}

	for result in results:

		probabilities = result.boxes.conf
		labels = result.boxes.cls
		
		for i in range(len(probabilities)):
			name = model.names[labels[i].item()]
			predicted[name] = probabilities[i].item()
			print(f"{name}: {probabilities[i]}")

	return predicted

def classifyRandom():
	dir = os.listdir("img")
	
print(classifyItem())

