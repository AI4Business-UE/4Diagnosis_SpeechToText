import { serve, file } from "bun";
import index from "./index.html";

import path from "node:path";

const server = serve({
  port: 3010,

  routes: {
    // Serve index.html for all unmatched routes.
    "/public/audio_processors/*": {
      async GET(req) {
        try {
          const url = new URL(req.url);
          const fileName = url.pathname.split('/').pop() || "";
          const pathToFile = path.join(process.cwd(), "public", "audio_processors", fileName);
          console.log("📂 Looking for file at:", pathToFile);
          
          const requestedFile = file(pathToFile);
          if (!requestedFile.exists()) {
            return new Response("Not Found", { status: 404 });
          }

          return new Response(requestedFile);
        } catch (e) {
          return new Response("Internal Error", { status: 500 });
        }
      }
    },
    "/*": index,
  },

  development: process.env.NODE_ENV !== "production" && {
    // Enable browser hot reloading in development
    hmr: true,

    // Echo console logs from the browser to the server
    console: true,
  },
});

console.log(`🚀 Server running at ${server.url}`);
