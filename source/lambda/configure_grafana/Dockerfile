FROM public.ecr.aws/sam/build-python3.9:latest

COPY . .

RUN pip install -t . -r requirements.txt && \
    rm Dockerfile && \
    rm requirements.txt && \
    zip -X -r lambda.zip ./

CMD mkdir -p /output/ && mv lambda.zip /output/