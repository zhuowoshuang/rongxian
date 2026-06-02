FROM node:20-alpine

WORKDIR /app

ARG BACKEND_URL=http://localhost:8000
ENV BACKEND_URL=$BACKEND_URL

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
