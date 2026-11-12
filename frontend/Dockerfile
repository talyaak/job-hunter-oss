FROM node:22-slim
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ENV VITE_HOST=0.0.0.0
EXPOSE 5173
CMD ["npm", "run", "dev"]
