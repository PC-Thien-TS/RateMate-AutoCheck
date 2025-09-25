FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install Node.js and npm (required for Appium)
RUN apt-get update && apt-get install -y curl unzip \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs

# Install Appium globally
RUN npm install -g appium

# Install Java for Android SDK
RUN apt-get update && apt-get install -y openjdk-21-jdk && rm -rf /var/lib/apt/lists/*
ENV JAVA_HOME /usr/lib/jvm/java-21-openjdk-amd64

# Install Android SDK (command-line tools)
# This is a simplified setup. A full Android SDK setup can be very large.
# We'll install a minimal set for Appium to function.
ENV ANDROID_HOME=/opt/android-sdk
ENV PATH=$PATH:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools
RUN mkdir -p $ANDROID_HOME/cmdline-tools \
    && curl -o /tmp/sdk-tools.zip https://dl.google.com/android/repository/commandlinetools-linux-9477386_latest.zip \
    && unzip /tmp/sdk-tools.zip -d $ANDROID_HOME/cmdline-tools/latest \
    && mv $ANDROID_HOME/cmdline-tools/latest/cmdline-tools/* $ANDROID_HOME/cmdline-tools/latest/ \
    && rm -rf $ANDROID_HOME/cmdline-tools/latest/cmdline-tools \
    && rm /tmp/sdk-tools.zip \
    && yes | sdkmanager --licenses \
    && sdkmanager "platform-tools" "platforms;android-33" "build-tools;33.0.0"

COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt \
    && python -m playwright install --with-deps chromium

COPY . /app

CMD ["rq", "worker", "-u", "redis://redis:6379/0", "taas"]
