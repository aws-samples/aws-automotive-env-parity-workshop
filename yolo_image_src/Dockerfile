FROM autoware/model-zoo-tvm-cli:1.0.0
RUN apt update && apt install git-lfs
WORKDIR /app
RUN GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/autowarefoundation/modelzoo && \
    cd modelzoo && \
    git lfs install && \
    git lfs pull

WORKDIR /app/modelzoo/perception/camera_obstacle_detection/yolo_v2_tiny/tensorflow_fp32_coco
RUN  tvm_cli compile \
    --config ./definition.yaml \
    --output_path ./example_pipeline/build

COPY main.cpp /app/modelzoo/perception/camera_obstacle_detection/yolo_v2_tiny/tensorflow_fp32_coco/example_pipeline

RUN cd example_pipeline && cmake . && make -j

FROM autoware/model-zoo-tvm-cli:1.0.0
ENV LD_LIBRARY_PATH="/usr/local/lib/"
WORKDIR /app

# Copy the dataset images over and extract them
COPY images/* ./images/

# Copy built binary and other supporting files from previous stage
COPY --from=0 /app/modelzoo/perception/camera_obstacle_detection/yolo_v2_tiny/tensorflow_fp32_coco/example_pipeline/build/ ./
COPY --from=0 /app/modelzoo/perception/camera_obstacle_detection/yolo_v2_tiny/tensorflow_fp32_coco/example_pipeline/example_pipeline ./example_pipeline
COPY --from=0 /app/modelzoo/perception/camera_obstacle_detection/yolo_v2_tiny/tensorflow_fp32_coco/model_files/anchors.csv ./anchors.csv
COPY --from=0 /app/modelzoo/perception/camera_obstacle_detection/yolo_v2_tiny/tensorflow_fp32_coco/model_files/labels.txt ./labels.txt

# Create directory for prediction results to save to host system
VOLUME ["/app/predictions/"]

# copy python script for execuing the executable and uploading results to S3
COPY execute_pipeline.py ./execute_pipeline.py

CMD ["execute_pipeline.py"]
ENTRYPOINT ["python3"] 