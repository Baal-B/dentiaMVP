import numpy as np
from ultralytics import YOLO

def run_eval():
    model = YOLO("weights/denti_yolo11m_best.pt")
    print("\n--- YOLO11m Cloud Model Evaluation on Validation Set ---")
    print(f"{'Conf':<6} | {'Class':<18} | {'Precision':<10} | {'Recall':<10} | {'mAP50':<10}")
    print("-" * 65)

    for conf in [0.25, 0.40, 0.50, 0.65, 0.75, 0.85]:
        val_res = model.val(data="dentex_yolo/data.yaml", imgsz=640, device=0, conf=conf, workers=0, verbose=False)
        p_per_class = val_res.box.p
        r_per_class = val_res.box.r
        names = val_res.names
        for i, name in names.items():
            p_val = p_per_class[i] if i < len(p_per_class) else 0.0
            r_val = r_per_class[i] if i < len(r_per_class) else 0.0
            ap50 = val_res.box.ap50[i] if i < len(val_res.box.ap50) else 0.0
            print(f"{conf:<6.2f} | {name:<18} | {p_val*100:<9.1f}% | {r_val*100:<9.1f}% | {ap50*100:<9.1f}%")
        print("-" * 65)

if __name__ == "__main__":
    run_eval()
