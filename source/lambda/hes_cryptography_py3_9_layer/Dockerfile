FROM public.ecr.aws/sam/build-python3.9:latest

COPY . .

RUN mkdir -p python/ && \
    pip install -t python/ -r requirements.txt && \
    find . -name "*.egg-info" -prune -exec rm -rf {} \; | true && \
    find . -name "*.pth" -prune -exec rm -rf {} \; | true && \
    find . -name "__pycache__" -prune -exec rm -rf {} \; | true && \
    rm Dockerfile && \
    rm requirements.txt && \
    zip -X -r lambda.zip ./

CMD mkdir -p /output/ && mv lambda.zip /output/