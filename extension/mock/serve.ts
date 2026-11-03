/**
 * Mock Target Page static server (port 3011).
 * Run: bun mock/serve.ts   →   http://localhost:3011/  and /controlled.html
 */
const PORT = Number(process.env.MOCK_PORT ?? 3011);

const server = Bun.serve({
  port: PORT,
  async fetch(request) {
    const url = new URL(request.url);
    const path = url.pathname === "/" ? "/index.html" : url.pathname;
    const file = Bun.file(`${import.meta.dir}${path}`);
    if (!(await file.exists())) {
      return new Response("Nie znaleziono strony mock.", { status: 404 });
    }
    return new Response(file);
  },
});

console.log(`Mock Target Page: http://localhost:${server.port}/  (+ /controlled.html)`);
