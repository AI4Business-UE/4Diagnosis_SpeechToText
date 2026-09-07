import { serve, file, Transpiler } from "bun";
import index from "./index.html";

import path from "node:path";

const server = serve({
  port: 3010,

  routes: {
    // Serve index.html for all unmatched routes.
    "/audio-worklets/BaseProcessor.js": {
      async GET() {
        const source = await file(path.join(process.cwd(), "src/audio-worklets/BaseProcessor.ts")).text();

        const javascript = await new Transpiler({
          loader: 'ts'
        }).transform(source);

        return new Response(javascript, {
          headers: {
            "Content-Type": "application/javascript",
            "Cache-Control": "no-store"
          }
        });
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
