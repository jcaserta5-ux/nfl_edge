FROM node:20-alpine AS builder

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .

# Bake the backend URL into the JS bundle at build time
ARG VITE_API_BASE_URL=https://nfl-edge.fly.dev/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build

# Production: serve via nginx
FROM nginx:1.27-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD [""nginx"", ""-g"", ""daemon off;""]