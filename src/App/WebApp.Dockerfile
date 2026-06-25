FROM node:24-alpine AS build
WORKDIR /home/node/app

COPY ./package*.json ./

RUN npm ci --omit=dev

COPY . .

RUN npm run build

FROM nginx:alpine

COPY --from=build /home/node/app/build /usr/share/nginx/html

COPY env.sh /docker-entrypoint.d/env.sh
RUN chmod +x /docker-entrypoint.d/env.sh && sed -i 's/\r$//' /docker-entrypoint.d/env.sh

COPY public/startup.sh /usr/share/nginx/html/startup.sh
RUN chmod +x /usr/share/nginx/html/startup.sh && sed -i 's/\r$//' /usr/share/nginx/html/startup.sh

COPY nginx.conf /etc/nginx/nginx.conf

RUN mkdir -p /etc/nginx/conf.d && touch /etc/nginx/conf.d/api-proxy.conf

EXPOSE 3000

CMD ["/bin/sh", "/usr/share/nginx/html/startup.sh"]