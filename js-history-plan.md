# JS History through Pain Points — Planning Doc

The idea: build a toy JS-like language and a surrounding ecosystem, introducing each tool in response to the pain that historically motivated it. Each header below is a pain point. In the curriculum, each pain leads to a tool/technique we build (or adopt) to resolve it.

Ordered roughly chronologically.

---

## 1. Code can't be split across files

Early JS: one `<script>` tag, or several, all sharing one global namespace. Two files both define `handleClick` → one silently overwrites the other. There's no `import`, no `require`, no modules of any kind.

**Why it matters historically:** forced the IIFE pattern (`(function(){ ... })()`) and the "namespace object" pattern (`MyApp.utils.foo`) as poor-man's modules. This is the soil that every module system grew out of.

---

## 2. No way to reuse other people's code reproducibly

Pre-2010: you wanted jQuery, you downloaded `jquery.min.js` and committed it to your repo. No version numbers, no dependency graph, no way to update. Transitive dependencies were manual.

**Why it matters historically:** motivated npm (2010, originally for Node), later Bower (for browser, now dead), and eventually the idea that a JS project has a *manifest* (`package.json`) and a *lockfile*. Half your `package.json` fields trace back to solving this.

---

## 3. Server-side JS needs real modules

Node (2009) wanted to write non-trivial server programs. Globals-and-script-tags doesn't fly when you have a 50-file backend. Node adopted **CommonJS**: `const x = require('./foo')`, synchronous, runtime-resolved, filesystem-based.

**Why it matters historically:** CJS became the lingua franca of server JS for a decade. Every npm package shipped CJS. The entire ecosystem's "default" was CJS until ESM started winning around 2020 — and we're still cleaning up the mess.

---

## 4. Browser can't do synchronous `require`

CJS assumes you can block on a local filesystem read. Browsers can't — fetching a module over the network is async. You can't evaluate `require('./foo')` inline because `foo` hasn't arrived yet.

**Why it matters historically:** motivated AMD (`define([...deps], factory)`) as an async alternative, UMD as the "works in both" wrapper, and — critically — **bundlers** as a workaround: pre-compile the whole dep graph into a single file so the browser never has to do runtime resolution. Browserify (2011) and webpack (2012) were born here.

---

## 5. Browsers don't implement new JS fast enough

ES6 (2015) shipped classes, arrow functions, `let`/`const`, destructuring. Developers wanted to use them *immediately*. IE11 and older browsers didn't support them and wouldn't for years.

**Why it matters historically:** motivated **transpilers**. Babel (2014, originally "6to5") compiled ES6 → ES5 so you could write modern code and ship it everywhere. This established the pattern that the JS you *write* is not the JS that *runs*. Every tool downstream (TypeScript, JSX, Svelte compilation) inherits this pattern.

---

## 6. JS's dynamic typing hurts at scale

Large codebases: refactors break silently, IDE autocomplete is guessing, `undefined is not a function` at runtime. Tolerable at 1k LoC, miserable at 500k.

**Why it matters historically:** Facebook tried Flow (2014), Microsoft built TypeScript (2012, took off ~2016). TS won by being *gradual* and *deliberately unsound* — pragmatism over correctness. The decision to make TS strip-only (types are erased, not enforced at runtime) shaped how every transpiler since treats types.

---

## 7. Sending 400 files to the browser is slow

HTTP/1.1 limits concurrent requests. Each request has overhead. A naive "one file per module" browser loader means a waterfall of hundreds of requests before your app boots.

**Why it matters historically:** the practical argument for bundlers. Even after async module loading was possible (AMD, then native ESM), bundling stuck around because one request for a concatenated file beats a hundred requests for tiny files. HTTP/2 multiplexing weakened this argument but didn't kill it.

---

## 8. Bundle sizes are huge

Naive bundling means visiting `/login` downloads your entire app including the admin dashboard and the checkout flow. Users on slow networks suffer.

