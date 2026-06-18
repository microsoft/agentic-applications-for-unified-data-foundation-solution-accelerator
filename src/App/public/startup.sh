#!/bin/sh

echo "Running env.sh..."
/docker-entrypoint.d/env.sh

echo "Injecting environment variables into runtime-config.js..."

if [ -f /usr/share/nginx/html/runtime-config.js ]; then
  envsubst < /usr/share/nginx/html/runtime-config.js > /usr/share/nginx/html/runtime-config.tmp.js
  mv /usr/share/nginx/html/runtime-config.tmp.js /usr/share/nginx/html/runtime-config.js
  echo "runtime-config.js updated successfully"
else
  echo "runtime-config.js not found!"
fi

echo "Starting nginx..."
nginx -g "daemon off;"