import { execSync } from "child_process";
import { readFileSync, existsSync, mkdirSync, rmSync, readdirSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dir = dirname(fileURLToPath(import.meta.url));
const CACHE = join(__dir, ".tests-cache");
const GENERATED = join(__dir, "src", "generated");
const OUT_DIR = join(__dir, "output");

function run(cmd) {
  console.log("  >", cmd);
  execSync(cmd, { stdio: "inherit" });
}

function ensure(dir) {
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
}

console.log("\n=== Step 0: Install dependencies ===");
run(`cd ${__dir} && npm install`);

console.log('\n=== Step 2: Using cached .tests-cache ===');

console.log("\n=== Step 2: Generate vectors ===");
run(`cd ${CACHE} && npm install`);
run(`cd ${CACHE} && node gen_types.mjs`);

const VEC_DIR = join(CACHE, "vectors");

console.log("\n=== Step 3: Generate emit code ===");
if (existsSync(GENERATED)) rmSync(GENERATED, { recursive: true });
ensure(GENERATED);

run(`cd ${__dir} && node_modules/.bin/tsp compile ${CACHE}/alltypes.tsp --emit=@specodec/typespec-emitter-python \
  --option @specodec/typespec-emitter-python.emitter-output-dir=${GENERATED}`);

const pyFiles = readdirSync(GENERATED).filter(f => f.endsWith(".py"));
if (pyFiles.length > 0) {
  console.log("  ✓ Generated " + pyFiles.join(", "));
} else {
  console.error("  FAIL: No generated Python files");
  process.exit(1);
}

console.log("\n=== Step 4: Generate test runner ===");
run(`cd ${__dir} && VEC_DIR=${VEC_DIR} node generate_emit_runner.mjs`);

console.log("\n=== Step 5: Type check ===");
run(`cd ${__dir} && mypy ${GENERATED} emit/ ../../src/ --ignore-missing-imports`);

console.log("\n=== Step 6: Run tests ===");
if (existsSync(OUT_DIR)) rmSync(OUT_DIR, { recursive: true });
ensure(OUT_DIR);

// Fetch runtime from Forgejo PyPI
run(`pip install --break-system-packages --index-url http://10.199.64.20:3000/api/packages/specodec/pypi/simple/ --trusted-host 10.199.64.20 specodec-runtime-python==1.0.0`);

try { run(`cd ${__dir} && VEC_DIR=${VEC_DIR} OUT_DIR=${OUT_DIR} python emit/main.py`); } catch (e) { console.log("Python tests completed (some failures expected)"); }

console.log('\n=== Step 7: Compare output ===');
const manifest = JSON.parse(readFileSync(join(VEC_DIR, 'manifest.json'), 'utf-8'));
let match = 0, mismatch = 0;

for (const [name] of Object.entries(manifest.scalars || {})) {
  const expected = join(VEC_DIR, 'scalars', `${name}.mp`);
  const actual = join(OUT_DIR, 'scalars', `${name}.mp`);
  if (!existsSync(actual)) { mismatch++; console.log(`MISSING: ${name}.mp`); continue; }
  if (readFileSync(expected).equals(readFileSync(actual))) match++;
  else { mismatch++; console.log(`MISMATCH: ${name}.mp`); }
}
for (const model of [...(manifest.testModels || []), ...(manifest.testUnions || [])]) {
  for (const [outExt, vecExt] of [['msgpack','msgpack'], ['json','json'], ['unformatted.json','json'], ['gron','gron']]) {
    const expected = join(VEC_DIR, `${model}.${vecExt}`);
    const actual = join(OUT_DIR, `${model}.${outExt}`);
    if (!existsSync(expected)) continue;
    if (!existsSync(actual)) { mismatch++; console.log(`MISSING: ${model}.${outExt}`); continue; }
    if (readFileSync(expected).equals(readFileSync(actual))) match++;
    else { mismatch++; console.log(`MISMATCH: ${model}.${outExt}`); }
  }
}
const total = match + mismatch;
console.log(`${match}/${total} match, ${mismatch} mismatch`);
if (mismatch > 0) process.exit(1);

console.log("\n=== ALL PASSED ===");