import { execSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

/** The unpacked extension must be built before Chromium loads it. */
export default async function globalSetup(): Promise<void> {
  const extensionRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
  execSync("bun run build", { cwd: extensionRoot, stdio: "inherit" });
}
