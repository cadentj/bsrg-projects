# JS History through Pain Points — Planning Doc

The idea: build a toy JS-like language and a surrounding ecosystem, introducing each tool in response to the pain that historically motivated it. Each header below is a pain point. In the curriculum, each pain leads to a tool/technique we build (or adopt) to resolve it.

Some thoughts on the toy JS langauge: 
- Should compile from our basic syntax --> Javascript
- It should be useable to do basic scripting for a toy app
- It should work in a real browser (maybe just by compiling to JS)

---

# Toy Language Syntax (v1)

Python-ish, untyped, compiles to JavaScript. Placeholder name.

**Hello world**
```
print("hello, world")
```

**Variables and arithmetic**
```
let x = 10
let y = 20
print(x + y)
```

**Functions**
```
fn greet(name):
    let msg = "hello, " + name
    print(msg)

greet("caden")
```

**Conditionals**
```
fn classify(n):
    if n > 0:
        print("positive")
    elif n < 0:
        print("negative")
    else:
        print("zero")
```

**Loops**
```
let i = 0
while i < 5:
    print(i)
    i = i + 1

let nums = [1, 2, 3, 4]
for n in nums:
    print(n * 2)
```

**Lists**
```
let nums = [1, 2, 3]
nums.push(4)
print(nums[0])
print(len(nums))
```

**Dicts**
```
let user = {"name": "caden", "age": 24}
print(user["name"])
user["age"] = 25

# iterate
for key in user:
    print(key, user[key])
```

**Objects (struct-like)**

Small sugar over dicts — identifier keys and dot access. Compiles to a plain JS object.
```
let point = {x: 10, y: 20}
print(point.x)
point.y = 30
```

**Comments**
```
# single-line comment
let x = 10  # trailing comment also fine

# fn add(a, b):
#     return a + b
```

**Core built-ins (v1)**
- `print(...)` — writes to stdout (compiles to `console.log`)
- `len(x)` — length of list, dict, or string
- `str(x)`, `num(x)` — type conversion
- list methods: `.push`, `.pop`
- (deliberately small — we add more as pain demands)

---

Ordered roughly chronologically.

---

## 1. Code can't be split across files

Early JS: one `<script>` tag, or several, all sharing one global namespace. Two files both define `handleClick` → one silently overwrites the other. There's no `import`, no `require`, no modules of any kind.

**Why it matters historically:** forced the IIFE pattern (`(function(){ ... })()`) and the "namespace object" pattern (`MyApp.utils.foo`) as poor-man's modules. This is the soil that every module system grew out of.

**Playground step:** our compiler is growing — lexer, parser, emitter, runtime all in one file. We try to split them across files and the shared global namespace bites us (two files both define `Node`, one silently wins). We reach for IIFEs and a namespace object as the first fix.

**Tie to JS:** we're re-living the 2005-era pain verbatim. The discomfort of "I need structure but the language won't give it to me" is exactly what forced the module-system arms race.

### Exercise Thoughts: 
- Is there a way we could get people to arrive on the right decision decision on their own? Maybe with some extra help, like reading some primary or secondary sources on the topic?
- I like the puzzle style questions from Sasha Rush's Triton Puzzles. I wonder if there's an analogy to any of the issues here.

---

## 2. No way to reuse other people's code reproducibly

Pre-2010: you wanted jQuery, you downloaded `jquery.min.js` and committed it to your repo. No version numbers, no dependency graph, no way to update. Transitive dependencies were manual.

**Why it matters historically:** motivated npm (2010, originally for Node), later Bower (for browser, now dead), and eventually the idea that a JS project has a *manifest* (`package.json`) and a *lockfile*. Half your `package.json` fields trace back to solving this.

**Playground step:** a `<textarea>` is a terrible code editor — we want CodeMirror (syntax highlighting, line numbers, autocomplete). Writing our own is infeasible; downloading a zipped `codemirror.js` and committing it is primitive. We install the real thing via npm and see a `package.json` + lockfile appear.

