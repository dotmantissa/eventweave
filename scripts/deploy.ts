import { spawn } from "node:child_process";
const child = spawn(
  process.execPath,
  ["scripts/python.mjs", "scripts/deploy.py", ...process.argv.slice(2)],
  { stdio: "inherit" },
);
child.on("exit", (code) => {
  process.exitCode = code ?? 1;
});
