#!/bin/sh

echo "Generating API proxy configuration..."

if [ -n "$BACKEND_API_HOST" ]; then

cat > /etc/nginx/conf.d/api-proxy.conf << PROXYEOF
location /api/ {
    resolver 168.63.129.16 valid=30s;

    set \$backend "https://$BACKEND_API_HOST";

    proxy_pass \$backend;

    proxy_set_header Host $BACKEND_API_HOST;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;

    proxy_ssl_server_name on;

    proxy_read_timeout 300s;
    proxy_connect_timeout 60s;
    proxy_buffering off;
}

location /history/ {
    resolver 168.63.129.16 valid=30s;

    set \$backend "https://$BACKEND_API_HOST";

    proxy_pass \$backend;

    proxy_set_header Host $BACKEND_API_HOST;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;

    proxy_ssl_server_name on;

    proxy_read_timeout 300s;
    proxy_connect_timeout 60s;
    proxy_buffering off;
}
PROXYEOF

echo "Reverse proxy enabled for $BACKEND_API_HOST"

else

echo "Reverse proxy disabled"
> /etc/nginx/conf.d/api-proxy.conf

fi