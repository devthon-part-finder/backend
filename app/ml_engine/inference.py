import torch
from ultralytics import YOLO
import torchvision.models as models
import torchvision.transforms as transforms
from PIL import Image
import os

# Get absolute path to the model relative to this file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "best.pt")

# --- Load Models (Global Singleton) ---
try:
    print(f"Loading YOLO model from: {MODEL_PATH}")
    yolo_model = YOLO(MODEL_PATH)
except Exception as e:
    print(f"Error loading YOLO: {e}")
    yolo_model = None

# Load ResNet
resnet = models.resnet50(weights='DEFAULT')
feature_extractor = torch.nn.Sequential(*list(resnet.children())[:-1])
feature_extractor.eval()

def detect_objects(image_path):
    if not yolo_model:
        raise RuntimeError("YOLO model not loaded")
    results = yolo_model(image_path)
    # Returns the first result's boxes
    return results[0].boxes

def get_feature_vector(image_path):
    img = Image.open(image_path).convert("RGB")
    preprocess = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    input_tensor = preprocess(img).unsqueeze(0)
    with torch.no_grad():
        vector = feature_extractor(input_tensor)
    return vector.flatten().tolist()