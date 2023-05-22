FROM public.ecr.aws/sam/build-python3.9:latest

COPY . .

RUN pip install -t . -r requirements.txt && \
    pip uninstall -y boto3 && \
    pip uninstall -y botocore && \
    find . -name "*.egg-info" -prune -exec rm -rf {} \; | true && \
    find . -name "*.pth" -prune -exec rm -rf {} \; | true && \
    find . -name "__pycache__" -prune -exec rm -rf {} \; | true && \
    find . -name "test" | xargs rm -rf {} \; | true && \
    find . -name "tests" | xargs rm -rf {} \; | true && \
    find . -name "__pycache__" -type d | xargs rm -rf {} \; | true && \
    find . -name '*.pyc' -delete && \
    rm Dockerfile && \
    rm requirements.txt && \
    zip -X -r lambda.zip ./

CMD mkdir -p /output/ && mv lambda.zip /output/