# Use the official AWS Lambda Python base image
FROM public.ecr.aws/lambda/python:3.11

# Install required Linux development libraries for lxml
RUN yum update -y && yum install -y libxml2-devel libxslt-devel gcc

# Copy requirements.txt
COPY requirements.txt ${LAMBDA_TASK_ROOT}

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy your python script code
COPY app.py ${LAMBDA_TASK_ROOT}

# Ensure the runtime client can read and execute your script files
RUN chmod -R 755 ${LAMBDA_TASK_ROOT}

# Set the CMD to your handler function (filename.function_name)
CMD [ "app.lambda_handler" ]

# Image version tagging convention: version is the commit hash