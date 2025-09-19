FROM node:18-bullseye-slim

WORKDIR /app
COPY package.json /app/package.json
RUN npm i --omit=dev
COPY . /app

ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production

RUN npm run build

EXPOSE 3000
CMD ["npm", "start"]

