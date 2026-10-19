import cv2
from PIL import Image
from pyzbar.pyzbar import decode

img_path = r"C:\Users\Administrator\.gemini\antigravity\brain\aba39f35-e849-49b7-8803-1f8c65a65dd7\.user_uploaded\media_1792403805107_be7ed972.png"

try:
    img = Image.open(img_path)
    res = decode(img)
    if res:
        for r in res:
            print("DECODED_URL:", r.data.decode("utf-8"))
    else:
        cv_img = cv2.imread(img_path)
        detector = cv2.QRCodeDetector()
        data, _, _ = detector.detectAndDecode(cv_img)
        print("DECODED_URL:", data)
except Exception as e:
    print("Error:", e)