**Tie to JS:** `npm install codemirror` is the first time we feel *why* the JS world moved from copy-pasted script tags to declared dependencies + lockfiles. The manifest isn't bureaucracy; it's the only way to say "I depend on CodeMirror 6.x" reproducibly.

---

## 3. Server-side JS needs real modules

Node (2009) wanted to write non-trivial server programs. Globals-and-script-tags doesn't fly when you have a 50-file backend. Node adopted **CommonJS**: `const x = require('./foo')`, synchronous, runtime-resolved, filesystem-based.

**Why it matters historically:** CJS became the lingua franca of server JS for a decade. Every npm package shipped CJS. The entire ecosystem's "default" was CJS until ESM started winning around 2020 — and we're still cleaning up the mess.

**Playground step:** the compiler runs on our machine (via Node) during build. We now split it into `lexer.js`, `parser.js`, `emitter.js`, each with `require('./lexer')`. Multi-file Node code works beautifully because `require` is synchronous and the filesystem is right there.

**Tie to JS:** this is the Node / CJS origin story exactly. We adopt the same solution for the same reason Node did — which makes it obvious why CJS was correct *for the server* and wrong *for the browser*.

---

## 4. Browser can't do synchronous `require`

CJS assumes you can block on a local filesystem read. Browsers can't — fetching a module over the network is async. You can't evaluate `require('./foo')` inline because `foo` hasn't arrived yet.

**Why it matters historically:** motivated AMD (`define([...deps], factory)`) as an async alternative, UMD as the "works in both" wrapper, and — critically — **bundlers** as a workaround: pre-compile the whole dep graph into a single file so the browser never has to do runtime resolution. Browserify (2011) and webpack (2012) were born here.

**Playground step:** we want the playground to run *in the browser* — user types toy code, compiler runs client-side, output shows live. But our CJS compiler can't load `require('./parser')` in a browser. We write a ~150-line toy bundler in Node: walk the entry's `require` graph, wrap each module in a function, emit one `bundle.js`. Ship it to the browser.

**Tie to JS:** this is browserify in miniature. Building it ourselves makes bundlers feel like a *natural* solution rather than a mysterious config layer — they exist because the browser can't do what Node can.

---

## 5. Browsers don't implement new JS fast enough

ES6 (2015) shipped classes, arrow functions, `let`/`const`, destructuring. Developers wanted to use them *immediately*. IE11 and older browsers didn't support them and wouldn't for years.

**Why it matters historically:** motivated **transpilers**. Babel (2014, originally "6to5") compiled ES6 → ES5 so you could write modern code and ship it everywhere. This established the pattern that the JS you *write* is not the JS that *runs*. Every tool downstream (TypeScript, JSX, Svelte compilation) inherits this pattern.

**Playground step:** meta moment — our playground *is* a transpiler (toy → JS). We notice our compiler emits modern JS (arrow fns, `let`, template strings) and want to support older browsers. We add a downlevel pass (or pipe output through esbuild with `target: es5`). We also recognize: the thing we built is architecturally identical to Babel.

**Tie to JS:** the "write one thing, ship another" pattern isn't special to JS — it's what our whole project *is*. Once the group sees that, Babel and TS stop being magical JS-only tools and become "compilers that target JS."

---

## 6. JS's dynamic typing hurts at scale

Large codebases: refactors break silently, IDE autocomplete is guessing, `undefined is not a function` at runtime. Tolerable at 1k LoC, miserable at 500k.

**Why it matters historically:** Facebook tried Flow (2014), Microsoft built TypeScript (2012, took off ~2016). TS won by being *gradual* and *deliberately unsound* — pragmatism over correctness. The decision to make TS strip-only (types are erased, not enforced at runtime) shaped how every transpiler since treats types.

