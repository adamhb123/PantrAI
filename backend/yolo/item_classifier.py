from ultralytics import YOLOWorld
import os
import random



def getModel(model="yolov8s-world.pt"):
	
	model = YOLOWorld("backend/yolo/" + model)

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

	model.set_classes(classes)

	# YOLO-E
	#embeddings = model.get_text_pe(classes)
	#model.set_classes(classes, embeddings)

	return model


def classifyItem(path="img/apple.png", model=None, show=False):
	
	results = model.predict(path)
	if show:
		results[0].show()
	predicted = {}

	for result in results:

		probabilities = result.boxes.conf
		labels = result.boxes.cls

		for i in range(len(probabilities)):
			name = model.names[labels[i].item()]
			predicted[name] = probabilities[i].item()

	return (path, predicted)


def classifyRandom(model=None, show=False):
	dir = random.choice(os.listdir("img"))
	img = random.choice(os.listdir(f"img/{dir}"))

	path = f"img/{dir}/{img}"
	return classifyItem(path, model=model, show=show)




if __name__ == "__main__":

	n = 30
	correct = 0
	total = 0

	list_models = ['yolov8l-world.pt', 'yolov8s-worldv2.pt', 'yoloe-26l-seg.pt']
	model = getModel(list_models[0])
	for i in range(n):
		response = classifyRandom(model, show=False)
		print(response)

		if len(response[1]) > 0: # there is a predicted result
			mx = max(response[1].items(), key=lambda x: x[1])

			if mx[0] in response[0]: # if 'apple' in 'apple/Image_1.png' 
				correct += 1
		total += 1
	
	print(f"Accuracy: {correct / total * 100}%")

