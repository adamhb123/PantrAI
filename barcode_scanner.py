from typing import Union, List
from pyzbar.pyzbar import decode, Decoded
from utility import load_image



def scan(image, debug=False) -> Union[List[Decoded], None]:
    barcodes = decode(image)
    return barcodes

def test(path):
    img = load_image(path)
    print("Got barcode: ", scan(img))

test("./test_assets/barcode/spam.png")