FROM node:20-alpine AS base

WORKDIR /app

ENV NEXT_TELEMETRY_DISABLED=1

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

RUN chmod +x /app/entrypoint.sh

EXPOSE 3000

ENTRYPOINT ["/app/entrypoint.sh"]

FROM base AS development

ENV NODE_ENV=development

CMD ["dev"]

FROM base AS production

ENV NODE_ENV=production

RUN npm run build

CMD ["prod"]
