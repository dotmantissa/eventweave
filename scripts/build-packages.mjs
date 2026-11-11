import { readFileSync, mkdirSync, writeFileSync } from "node:fs";
import ts from "typescript";

// Publish executable JavaScript inside each workspace. Node functions cannot
// consume TypeScript package exports, even when the entry function is compiled.
for (const name of ["protocol", "client"]) {
  const source = `packages/${name}/src/index.ts`;
  const result = ts.transpileModule(readFileSync(source, "utf8"), {
    fileName: source,
    compilerOptions: {
      target: ts.ScriptTarget.ES2022,
      module: ts.ModuleKind.ESNext,
    },
  });
  mkdirSync(`packages/${name}/dist`, { recursive: true });
  writeFileSync(`packages/${name}/dist/index.js`, result.outputText);
}
