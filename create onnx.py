from ultralytics import YOLO

model = YOLO('yolov8n.pt')

print("Started Exporting")

model_file = model.export(format = 'onnx', imgsz = 640, simplify = True, opset = 12)

print(f'done, saved at: {model_file}')

# /usr/src/tensorrt/bin/trtexec --onnx=yolov8n.onnx --saveEngine=yolov8n.engine --fp16 --workspace=1024
# command to convert to tensorrt in jetson