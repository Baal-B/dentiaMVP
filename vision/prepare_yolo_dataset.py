import json
import os
import random

def convert_dentex_to_yolo(
    json_path="training_data/training_data/quadrant-enumeration-disease/train_quadrant_enumeration_disease.json",
    images_dir="training_data/training_data/quadrant-enumeration-disease/xrays",
    output_dir="dentex_yolo",
    val_ratio=0.2,
    seed=42
):
    random.seed(seed)
    
    with open(json_path, "r") as f:
        data = json.load(f)
        
    images = data["images"]
    annotations = data["annotations"]
    
    # Map image id to list of annotations
    img_to_anns = {}
    for ann in annotations:
        img_id = ann["image_id"]
        img_to_anns.setdefault(img_id, []).append(ann)
        
    # Map image id to image info
    id_to_img = {img["id"]: img for img in images}
    
    # Shuffle and split
    all_img_ids = list(id_to_img.keys())
    random.shuffle(all_img_ids)
    
    val_count = int(len(all_img_ids) * val_ratio)
    val_ids = set(all_img_ids[:val_count])
    train_ids = set(all_img_ids[val_count:])
    
    for split in ["train", "val"]:
        os.makedirs(os.path.join(output_dir, "images", split), exist_ok=True)
        os.makedirs(os.path.join(output_dir, "labels", split), exist_ok=True)
        
    for img_id, img_info in id_to_img.items():
        split = "val" if img_id in val_ids else "train"
        file_name = img_info["file_name"]
        src_img_path = os.path.join(images_dir, file_name)
        dst_img_path = os.path.join(output_dir, "images", split, file_name)
        
        # Link or copy image
        if not os.path.exists(dst_img_path):
            try:
                os.link(src_img_path, dst_img_path)
            except Exception:
                import shutil
                shutil.copy2(src_img_path, dst_img_path)
                
        # Write labels
        base_name = os.path.splitext(file_name)[0]
        label_file = os.path.join(output_dir, "labels", split, f"{base_name}.txt")
        
        img_w = float(img_info["width"])
        img_h = float(img_info["height"])
        
        anns = img_to_anns.get(img_id, [])
        lines = []
        for ann in anns:
            cat_id = ann["category_id_3"]  # 0: Impacted, 1: Caries, 2: Periapical Lesion, 3: Deep Caries
            x, y, w, h = ann["bbox"]
            
            x_center = (x + w / 2.0) / img_w
            y_center = (y + h / 2.0) / img_h
            norm_w = w / img_w
            norm_h = h / img_h
            
            # Clip between 0 and 1
            x_center = max(0.0, min(1.0, x_center))
            y_center = max(0.0, min(1.0, y_center))
            norm_w = max(0.0, min(1.0, norm_w))
            norm_h = max(0.0, min(1.0, norm_h))
            
            lines.append(f"{cat_id} {x_center:.6f} {y_center:.6f} {norm_w:.6f} {norm_h:.6f}")
            
        with open(label_file, "w") as lf:
            lf.write("\n".join(lines))
            
    # Create data.yaml
    yaml_content = f"""# Dentex YOLO Dataset configuration for DentiAI
path: {os.path.abspath(output_dir).replace('\\', '/')}
train: images/train
val: images/val

names:
  0: Impacted
  1: Caries
  2: Periapical Lesion
  3: Deep Caries
"""
    yaml_path = os.path.join(output_dir, "data.yaml")
    with open(yaml_path, "w") as yf:
        yf.write(yaml_content)
        
    print(f"Dataset successfully created in {output_dir}")
    print(f"Train images: {len(train_ids)}, Val images: {len(val_ids)}")
    print(f"YAML config written to: {yaml_path}")

if __name__ == "__main__":
    convert_dentex_to_yolo()
