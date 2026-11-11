import { spawn } from "node:child_process";
const child = spawn("python3", ["scripts/network-verify.py"], {
  stdio: "inherit",
});
child.on("exit", (code) => {
  process.exitCode = code ?? 1;
});
