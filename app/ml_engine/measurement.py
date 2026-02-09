import cv2

def calculate_real_size(image_path, coin_box, part_box):
    """
    coin_box & part_box: [x1, y1, x2, y2] tensors or lists
    """
    # Standard Reference: US Quarter = 24.26mm (Change this to your coin)
    REAL_COIN_DIAMETER_MM = 24.26
    
    # Calculate Pixel Widths
    # Box format is [x1, y1, x2, y2]
    coin_w_px = float(coin_box[2] - coin_box[0])
    part_w_px = float(part_box[2] - part_box[0])
    part_h_px = float(part_box[3] - part_box[1])
    
    # Avoid division by zero
    if coin_w_px == 0: return 0, 0

    # Calculate Scale
    mm_per_pixel = REAL_COIN_DIAMETER_MM / coin_w_px
    
    # Apply to Part
    width_mm = part_w_px * mm_per_pixel
    height_mm = part_h_px * mm_per_pixel
    
    return width_mm, height_mm