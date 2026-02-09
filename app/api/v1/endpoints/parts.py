from fastapi import APIRouter, UploadFile, File, HTTPException
from app.ml_engine.inference import detect_objects, get_feature_vector, yolo_model
from app.ml_engine.measurement import calculate_real_size
import shutil
import os

router = APIRouter()

@router.post("/analyze")
async def analyze_part(file: UploadFile = File(...)):
    # 1. Setup temporary filename
    temp_filename = f"temp_{file.filename}"
    
    try:
        # 2. Save the Uploaded File
        with open(temp_filename, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # ---------------------------------------------------------
        # STEP 3: RUN AI INFERENCE
        # ---------------------------------------------------------
        # We use a lower confidence threshold (0.15) to ensure we don't miss 
        # a coin just because the lighting is bad.
        # iou=0.5 helps remove duplicate boxes overlapping each other.
        results = yolo_model(temp_filename, conf=0.15, iou=0.5)
        boxes = results[0].boxes

        print(f"DEBUG: YOLO detected {len(boxes)} objects.")

        # ---------------------------------------------------------
        # STEP 4: DEFINE COIN SIZES (The "Ground Truth")
        # ---------------------------------------------------------
        # These IDs must match your data.yaml file from Roboflow/Kaggle.
        # Assuming Alphabetical Order:
        # 0=Bearing, 1=Bolt, 2=Dime, 3=Gear, 4=Nickel, 5=Nut, 6=Penny, 7=Quarter
        COIN_MAP = {
            2: 17.91,  # Dime
            4: 21.21,  # Nickel
            6: 19.05,  # Penny
            7: 24.26   # Quarter
        }
        
        # ---------------------------------------------------------
        # STEP 5: SEPARATE COINS FROM PARTS
        # ---------------------------------------------------------
        detected_coins = []
        detected_parts = []

        for box in boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            
            # Check if this object is in our known "Coin List"
            if cls_id in COIN_MAP:
                detected_coins.append(box)
                print(f"DEBUG: Found Coin (Class {cls_id}) with conf {conf:.2f}")
            else:
                detected_parts.append(box)
                print(f"DEBUG: Found Part (Class {cls_id}) with conf {conf:.2f}")

        # ---------------------------------------------------------
        # STEP 6: SELECT THE BEST COIN (Logic Fix)
        # ---------------------------------------------------------
        final_coin_box = None
        real_coin_diameter = 0.0
        
        if len(detected_coins) > 0:
            # If multiple coins are found, pick the one with HIGHEST CONFIDENCE
            best_coin = max(detected_coins, key=lambda x: float(x.conf[0]))
            final_coin_box = best_coin.xyxy[0]
            
            # Get the real size for this specific coin type
            coin_id = int(best_coin.cls[0])
            real_coin_diameter = COIN_MAP[coin_id]
            print(f"DEBUG: Selected Best Coin: Class {coin_id} ({real_coin_diameter}mm)")
        else:
            # FATAL ERROR: We cannot measure without a reference
            return {
                "status": "error",
                "message": "No coin detected. Please verify lighting or place a standard US coin (Penny, Nickel, Dime, Quarter) next to the part."
            }

        # ---------------------------------------------------------
        # STEP 7: SELECT THE PART (Logic Fix)
        # ---------------------------------------------------------
        final_part_box = None
        detected_class_name = "Unknown Part"
        
        if len(detected_parts) > 0:
            # If multiple parts found, pick the LARGEST one by area
            # Area = (x2 - x1) * (y2 - y1)
            final_part_box = max(detected_parts, key=lambda b: (b.xyxy[0][2] - b.xyxy[0][0]) * (b.xyxy[0][3] - b.xyxy[0][1])).xyxy[0]
            
            # Get the detected Class ID for the vector search metadata
            part_id = int(max(detected_parts, key=lambda b: (b.xyxy[0][2] - b.xyxy[0][0]) * (b.xyxy[0][3] - b.xyxy[0][1])).cls[0])
            detected_class_name = results[0].names[part_id] # Gets "Bolt", "Nut", etc. from model
            print(f"DEBUG: Selected Main Part: {detected_class_name}")
        else:
             return {
                "status": "error",
                "message": "No mechanical part detected. Please ensure the part is clearly visible."
            }

        # ---------------------------------------------------------
        # STEP 8: CALCULATE & EXTRACT
        # ---------------------------------------------------------
        
        # 1. Calculate Real World Size (in mm)
        # We manually calculate scale here to handle dynamic coin sizes
        coin_width_px = float(final_coin_box[2] - final_coin_box[0])
        mm_per_pixel = real_coin_diameter / coin_width_px
        
        part_width_px = float(final_part_box[2] - final_part_box[0])
        part_height_px = float(final_part_box[3] - final_part_box[1])
        
        width_mm = part_width_px * mm_per_pixel
        height_mm = part_height_px * mm_per_pixel
        
        # 2. Extract Feature Vector (PyTorch ResNet)
        vector = get_feature_vector(temp_filename)
        
        return {
            "status": "success",
            "part_detected": True,
            "inferred_type": detected_class_name,
            "dimensions": {
                "width_mm": round(width_mm, 2),
                "height_mm": round(height_mm, 2)
            },
            "embedding_sample": vector[:5] 
        }

    except Exception as e:
        print(f"CRITICAL ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        # Cleanup temp file
        if os.path.exists(temp_filename):
            os.remove(temp_filename)