**Why it matters historically:** motivated **tree-shaking** (drop unused exports — relies on ESM's static structure, which is a big reason ESM was designed to be static), **code-splitting** (lazy chunks loaded on demand), and **dynamic import** (`import()`). This is why Rollup pushed ESM-first: CJS can't be tree-shaken reliably because `require` is dynamic.

---

## 9. Every save triggers a full rebuild

Early bundler dev loops: edit a file → rebuild the whole bundle → reload the page → lose your app state. Painful for anything non-trivial.

**Why it matters historically:** motivated **watch mode**, then **incremental compilation**, then **Hot Module Replacement** (HMR) — swap a module in a running app without losing state. HMR is one of the killer features of modern dev servers and why Vite/webpack-dev-server feel magical.

---

## 10. Cold-start dev servers are slow

Webpack-era dev: start the server, wait 30 seconds while it bundles everything, *then* you can open localhost. For large apps, dev startup became minutes.

**Why it matters historically:** motivated Vite's architectural bet — **don't bundle in dev at all**. Serve native ESM to the browser, let it request modules on demand, only transform what's needed. Dev server starts instantly regardless of app size. This is *the* defining idea of modern JS tooling in the 2020s.

---

## 11. JS-in-JS tooling is slow

Babel, webpack, Rollup are all written in JavaScript. Parsing JS in JS, for a large codebase, is inherently slow — you're running an interpreter on an interpreter.

**Why it matters historically:** motivated the native-language rewrites: **esbuild** (Go, ~2020), **SWC** (Rust, ~2019), **Turbopack** (Rust, 2022), **Rolldown** (Rust, 2024). The speedups were 10–100x, enough to reshape what tools people use. Vite uses esbuild in dev and is migrating its prod bundler from Rollup to Rolldown.

---

## 12. Errors in transpiled/bundled code are unreadable

Stack trace says `bundle.min.js:1:48372`. The original source was `src/components/Checkout.tsx:42`. You can't debug what you can't read.

**Why it matters historically:** motivated **source maps** — a JSON file that maps positions in the output back to the original source. Every transpiler and bundler generates them. Browsers and Node both consume them. Without source maps, the "transpile everything" ecosystem would be unusable in production.

---

## 13. Imperative DOM updates don't scale

jQuery-era code: a click handler reads state from the DOM, computes new state, writes it back to the DOM. With many interacting pieces of state, you get a spaghetti of "if this element changes, remember to update those three other elements." Bugs are inevitable.

**Why it matters historically:** motivated **declarative UI frameworks** — React (2013), Vue (2014), Svelte (2016). The shared idea: you describe what the UI *should look like* given the current state, the framework figures out what DOM operations to perform. This is the single biggest shift in how frontend code is written in the last 15 years.

---

## 14. Node-isms don't run on the edge or in the browser

Node has `fs`, `path`, `process`, `Buffer`, a specific module resolution algorithm, CJS by default. None of this exists in Cloudflare Workers, Deno, or the browser. Code written for Node doesn't port.

**Why it matters historically:** motivated the **Web-Standard APIs** push — runtimes agreeing on `fetch`, `Request`, `Response`, `ReadableStream` as the common vocabulary. Deno (2020) and Bun (2022) both ship Web APIs as first-class. Node has been back-porting them (`fetch` landed in Node 18). This is an active, ongoing realignment.

---

## 15. `node_modules` is a disaster

400MB on disk, 30,000+ files, slow to install, slow to traverse, duplicated across every project on your machine. npm's install algorithm was designed in 2010 and the ecosystem has outgrown it.

**Why it matters historically:** motivated **pnpm** (content-addressable store + symlinks — install once globally, symlink into each project), **yarn PnP** (no `node_modules` at all, zip-based resolution), **bun**'s install (parallelism + native speed). This is also where supply-chain concerns live: lockfiles, `npm audit`, package signing discussions.

---

## 16. CJS and ESM don't interop cleanly

Node supports both. Import a CJS package from an ESM file → sometimes works, sometimes gives you `{ default: actualExport }`, sometimes errors. Libraries that ship both have a "dual-package hazard": two copies of the same module, two separate identities.

**Why it matters historically:** this is *the* reason `package.json` got complicated. `"type"`, `"main"`, `"module"`, `"exports"`, conditional exports, `.mjs` vs `.cjs` — all of it is Node trying to support both module systems without breaking the world. Arguably the biggest open wound in the JS ecosystem in 2026.

---

## 17. Configuration explosion

A modern project has `package.json`, `tsconfig.json`, `vite.config.ts`, `eslint.config.js`, `.prettierrc`, `postcss.config.js`, `.browserslistrc`, `.npmrc`, sometimes more. Each has its own schema, docs, and gotchas. Onboarding a new developer is mostly explaining config.

**Why it matters historically:** motivated **zero-config tools** (Parcel's original pitch) and **opinionated frameworks** (Next.js, Remix, SvelteKit, Astro) that hide the config behind a single `framework.config.js`. The trade is flexibility for velocity — and most teams are taking it.

---

# How these map to sessions

Probably too many for three 2-hour sessions. A rough grouping:

- **Session 1 — Modules, packaging, building:** pains 1, 2, 3, 4, 7, 8. Build a toy language + a toy bundler. End with a multi-file program running in a browser.
- **Session 2 — Transpilation, types, dev loop:** pains 5, 6, 9, 10, 11, 12. Add a type-stripper, a dev server with HMR, source maps.
- **Session 3 — The modern stack:** pains 13, 14, 15, 16, 17. Build a tiny reactive framework. Discuss runtimes, interop, and the framework-as-config-hider trend.

Open question: pain 13 (declarative UI) is huge and probably deserves its own session. Could push that to a 4th week or cut it and leave frameworks as "further reading."
