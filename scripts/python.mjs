import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
const python = fileURLToPath(new URL("../.venv/bin/python", import.meta.url));
if (!existsSync(python)) {
  console.error("Run npm run setup to install the project Python environment.");
  process.exit(1);
}
const child = spawn(python, process.argv.slice(2), { stdio: "inherit" });
child.on("error", () => {
  process.exitCode = 1;
});
child.on("exit", (code) => {
  process.exitCode = code ?? 1;
});