**Playground step:** our AST has ~15 node shapes. A refactor renames `node.value` to `node.literal` and things silently break in the emitter. We add type annotations to the compiler — either port the compiler to TypeScript, or add an optional type layer to our toy language and use it. Types are stripped at build time; runtime is unchanged.

**Tie to JS:** mirrors the TS origin story: types bolted onto a dynamic language *after the fact*, stripped at compile time, gradual adoption. Doing this on our compiler makes the "why strip-only?" design decision feel obvious rather than weird.

---

## 7. Sending 400 files to the browser is slow

HTTP/1.1 limits concurrent requests. Each request has overhead. A naive "one file per module" browser loader means a waterfall of hundreds of requests before your app boots.

**Why it matters historically:** the practical argument for bundlers. Even after async module loading was possible (AMD, then native ESM), bundling stuck around because one request for a concatenated file beats a hundred requests for tiny files. HTTP/2 multiplexing weakened this argument but didn't kill it.

**Playground step:** we switch to native ESM (`<script type="module">`) to see what the browser can do unaided. It works — but the network tab shows 30+ sequential requests as it resolves `import` chains through our compiler + CodeMirror. We re-run our bundler and watch load time collapse.

**Tie to JS:** shows that bundlers aren't just a module-system hack — they're a performance tool, independent of whether the browser supports modules natively. This is why bundling survived ESM shipping.

---

## 8. Bundle sizes are huge

Naive bundling means visiting `/login` downloads your entire app including the admin dashboard and the checkout flow. Users on slow networks suffer.

