FROM node:18-bullseye-slim

WORKDIR /app
COPY package.json /app/package.json
RUN npm i
COPY . /app

# Accept the API key as a build-time argument
ARG NEXT_PUBLIC_API_KEY
# Set the API key as an environment variable for the 'npm run build' command
ENV NEXT_PUBLIC_API_KEY=${NEXT_PUBLIC_API_KEY}

ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production

RUN npm run build

EXPOSE 3000
CMD ["npm", "start"]