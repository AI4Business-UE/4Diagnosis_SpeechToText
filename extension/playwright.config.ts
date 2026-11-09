import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  workers: 1,
  reporter: "list",
  globalSetup: "./e2e/global-setup.ts",
  webServer: [
    {
      command: "bun run dev",
      cwd: "../app",
      url: "http://localhost:3010",
      reuseExistingServer: true,
      stdout: "ignore",
      stderr: "pipe",
    },
    {
      command: "bun mock/serve.ts",
      url: "http://localhost:3011",
      reuseExistingServer: true,
      stdout: "ignore",
      stderr: "pipe",
    },
  ],
});
