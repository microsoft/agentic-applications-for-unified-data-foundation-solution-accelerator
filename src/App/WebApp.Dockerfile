FROM node:20-alpine AS build 
WORKDIR /home/node/app  

COPY ./package*.json ./  
  
RUN npm ci --omit=dev 
 
COPY . .  
 
RUN npm run build  
  
FROM nginx:alpine  

COPY --from=build /home/node/app/build /usr/share/nginx/html  

COPY public/startup.sh /usr/share/nginx/html/startup.sh
RUN chmod +x /usr/share/nginx/html/startup.sh

# Expose the application port
EXPOSE 3000

# Run startup script instead of nginx directly
CMD ["/bin/sh", "/usr/share/nginx/html/startup.sh"]