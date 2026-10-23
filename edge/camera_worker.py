"""Edge-only occupancy worker.

Frames remain on the camera host. Only anonymous table occupancy observations
are sent to the MidaPulse API.
"""

import argparse
import json
import time
from pathlib import Path

import cv2
import requests


def point_in_zone(point, table):
    x, y = point
    return abs(x - table["x"]) <= 12 and abs(y - table["y"]) <= 15


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="0", help="Camera index or video path")
    parser.add_argument("--api", default="http://127.0.0.1:8100")
    parser.add_argument("--floor", default="config/floor.json")
    args = parser.parse_args()

    tables = json.loads(Path(args.floor).read_text(encoding="utf-8"))["tables"]
    source = int(args.source) if args.source.isdigit() else args.source
    capture = cv2.VideoCapture(source)
    detector = cv2.HOGDescriptor()
    detector.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    previous = {}

    while capture.isOpened():
        ok, frame = capture.read()
        if not ok:
            break
        height, width = frame.shape[:2]
        boxes, weights = detector.detectMultiScale(frame, winStride=(8, 8), padding=(8, 8), scale=1.05)
        occupancy = {table["id"]: (False, 0.0) for table in tables}
        for (x, y, w, h), weight in zip(boxes, weights):
            anchor = ((x + w / 2) / width * 100, (y + h) / height * 100)
            for table in tables:
                if point_in_zone(anchor, table):
                    occupancy[table["id"]] = (True, max(float(weight), occupancy[table["id"]][1]))
        for table_id, (occupied, confidence) in occupancy.items():
            if previous.get(table_id) == occupied:
                continue
            requests.post(f"{args.api}/api/observations", json={"table_id": table_id, "occupied": occupied, "confidence": min(1.0, confidence), "source": "opencv-edge"}, timeout=3)
            previous[table_id] = occupied
        time.sleep(1)

    capture.release()


if __name__ == "__main__":
    main()