**Why it matters historically:** motivated **tree-shaking** (drop unused exports — relies on ESM's static structure, which is a big reason ESM was designed to be static), **code-splitting** (lazy chunks loaded on demand), and **dynamic import** (`import()`). This is why Rollup pushed ESM-first: CJS can't be tree-shaken reliably because `require` is dynamic.

**Playground step:** the playground now includes a docs panel, AST visualizer, and example gallery. Bundle is ~2MB; most first-time users never open the docs. We add code-splitting (lazy-load the docs chunk on first click) and tree-shaking (drop unused CodeMirror extensions). Bundle drops to something reasonable.

**Tie to JS:** demonstrates why Rollup/ESM won the library bundler space. You literally can't tree-shake our CJS toy bundler's output because `require` is dynamic — you need ESM's static structure. That constraint is a language-design decision with real consequences.

---

## 9. Every save triggers a full rebuild

Early bundler dev loops: edit a file → rebuild the whole bundle → reload the page → lose your app state. Painful for anything non-trivial.

**Why it matters historically:** motivated **watch mode**, then **incremental compilation**, then **Hot Module Replacement** (HMR) — swap a module in a running app without losing state. HMR is one of the killer features of modern dev servers and why Vite/webpack-dev-server feel magical.

**Playground step:** we're iterating on the compiler constantly. Every save → rebuild bundle → reload page → the toy program the user typed into the textarea is wiped. Add a file watcher that rebuilds on save, then an HMR protocol (websocket + module-replacement stub) so we can edit the compiler without blowing away playground state.

**Tie to JS:** the "why is HMR a killer feature?" question is abstract until you personally lose your textarea contents 40 times in an hour. Then it's obvious.

---

## 10. Cold-start dev servers are slow

Webpack-era dev: start the server, wait 30 seconds while it bundles everything, *then* you can open localhost. For large apps, dev startup became minutes.

**Why it matters historically:** motivated Vite's architectural bet — **don't bundle in dev at all**. Serve native ESM to the browser, let it request modules on demand, only transform what's needed. Dev server starts instantly regardless of app size. This is *the* defining idea of modern JS tooling in the 2020s.

**Playground step:** our toy bundler's cold-start time grows linearly with compiler size. We switch to a dev mode that doesn't bundle: a tiny HTTP server serves each module as its own request, the browser resolves imports natively, we only transform on demand. Cold start drops from seconds to near-instant.

**Tie to JS:** lets us feel the Vite insight directly. "Don't do the work until the browser asks for it" is the kind of architectural bet that seems obvious in hindsight and was non-obvious for a decade.

---

## 11. JS-in-JS tooling is slow

Babel, webpack, Rollup are all written in JavaScript. Parsing JS in JS, for a large codebase, is inherently slow — you're running an interpreter on an interpreter.

**Why it matters historically:** motivated the native-language rewrites: **esbuild** (Go, ~2020), **SWC** (Rust, ~2019), **Turbopack** (Rust, 2022), **Rolldown** (Rust, 2024). The speedups were 10–100x, enough to reshape what tools people use. Vite uses esbuild in dev and is migrating its prod bundler from Rollup to Rolldown.

**Playground step:** time our JS-based compiler on a large toy program (generate a 10,000-line one). It's slow. Swap the JS-emission / minification step to esbuild and measure again — order-of-magnitude faster. Optional exercise: port our parser to a WASM language for comparison.

**Tie to JS:** turns an abstract "native is faster" claim into a stopwatch number. Makes clear why esbuild/SWC/Rolldown are reshaping the ecosystem even though they're "just rewrites."

---

## 12. Errors in transpiled/bundled code are unreadable

Stack trace says `bundle.min.js:1:48372`. The original source was `src/components/Checkout.tsx:42`. You can't debug what you can't read.

**Why it matters historically:** motivated **source maps** — a JSON file that maps positions in the output back to the original source. Every transpiler and bundler generates them. Browsers and Node both consume them. Without source maps, the "transpile everything" ecosystem would be unusable in production.

**Playground step:** user writes broken toy code. Browser throws; the stack trace points at compiled JS line 847, which is meaningless. We teach our emitter to track `{ line, col }` positions from source to output, emit a `.map` file alongside the bundle, and watch the error now point at the user's toy-language line. Satisfying.

**Tie to JS:** source maps feel like plumbing until you see them light up. Once the error jumps to the right line, the group understands why *every* transpiler in the JS world ships them and why their absence would make the ecosystem unworkable.

---

## 13. Imperative DOM updates don't scale

jQuery-era code: a click handler reads state from the DOM, computes new state, writes it back to the DOM. With many interacting pieces of state, you get a spaghetti of "if this element changes, remember to update those three other elements." Bugs are inevitable.

**Why it matters historically:** motivated **declarative UI frameworks** — React (2013), Vue (2014), Svelte (2016). The shared idea: you describe what the UI *should look like* given the current state, the framework figures out what DOM operations to perform. This is the single biggest shift in how frontend code is written in the last 15 years.

**Playground step:** the playground UI has the editor, output pane, AST view, error display, compile button, share button — all of which need to update coherently as state changes. Imperative DOM updates become spaghetti. We write a ~50-line signals-based reactive runtime (`signal`, `effect`, `derived`) and refactor the UI on top of it.

**Tie to JS:** writing a signals runtime yourself makes React/Vue/Svelte stop being "frameworks you learn" and start being "solutions to a problem you've had." The 50 lines you wrote is the core of SolidJS.

---

## 14. Node-isms don't run on the edge or in the browser

Node has `fs`, `path`, `process`, `Buffer`, a specific module resolution algorithm, CJS by default. None of this exists in Cloudflare Workers, Deno, or the browser. Code written for Node doesn't port.

**Why it matters historically:** motivated the **Web-Standard APIs** push — runtimes agreeing on `fetch`, `Request`, `Response`, `ReadableStream` as the common vocabulary. Deno (2020) and Bun (2022) both ship Web APIs as first-class. Node has been back-porting them (`fetch` landed in Node 18). This is an active, ongoing realignment.

**Playground step:** we want shareable playground URLs (`playground.example/abc123`). User code can't run on our server for free — sandbox it in a Cloudflare Worker. Our build tooling used `fs.readFileSync` for example programs; Workers have no `fs`. We migrate to `fetch` + KV storage, swapping Node-only APIs for web-standard ones.

**Tie to JS:** makes the "Node-isms don't port" problem concrete. Every `fs` call you have to replace is a small lesson in why runtimes are converging on web standards.

---

## 15. `node_modules` is a disaster

400MB on disk, 30,000+ files, slow to install, slow to traverse, duplicated across every project on your machine. npm's install algorithm was designed in 2010 and the ecosystem has outgrown it.

**Why it matters historically:** motivated **pnpm** (content-addressable store + symlinks — install once globally, symlink into each project), **yarn PnP** (no `node_modules` at all, zip-based resolution), **bun**'s install (parallelism + native speed). This is also where supply-chain concerns live: lockfiles, `npm audit`, package signing discussions.

**Playground step:** we've accumulated CodeMirror, esbuild, a parser-combinator lib, a test framework, a deploy CLI. `du -sh node_modules` — it's huge. We migrate to pnpm and show the symlinked structure; compare disk usage and install time against npm.

**Tie to JS:** hands-on "why does pnpm exist?" demonstration. Mostly a compare-and-discuss moment rather than a build step — there's nothing to construct, just to observe.

---

## 16. CJS and ESM don't interop cleanly

Node supports both. Import a CJS package from an ESM file → sometimes works, sometimes gives you `{ default: actualExport }`, sometimes errors. Libraries that ship both have a "dual-package hazard": two copies of the same module, two separate identities.

**Why it matters historically:** this is *the* reason `package.json` got complicated. `"type"`, `"main"`, `"module"`, `"exports"`, conditional exports, `.mjs` vs `.cjs` — all of it is Node trying to support both module systems without breaking the world. Arguably the biggest open wound in the JS ecosystem in 2026.

**Playground step:** we want to publish our compiler as an npm package so others can use it from Node scripts *and* from Vite projects. Try shipping CJS-only → Vite users complain. Ship ESM-only → Node script users break. We configure the `exports` field with conditional entries and ship both. Dual-package hazard manifests and we debug it.

**Tie to JS:** turns the opaque `exports` field into something with a story. Every field you add is answering a specific "what environment is importing me?" question.

---

## 17. Configuration explosion

A modern project has `package.json`, `tsconfig.json`, `vite.config.ts`, `eslint.config.js`, `.prettierrc`, `postcss.config.js`, `.browserslistrc`, `.npmrc`, sometimes more. Each has its own schema, docs, and gotchas. Onboarding a new developer is mostly explaining config.

**Why it matters historically:** motivated **zero-config tools** (Parcel's original pitch) and **opinionated frameworks** (Next.js, Remix, SvelteKit, Astro) that hide the config behind a single `framework.config.js`. The trade is flexibility for velocity — and most teams are taking it.

**Playground step:** retrospective. Count every config file we've accumulated: `package.json`, `tsconfig.json`, bundler config, dev-server config, `.eslintrc`, `.prettierrc`, `wrangler.toml` for the Worker, `pnpm-workspace.yaml` if we split packages. Then: try rebuilding the playground on top of a meta-framework (SvelteKit or Astro) and watch most of the configs collapse into one.

**Tie to JS:** only makes sense *after* having felt each config's pain. The "frameworks hide this" conclusion lands because you paid the cost of every layer they're hiding.

---

# How these map to sessions

Probably too many for three 2-hour sessions. A rough grouping:

- **Session 1 — Modules, packaging, building:** pains 1, 2, 3, 4, 7, 8. Build a toy language + a toy bundler. End with a multi-file program running in a browser.
- **Session 2 — Transpilation, types, dev loop:** pains 5, 6, 9, 10, 11, 12. Add a type-stripper, a dev server with HMR, source maps.
- **Session 3 — The modern stack:** pains 13, 14, 15, 16, 17. Build a tiny reactive framework. Discuss runtimes, interop, and the framework-as-config-hider trend.

Open question: pain 13 (declarative UI) is huge and probably deserves its own session. Could push that to a 4th week or cut it and leave frameworks as "further reading."
