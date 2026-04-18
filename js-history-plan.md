
The web has a long history, and there are a lot of design decisions that went into the modern javascript ecosystem. There are also a lot of tools and conventions (many of them overlapping), and it would be great to orient myself on them.

Rather than learning things by just reading "esbuild is X", I'd like to build a toy project, progressively going up the tech stack to understand why tools and language changes occured.

## What we're building

We'll build a toy chat app. A user types messages, an LLM responds. We start as a single HTML file with a `<script>` tag calling a free OpenRouter endpoint and grow into a multi-page web app with streaming responses, conversation history, markdown rendering, and a settings panel — deployed to the edge.

**Feature progression (rough shape, not a rigid plan):**
- v1: one page, one input, messages stacked, non-streaming response
- v2: streaming tokens (arrive as they generate), markdown rendering with code blocks
- v3: conversation list sidebar, settings page, shareable URLs, deployed to Cloudflare

### Architecture

- **Client** — the browser app. Most of our work lives here.
- **Proxy** — a tiny Node server that holds the OpenRouter API key and forwards requests from the browser. Never put the API key in client JS — it leaks to anyone viewing page source. The proxy grows into a real backend (rate limiting, model list, usage tracking) as sessions progress.

### Source conventions

We start writing **plain, old-style JavaScript** — no `let`/`const`, no arrow functions, no modules. ES3/ES5-ish. This is deliberate: starting old-school makes each ecosystem advance an authentic pain relief rather than a fake analogy. Modern syntax gets introduced later via a transpile step (pain #5).

### Tooling language

All the tools we build (bundler, type-stripper, dev server, source-map generator) are written in **zero-dependency Node**. We deliberately don't shell out to `esbuild` or `webpack` initially — we implement them ourselves in vanilla Node, the same language the real ecosystem is mostly built in. Pain #11 is where we swap our hand-rolled tool for a native one and feel the speedup.

### Stretch / optional

- **Streaming** (ReadableStream / async iterators) pulled in at session 1. Exposes a whole async-concurrency story in JS. Drop if it eats too much time.
- **Triton-puzzle-style exercises** — concrete before/after perf targets the group races to hit (e.g., "get the settings page under 50KB"). Fit naturally at pains 8, 10, 12, 13.

### Exercise Thoughts: 
- Is there a way we could get people to arrive on the right decision decision on their own? Maybe with some extra help, like reading some primary or secondary sources on the topic?
- I like the puzzle style questions from Sasha Rush's Triton Puzzles. I wonder if there's an analogy to any of the issues here.

---

Pain points below are ordered roughly chronologically.

---

## 1. Code can't be split across files

Early JS: one `<script>` tag, or several, all sharing one global namespace. Two files both define `handleClick` → one silently overwrites the other. There's no `import`, no `require`, no modules of any kind.

**Why this mattered**: 
Forced the IIFE pattern and "namespace object" pattern as poor-man's modules. Modern module systems grew out of these patterns.
- **IIFE** (Immediately Invoked Function Expression) — `(function(){ ... })()`. A function you define and call in the same expression. Everything declared inside is scoped to the function, not leaked to `window`.
- **Namespace object pattern** — instead of 30 globals (`addMessage`, `renderAll`, `sendToApi`, ...), you make *one* global (`APP`) and hang everything off it: `APP.state.addMessage(...)`, `APP.render.renderAll()`. Poor-man's modules.


**Chat app step:** 
v1 is one `index.html` + one `<script>` tag. 

As we add features — message list rendering, input handling, fetch to the proxy, streaming parser, markdown display — the script crosses 300 lines. We split it into `api.js`, `render.js`, `state.js`, each as its own `<script>` tag. 

`render.js` and `state.js` both declare top-level `messages` → whichever loads last wins. We fall back to IIFEs + a manual `window.APP = {}` namespace and feel how fragile it is.

The goal is to help people understand the 2005-era script-tag pain. The discomfort of "I need structure but the language won't give it to me" is exactly what forced the module-system arms race.

**Version 1 — naive: every `var` is a global, files collide**

```html
<!DOCTYPE html>
<html>
<body>
  <div id="messages"></div>
  <input id="input" />
  <button id="send">Send</button>

  <script src="state.js"></script>
  <script src="render.js"></script>
</body>
</html>
```

```js
// state.js — holds the list of chat messages
var messages = [];

function addMessage(role, text) {
  messages.push({ role: role, text: text });
}
```

```js
// render.js — paints the DOM
var messages = document.getElementById('messages'); // same name!

function renderAll() {
  // we wanted to loop over the messages *array*,
  // but `messages` now points at a <div> — state.js's array is gone.
}
```

Both files do `var messages` at the top level. In classic `<script>` land that's the same as `window.messages = ...`. Whichever file loads last wins. Load order becomes load-bearing and silent. This is the pain.

Version 2 uses a `window.APP = {}` pattern. In a browser, top-level `var` and function declarations become properties of `window`. `window.APP = {}` creates one shared global object that every file attaches its public API to.

**Version 2 — IIFE wraps each file, one shared `APP` namespace**

```html
<!DOCTYPE html>
<html>
<body>
  <div id="messages"></div>
  <input id="input" />
  <button id="send">Send</button>

  <script>window.APP = {};</script>   <!-- create the shared namespace once -->
  <script src="state.js"></script>
  <script src="render.js"></script>
</body>
</html>
```

```js
// state.js
(function () {
  var messages = []; // private to this IIFE — invisible to render.js

  function addMessage(role, text) {
    messages.push({ role: role, text: text });
  }

  // publish only what other files need
  window.APP.state = {
    addMessage: addMessage,
    getMessages: function () { return messages; }
  };
})();
```

```js
// render.js
(function () {
  var messagesEl = document.getElementById('messages'); // private, can't collide

  function renderAll() {
    var list = window.APP.state.getMessages();
    messagesEl.innerHTML = list.map(function (m) {
      return '<div>' + m.role + ': ' + m.text + '</div>';
    }).join('');
  }

  window.APP.render = { renderAll: renderAll };
})();
```

Now `state.js`'s `messages` and `render.js`'s `messagesEl` each live inside their own function scope. The *only* thing either file leaks to the global world is its one entry on `window.APP`. You still have to pick unique keys on `APP` (`APP.state`, `APP.render`, `APP.api`), but that's one namespace to police instead of the whole global object. This is exactly why CommonJS and ES Modules feel like such a relief later — they bake "each file is its own scope, exports are explicit" into the language so you stop hand-rolling it.

### Caden Todos here: 
- Build a basic chat app using only the `<script>` tag for Javascript. Can expand on the basic patterns that Opus 4.7 gave me

### Exercises here: 
- Read about the old JS import system, maybe from the "JS: First 20 years" source. 
- Read through Alman's blog post, maybe some linked ECMA standards
- Maybe I give people version 1 of the script with a big state file and ask them to do some light refactoring into the global `APP` pattern. 
  - Plant a footgun where, the logical ordering of imports looks fine but for some reason render has to be written first since it loads ~last for some reason?
  - (Opus 4.7) Why it works mechanically: classic `<script src="...">` tags (no `async`/`defer`) execute synchronously in document order. Every top-level `var x = ...` or `function x() {}` is `window.x = ...`, so if two files both declare `messages`, the one listed **later** in the HTML wins. Deterministic, not racy.
  - (Opus 4.7) Make the failure *runtime*, not load-time. If state.js and render.js both `var messages = ...` and render.js loads last, `window.messages` ends up pointing at a `<div>`. Nothing breaks at load — everything parses and every function gets defined. The app only explodes when someone types a message and `addMessage` runs `messages.push(...)` → `TypeError: messages.push is not a function`. The stack trace points at state.js (the caller), but the *cause* is render.js (the clobberer). That distance between symptom and cause is the whole lesson.
  - (Opus 4.7) The "logical ordering" twist: put the scripts in the order a human would naturally write them — state first, render second ("define the data, then render it"). That's what breaks. The fix-by-reordering workaround (put render *first* so state clobbers it) feels absurd because it reverses the mental model, which is what makes IIFEs feel like the real answer rather than a stylistic preference.
  - (Opus 4.7) Stronger variant: have the footgun involve a function, not just a var. Both files define `function init() { ... }`. Whichever loads last wins. At the bottom of the HTML you call `init()` — it does the wrong thing, and neither file's `init` looks wrong in isolation. Makes the point that *every* top-level identifier is a collision risk, not just variables.
  - (Opus 4.7) Keep the exercise on vanilla `<script src>` tags only. `defer` runs scripts in order but after parsing; `type="module"` gives each script its own scope. Either one makes the footgun non-deterministic or eliminates it entirely, and students get confused about why their fix "worked."

### References: 

Ben Alman, "Immediately-Invoked Function Expression (IIFE)"
- https://benalman.com/news/2010/11/immediately-invoked-function-expression/

Opus 4.7

---

## 2. No way to reuse other people's code reproducibly

Pre-2010: you wanted jQuery, you downloaded `jquery.min.js` and committed it to your repo. No version numbers, no dependency graph, no way to update. Transitive dependencies were manual.

**Why it matters historically:** motivated npm (2010, originally for Node), later Bower (for browser, now dead), and eventually the idea that a JS project has a *manifest* (`package.json`) and a *lockfile*. Half your `package.json` fields trace back to solving this.

**Chat app step:** LLM responses come back as markdown. We want them rendered as real HTML — headings, lists, inline code, code blocks. Writing our own markdown parser is a rabbit hole; we reach for `marked`. Without a package manager we'd download a zip, commit it, pin to whatever version was in the zip, and hope updates don't break us. Instead: `npm init`, `npm install marked`, and a `package.json` + lockfile appear.

**Tie to JS:** first real dependency. `npm install marked` is the moment the manifest-and-lockfile pattern stops feeling like bureaucracy and starts feeling like the only way to say "I depend on marked 9.x" reproducibly.


### Caden Todos here: 
- I disagree w claude, i think we should write a very basic markdown parser for users to use here, using NPM feels too easy.
- Then they can write a basic package manager? 
- i could write more than one package with some fake dependencies so they have to resolve the deps with a manager or smtn.

---

## 3. Server-side JS needs real modules

Node (2009) wanted to write non-trivial server programs. Globals-and-script-tags doesn't fly when you have a 50-file backend. Node adopted **CommonJS**: `const x = require('./foo')`, synchronous, runtime-resolved, filesystem-based.

**Why it matters historically:** CJS became the lingua franca of server JS for a decade. Every npm package shipped CJS. The entire ecosystem's "default" was CJS until ESM started winning around 2020 — and we're still cleaning up the mess.

**Chat app step:** the proxy was one `server.js`. It grows — routes for chat completion, model list, usage stats; middleware for rate limiting and logging. We split it across `server.js`, `routes/chat.js`, `routes/models.js`, `middleware/ratelimit.js`, each with `require('./routes/chat')` etc. Node's CJS makes this effortless because `require` is synchronous and the filesystem is right there.

**Tie to JS:** the Node / CJS origin story verbatim. Because we're building a server and a client at the same time, the contrast is vivid: the server side splits files beautifully; the browser side (pain #4 next door) can't.

---

## 4. Browser can't do synchronous `require`

CJS assumes you can block on a local filesystem read. Browsers can't — fetching a module over the network is async. You can't evaluate `require('./foo')` inline because `foo` hasn't arrived yet.

**Why it matters historically:** motivated AMD (`define([...deps], factory)`) as an async alternative, UMD as the "works in both" wrapper, and — critically — **bundlers** as a workaround: pre-compile the whole dep graph into a single file so the browser never has to do runtime resolution. Browserify (2011) and webpack (2012) were born here.

**Chat app step:** we love how the proxy splits across files. We want the same on the client — `require('./render')`, `require('./api')`. The browser can't do `require`. We write a ~150-line zero-dep Node bundler: walk the entry's require graph, wrap each module in a function, assign IDs, emit one `bundle.js` with a tiny runtime. The chat app now ships as one bundled `<script>` that loads `marked`, our modules, and the glue, all resolved at build time.

**Tie to JS:** browserify in miniature. Building it ourselves makes bundlers feel like a *natural* solution rather than a mysterious config layer — they exist because the browser can't do what Node can.

---

## 5. Browsers don't implement new JS fast enough

ES6 (2015) shipped classes, arrow functions, `let`/`const`, destructuring. Developers wanted to use them *immediately*. IE11 and older browsers didn't support them and wouldn't for years.

**Why it matters historically:** motivated **transpilers**. Babel (2014, originally "6to5") compiled ES6 → ES5 so you could write modern code and ship it everywhere. This established the pattern that the JS you *write* is not the JS that *runs*. Every tool downstream (TypeScript, JSX, Svelte compilation) inherits this pattern.

**Chat app step:** we've been writing `var` everywhere, IIFEs, no arrow functions. Tiring. We want modern JS — `let`/`const`, arrows, classes, template strings, async/await. We add a **transpile step** to our pipeline: write modern source → our tool rewrites to ES5 → bundler concatenates → ship. V1 handles a few transforms by hand (just enough — arrows, `let`/`const`, template strings); later we pipe through esbuild's `target: es5` for full coverage.

**Tie to JS:** Babel's exact origin story, told with our tooling. Writing even one transform ("arrow fn → function expression, re-bind `this`") makes transpilers stop feeling like magic.

---

## 6. JS's dynamic typing hurts at scale

Large codebases: refactors break silently, IDE autocomplete is guessing, `undefined is not a function` at runtime. Tolerable at 1k LoC, miserable at 500k.

**Why it matters historically:** Facebook tried Flow (2014), Microsoft built TypeScript (2012, took off ~2016). TS won by being *gradual* and *deliberately unsound* — pragmatism over correctness. The decision to make TS strip-only (types are erased, not enforced at runtime) shaped how every transpiler since treats types.

**Chat app step:** message shapes have gotten complicated — `{ role, content, tokens, streaming, error, retryCount, timestamp, citations, ... }`. A refactor renames `content` to `text` along one code path and the streaming renderer silently breaks — tokens stop showing up, no error, just a blank message. We port the app + tooling to TypeScript. Types are stripped at build; runtime is unchanged. The next refactor fails at edit time instead of at 2am during a demo.

**Tie to JS:** mirrors the TS origin story: types bolted onto a dynamic language *after the fact*, stripped at compile time, gradual adoption. The chat app becomes exactly the sort of codebase TS was designed for — lots of interacting data shapes, async edges, easy places to silently mis-wire.

---

## 7. Sending 400 files to the browser is slow

HTTP/1.1 limits concurrent requests. Each request has overhead. A naive "one file per module" browser loader means a waterfall of hundreds of requests before your app boots.

**Why it matters historically:** the practical argument for bundlers. Even after async module loading was possible (AMD, then native ESM), bundling stuck around because one request for a concatenated file beats a hundred requests for tiny files. HTTP/2 multiplexing weakened this argument but didn't kill it.

**Chat app step:** try shipping the chat app using native `<script type="module">` + `import`. It works — but the network tab shows a cascading waterfall of requests as the browser resolves the import chain through marked, our modules, and their transitive deps. We re-enable the bundler and the app loads in one round trip.

**Tie to JS:** bundlers aren't just a module-system hack — they're a performance tool, independent of whether the browser supports modules natively. Why bundling survived ESM shipping.

---

## 8. Bundle sizes are huge

Naive bundling means visiting `/login` downloads your entire app including the admin dashboard and the checkout flow. Users on slow networks suffer.

**Why it matters historically:** motivated **tree-shaking** (drop unused exports — relies on ESM's static structure, which is a big reason ESM was designed to be static), **code-splitting** (lazy chunks loaded on demand), and **dynamic import** (`import()`). This is why Rollup pushed ESM-first: CJS can't be tree-shaken reliably because `require` is dynamic.

**Chat app step:** we add a Settings page (model picker, theme, API-key management, usage history). Our naive bundler produces one monolithic bundle that includes the settings form libs, a color picker, and the admin tools on *every* page — including the main chat route. Set budgets: chat page < 150KB, settings page < 50KB. We miss. Add (a) route-level code splitting — settings becomes a lazy chunk loaded on navigation — and (b) tree-shaking, which requires switching import parsing to ESM's static `import`/`export` form so we can tell what's unused. Hit the budget.

**Tie to JS:** exactly why Rollup/ESM pushed static imports — you can't tree-shake our CJS bundler output because `require` is dynamic; you need ESM's static structure. A language-design decision with concrete downstream consequences.

**Exercise idea (Triton-puzzle style):** "The settings page is 180KB. Get it under 50KB without removing features." Group races, measures with their own bundler output, iterates.

---

## 9. Every save triggers a full rebuild

Early bundler dev loops: edit a file → rebuild the whole bundle → reload the page → lose your app state. Painful for anything non-trivial.

**Why it matters historically:** motivated **watch mode**, then **incremental compilation**, then **Hot Module Replacement** (HMR) — swap a module in a running app without losing state. HMR is one of the killer features of modern dev servers and why Vite/webpack-dev-server feel magical.

**Chat app step:** we're iterating on the message renderer constantly — fixing how code blocks display, tweaking spacing, testing streaming edge cases. Every save → rebuild bundle → reload page → the conversation we were testing evaporates. We start sending the LLM "test" over and over to recreate state. Add a file watcher that rebuilds on save, then an HMR protocol (websocket + module swap) so the renderer reloads without blowing away the conversation in memory.

**Tie to JS:** HMR's value is abstract until you lose your test conversation 40 times in one hour. Then it's obvious.

---

## 10. Cold-start dev servers are slow

Webpack-era dev: start the server, wait 30 seconds while it bundles everything, *then* you can open localhost. For large apps, dev startup became minutes.

**Why it matters historically:** motivated Vite's architectural bet — **don't bundle in dev at all**. Serve native ESM to the browser, let it request modules on demand, only transform what's needed. Dev server starts instantly regardless of app size. This is *the* defining idea of modern JS tooling in the 2020s.

**Chat app step:** the chat app + its deps have grown. Our bundler's cold start now takes several seconds before we can open localhost. Switch dev to a Vite-style model: a tiny Node HTTP server serves each module as a native-ESM response on demand, transforms only on request, no eager bundling. Cold start is near-instant regardless of project size.

**Tie to JS:** Vite's insight: don't do the work until the browser asks for it. Obvious in hindsight, non-obvious for a decade.

---

## 11. JS-in-JS tooling is slow

Babel, webpack, Rollup are all written in JavaScript. Parsing JS in JS, for a large codebase, is inherently slow — you're running an interpreter on an interpreter.

**Why it matters historically:** motivated the native-language rewrites: **esbuild** (Go, ~2020), **SWC** (Rust, ~2019), **Turbopack** (Rust, 2022), **Rolldown** (Rust, 2024). The speedups were 10–100x, enough to reshape what tools people use. Vite uses esbuild in dev and is migrating its prod bundler from Rollup to Rolldown.

**Chat app step:** once we have per-page bundle budgets (pain #8), we iterate constantly — remove this import, add that dynamic chunk, rerun the bundler, recheck sizes. Our zero-dep Node bundler takes 3–5 seconds per rebuild; iteration becomes painful. Swap the bundle step to esbuild and watch it drop to ~100ms. Budget-tuning becomes interactive.

**Tie to JS:** native speed isn't just "faster" — it changes what kinds of work are interactive. At 3s/rebuild you test changes serially; at 100ms you explore combinations. That shift is why esbuild/SWC/Rolldown reshaped the ecosystem.

---

## 12. Errors in transpiled/bundled code are unreadable

Stack trace says `bundle.min.js:1:48372`. The original source was `src/components/Checkout.tsx:42`. You can't debug what you can't read.

**Why it matters historically:** motivated **source maps** — a JSON file that maps positions in the output back to the original source. Every transpiler and bundler generates them. Browsers and Node both consume them. Without source maps, the "transpile everything" ecosystem would be unusable in production.

**Chat app step:** someone reports "the chat crashes when I click the retry button on a failed message" and pastes a screenshot: `Uncaught TypeError at bundle.min.js:1:48372`. Useless. Teach our bundler + transpiler to track `{ file, line, col }` positions from each source file through every transform and into the final bundle. Emit a `.map` file alongside; serve it. The browser's devtools now surface the error at `render.js:43` — the actual bug site.

**Tie to JS:** source maps feel like plumbing until you see them light up. Once errors jump to the right file and line, the group understands why *every* transpiler and bundler in the JS world ships them.

---

## 13. Imperative DOM updates don't scale

jQuery-era code: a click handler reads state from the DOM, computes new state, writes it back to the DOM. With many interacting pieces of state, you get a spaghetti of "if this element changes, remember to update those three other elements." Bugs are inevitable.

**Why it matters historically:** motivated **declarative UI frameworks** — React (2013), Vue (2014), Svelte (2016). The shared idea: you describe what the UI *should look like* given the current state, the framework figures out what DOM operations to perform. This is the single biggest shift in how frontend code is written in the last 15 years.

**Chat app step:** streaming LLM responses push tokens into the current message every ~20ms. Meanwhile: the input box has its own state, the sidebar needs to reflect new conversations, the send button disables during streaming, errors need an overlay, the typing indicator appears/disappears, scroll has to follow new content. Imperative DOM is unmanageable — we keep forgetting one of the updates. We write a ~50-line signals-based reactive runtime (`signal`, `effect`, `derived`) and refactor the UI on top of it. Everything updates coherently because each piece just reads the signals it cares about.

**Tie to JS:** chat UIs are the ideal place to feel this pain — every state change touches three other things. Writing the 50-line signals runtime makes React/Vue/Svelte stop being "frameworks you learn" and start being "solutions to a problem you've had." Those 50 lines are the core of SolidJS.

---

## 14. Node-isms don't run on the edge or in the browser

Node has `fs`, `path`, `process`, `Buffer`, a specific module resolution algorithm, CJS by default. None of this exists in Cloudflare Workers, Deno, or the browser. Code written for Node doesn't port.

**Why it matters historically:** motivated the **Web-Standard APIs** push — runtimes agreeing on `fetch`, `Request`, `Response`, `ReadableStream` as the common vocabulary. Deno (2020) and Bun (2022) both ship Web APIs as first-class. Node has been back-porting them (`fetch` landed in Node 18). This is an active, ongoing realignment.

**Chat app step:** our proxy runs on a VPS — always-on, bills by the hour even when idle, boot time for deploys. Port it to Cloudflare Workers: per-request billing, instant cold start, closer to users. Problems: the proxy uses `fs.readFileSync` to load prompt templates and `http` for server setup — neither exists on Workers. Migrate prompt loading to `fetch` from a Worker KV binding; swap the `http` server for the Worker `fetch` handler signature. Everything else — `Request`, `Response`, `URL`, `Headers`, `fetch` — already works, because Node back-ported them.

**Tie to JS:** every `fs` call you replace is a lesson in why runtimes are converging on web-standard APIs. Also a good moment to discuss why Workers are especially well-suited to LLM proxies (cheap, global, short-lived).

---

## 15. `node_modules` is a disaster

400MB on disk, 30,000+ files, slow to install, slow to traverse, duplicated across every project on your machine. npm's install algorithm was designed in 2010 and the ecosystem has outgrown it.

**Why it matters historically:** motivated **pnpm** (content-addressable store + symlinks — install once globally, symlink into each project), **yarn PnP** (no `node_modules` at all, zip-based resolution), **bun**'s install (parallelism + native speed). This is also where supply-chain concerns live: lockfiles, `npm audit`, package signing discussions.

**Chat app step:** we've accumulated marked, a syntax highlighter (Shiki or highlight.js), a test framework, TypeScript, esbuild, wrangler for Workers, plus dev-side tooling. `du -sh node_modules` is alarming. Migrate to pnpm; show the content-addressable store + symlinked `node_modules` structure; compare install time and disk usage against npm on a clean clone.

**Tie to JS:** hands-on "why does pnpm exist?" demonstration. More of a compare-and-discuss moment than a build step — nothing to construct, just to observe.

---

## 16. CJS and ESM don't interop cleanly

Node supports both. Import a CJS package from an ESM file → sometimes works, sometimes gives you `{ default: actualExport }`, sometimes errors. Libraries that ship both have a "dual-package hazard": two copies of the same module, two separate identities.

**Why it matters historically:** this is *the* reason `package.json` got complicated. `"type"`, `"main"`, `"module"`, `"exports"`, conditional exports, `.mjs` vs `.cjs` — all of it is Node trying to support both module systems without breaking the world. Arguably the biggest open wound in the JS ecosystem in 2026.

**Chat app step:** we extract the core chat-loop logic — message state machine, streaming parser, model abstraction — into a package, `@our-chat/core`. Then we build a second package `@our-chat/plugin-retry` that depends on core and adds retry-on-failure behavior. Ship core as CJS-only → ESM users importing from Vite complain. Ship ESM-only → older build tools break. We configure the `exports` field with conditional entries (`"import"`, `"require"`, `"types"`) and ship both. Hit the dual-package hazard (two instances of core when one caller is CJS and another is ESM) and debug it.

**Tie to JS:** turns the opaque `exports` field into something with a story. Every condition you add answers a specific "what environment is importing me?" question.

---

## 17. Configuration explosion

A modern project has `package.json`, `tsconfig.json`, `vite.config.ts`, `eslint.config.js`, `.prettierrc`, `postcss.config.js`, `.browserslistrc`, `.npmrc`, sometimes more. Each has its own schema, docs, and gotchas. Onboarding a new developer is mostly explaining config.

**Why it matters historically:** motivated **zero-config tools** (Parcel's original pitch) and **opinionated frameworks** (Next.js, Remix, SvelteKit, Astro) that hide the config behind a single `framework.config.js`. The trade is flexibility for velocity — and most teams are taking it.

**Chat app step:** retrospective. Count every config we've accumulated: `package.json`, `tsconfig.json`, bundler config, dev-server config, `.eslintrc`, `.prettierrc`, `wrangler.toml` for the Worker, `pnpm-workspace.yaml` for the packages split in pain #16. Then: try rebuilding the chat app on SvelteKit or Next. Most configs collapse into one `framework.config.js`. Discuss what's gained (velocity, consistency) and lost (flexibility, transparency).

**Tie to JS:** only lands *after* having felt each config's pain. "Frameworks hide this" is powerful because you paid the cost of every layer they're hiding.

---

# How these map to sessions

Probably too many for three 2-hour sessions. A rough grouping:

- **Session 1 — Ship the chat app, feel the module pain:** pains 1, 2, 3, 4, 7. Build chat app v1 (single HTML + script tag, fetch through a Node proxy, maybe streaming). Split into multiple files and feel the globals collision. Install `marked`. Split the proxy across files with CJS. Write the zero-dep Node bundler. End with a multi-file chat app running from one bundled `<script>`.
- **Session 2 — Tooling layer:** pains 5, 6, 8, 9, 10, 11, 12. Transpile step (modern JS → ES5), port to TS, route-level code splitting + tree-shaking against per-page bundle budgets, dev server with HMR, Vite-style dev, swap to esbuild for speed, source maps. Biggest session — probably needs trimming.
- **Session 3 — The modern stack:** pains 13, 14, 15, 16, 17. Build a tiny reactive framework and refactor the UI on top of it, deploy the proxy to Cloudflare Workers, migrate to pnpm, extract + publish core as a dual CJS/ESM package, retrospective on configs.

Open questions:
- Pain 13 (declarative UI / signals) is huge and probably deserves its own session. Could push to a 4th week or leave frameworks as "further reading."
- Session 2 is overloaded. Candidates to lighten: pain 11 can be a ~20min demo (swap bundler step → time it) rather than a full rebuild; pain 8 can focus on the settings-page budget exercise rather than also doing tree-shaking from scratch.
- Streaming (ReadableStream / async iterators) in session 1 is a nice-to-have that could get cut if session 1 runs long.
