FROM node:20

RUN curl -fsSL https://bun.sh/install | bash

ENV BUN_INSTALL="/root/.bun"
ENV PATH="$BUN_INSTALL/bin:$PATH"

WORKDIR /app

COPY package*.json ./
RUN bun install --legacy-peer-deps

COPY . .

EXPOSE 3010
CMD ["bun", "dev"]
