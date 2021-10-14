import numpy as np
import pandas as pd
import os
import glob 
import json
from PIL import Image, ImageDraw
from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval

def load_latest_predictions_file(image_filename):
    all_prediction_file_paths = glob.glob(f"predictions/predictions_{image_filename}_*.txt")
    latest_prediction_file_path = max(all_prediction_file_paths)
    df_predictions = pd.read_csv(latest_prediction_file_path)
    return df_predictions

def draw_box(image_path, df_predictions, df_ground_truth):
    df_ground_truth["right"] = df_ground_truth["left"] + df_ground_truth["width"]
    df_ground_truth["bottom"] = df_ground_truth["top"] + df_ground_truth["height"]
    
    basename = os.path.basename(image_path)
    img = Image.open(image_path)
    draw = ImageDraw.Draw(img)
    
    pred_coords = df_predictions[["object", "left", "top", "right", "bottom"]].to_numpy()
    for box in pred_coords: #df_predictions.iterrows():
        draw.rectangle(box[1:], width=5, outline="red")
        draw.text(box[1:3], box[0], fill="red")
        
    gt_coords = df_ground_truth[["label_category_attr:type","left", "top", "right", "bottom"]].to_numpy()
    for box in gt_coords:
        draw.rectangle(box[1:], width=5, outline="white")
        draw.text(box[1:3], box[0], fill="white")
    img.save(f"pred_images_gt_overlay/gt_predictions_{basename}")
    
def construct_pycoco_prediction_dict(image_i, df):
    df["image_id"] = image_i
    df["category_id"] = 0
    

    df["bbox"] = df.apply(
        lambda row: [row["left"], row["top"], row["right"]-row["left"], row["bottom"]-row["top"]],
        axis=1
    )
    df["score"] = df["confidence"]

    return df[["image_id", "category_id", "bbox", "score"]].to_dict("records")

def construct_pycoco_gt_dict(image_i, filename, df):
    images_sub_dict = {
        "filename": filename,
        "id": image_i,
        "width": 1920,
        "height": 1080
    } 
    
    
    df["image_id"] = image_i
    df["id"] = np.arange(len(df))
    df["category_id"] = 0
    df["bbox"] = df.apply(lambda row: [row["left"], row["top"], row["width"], row["height"]], axis=1)
    df["iscrowd"] = 0
    df["area"] = df.apply(lambda row: row["width"] * row["height"], axis=1)
    annotations_sub_dict_list = df[["image_id", "id", "category_id", "bbox", "iscrowd", "area"]].to_dict("records")
    
    return images_sub_dict, annotations_sub_dict_list

def main():
    coco_groundtruth = {
        "images": [], 
        "annotations": [], 
        "categories": [
            {
                "name": "Vehicle",
                "id": 0
            }
        ]
    }
    
    coco_predictions = []
    
    image_paths = glob.glob("images/*png")
    for image_i, image_path in enumerate(image_paths): 
        basename = os.path.basename(image_path)
        df_gt = pd.read_csv(f"ground_truth/{basename}.csv").dropna()
        df_predictions = load_latest_predictions_file(basename)
        
        draw_box(image_path, df_predictions, df_gt)
        
        coco_predictions.extend(construct_pycoco_prediction_dict(image_i, df_predictions))
        image_sub_dict, annotations_sub_dict_list = construct_pycoco_gt_dict(image_i, basename, df_gt)
        coco_groundtruth["images"].append(image_sub_dict)
        coco_groundtruth["annotations"].extend(annotations_sub_dict_list)

    
    with open("ground_truth.json", "w") as f:
        json.dump(coco_groundtruth, f)
    
    with open("predictions.json", "w") as f:
        json.dump(coco_predictions, f)
    
    
    cocoGt = COCO("ground_truth.json")
    cocoDt = cocoGt.loadRes("predictions.json")
    cocoEval = COCOeval(cocoGt, cocoDt, "bbox")
    cocoEval.evaluate()
    cocoEval.accumulate()
    cocoEval.summarize()
        
if __name__ == "__main__":
    main()