import numpy as np
from ultralytics import YOLO

def run_sweep():
    model = YOLO('runs/detect/dentiai_experiments/yolo11s_dentex_production/weights/best.pt')

    print("Confidence Sweep Analysis:")
    print(f"{'Conf':<6} | {'Class':<18} | {'Precision':<10} | {'Recall':<10}")
    print("-" * 55)

    for conf in [0.25, 0.40, 0.50, 0.60, 0.70, 0.80]:
        val_res = model.val(data='dentex_yolo/data.yaml', device=0, conf=conf, workers=0, verbose=False)
        p_per_class = val_res.box.p
        r_per_class = val_res.box.r
        names = val_res.names
        for i, name in names.items():
            p_val = p_per_class[i] if i < len(p_per_class) else 0.0
            r_val = r_per_class[i] if i < len(r_per_class) else 0.0
            print(f"{conf:<6.2f} | {name:<18} | {p_val*100:<9.1f}% | {r_val*100:<9.1f}%")
        print("-" * 55)

if __name__ == "__main__":
    run_sweep()
