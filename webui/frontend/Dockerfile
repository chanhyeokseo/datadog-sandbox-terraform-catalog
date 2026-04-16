FROM node:18-alpine as build

WORKDIR /app

COPY package*.json ./

RUN npm install

COPY . .

RUN npm run build

FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html

COPY nginx.conf.template /etc/nginx/templates/default.conf.template

ENV WEBUI_PORT=7620
ENV TFRUNNER_PORT=7621

EXPOSE ${WEBUI_PORT}

CMD ["/bin/sh", "-c", "envsubst '${WEBUI_PORT} ${TFRUNNER_PORT}' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
