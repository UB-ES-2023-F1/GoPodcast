# 1. Base image
FROM python:3.11

# 2. Copy files
COPY . /src

# 3. Add commit hash
ARG GIT_HASH
ENV GIT_HASH=${GIT_HASH:-dev}

# 4. Install dependencies
RUN pip install -r src/requirements.txt --no-cache-dir

# 5. Run the app?
WORKDIR /src
CMD ["python3 app.py"]
