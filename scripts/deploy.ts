import { spawn } from "node:child_process";
const child = spawn(
  "python3",
  ["scripts/deploy.py", ...process.argv.slice(2)],
  { stdio: "inherit" },
);
child.on("exit", (code) => {
  process.exitCode = code ?? 1;
});
