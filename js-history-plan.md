
The web has a long history, and there are a lot of design decisions that went into the modern javascript ecosystem. There are also a lot of tools and conventions (many of them overlapping), and it would be great to orient myself on them.

Rather than learning things by just reading "esbuild is X", I'd like to build a toy project, progressively going up the tech stack to understand why tools and language changes occured.

## What we're building

We'll build a toy chat app. A user types messages, an LLM responds. We start as a single HTML file with a `<script>` tag calling a free OpenRouter endpoint and grow into a multi-page web app with markdown-rendered replies, conversation history, and a settings panel — deployed to the edge.

**Feature progression (rough shape, not a rigid plan):**
- v1: one page, one input, messages stacked, request-response (send → wait → display)
- v2: markdown rendering with code blocks, retry on failure, conversation history persisted to localStorage
- v3: conversation list sidebar, settings page, shareable URLs, deployed to Cloudflare

### Architecture

- **Client** — the browser app. Most of our work lives here.
- **Proxy** — a tiny Node server that holds the OpenRouter API key and forwards requests from the browser. Never put the API key in client JS — it leaks to anyone viewing page source. The proxy grows into a real backend (rate limiting, model list, usage tracking) as sessions progress.

### Source conventions

We start writing **plain, old-style JavaScript** — no `let`/`const`, no arrow functions, no modules. ES3/ES5-ish. The one deliberate exception is async code: pain #1 walks through the XHR → Promises → async/await arc up front so everyone sees the history, and from that point on we use async/await everywhere — it's too painful to read deeply-nested callbacks for the whole project. Other modern syntax (let/const, arrows, classes, destructuring) gets introduced later via a transpile step (pain #6).

### Tooling language

All the tools we build (bundler, type-stripper, dev server, source-map generator) are written in **zero-dependency Node**. We deliberately don't shell out to `esbuild` or `webpack` initially — we implement them ourselves in vanilla Node, the same language the real ecosystem is mostly built in. Pain #12 is where we swap our hand-rolled tool for a native one and feel the speedup.

### Stretch / optional

- **Token-level streaming** (ReadableStream / async iterators) as an optional enhancement for LLM responses. Pairs naturally with pain #1 (async) as the "what comes after async/await" beat. Skip unless time allows.
- **Triton-puzzle-style exercises** — concrete before/after perf targets the group races to hit (e.g., "get the settings page under 50KB"). Fit naturally at pains 9, 11, 13, 14.

### Exercise Thoughts: 
- Is there a way we could get people to arrive on the right decision decision on their own? Maybe with some extra help, like reading some primary or secondary sources on the topic?
- I like the puzzle style questions from Sasha Rush's Triton Puzzles. I wonder if there's an analogy to any of the issues here.

---

Pain points below are ordered roughly chronologically.

---

## 1. No first-class async

When JS launched in 1995, pages could do math and move things around — but talking to a server meant a full page reload. Microsoft fixed this in 1999 by shipping `XMLHttpRequest` in IE5 (as an `ActiveXObject`, of all things). Gmail made the pattern famous in 2004; "AJAX" was coined the year after. But the language itself had no native async primitive for another decade: Promises landed in ES2015, async/await in ES2017. That's a **22-year arc** from "there is no async" to "async is readable."

**Why it matters historically:**
Every browser API that waits on something — network, disk, timers, user input, streaming — is async. The callback → Promise → async/await progression is the single most important readability shift in JS's history. It also forced the language to formalize the **event loop** and **microtask queue**, which are the mental model every JS dev needs and the source of most "why didn't my UI update when I expected" bugs.

**Chat app step:**
We need to send a message to the proxy and display the reply. We write the request three ways, chronologically, to feel the arc — then use the modern form for the rest of the project.

1. **XHR with callbacks (1999).** Nested `onload`/`onerror` handlers, no error propagation.
2. **Promises (2015).** Chainable `.then`, errors bubble through `.catch`. Still callback-shaped.
3. **async/await (2017).** Flat, linear, `try/catch` works normally.

```js
// 1. XHR — nesting compounds; two requests means two layers
var xhr = new XMLHttpRequest();
xhr.open('POST', '/chat');
xhr.onload = function () {
  if (xhr.status !== 200) { showError(xhr.statusText); return; }
  var reply = JSON.parse(xhr.responseText);
  render(reply);
};
xhr.onerror = function () { showError('request failed'); };
xhr.send(JSON.stringify({ text: input }));
```

```js
// 2. Promises — flat chain, single .catch
fetch('/chat', { method: 'POST', body: JSON.stringify({ text: input }) })
  .then(function (res) { return res.json(); })
  .then(render)
  .catch(showError);
```

```js
// 3. async/await — looks synchronous, errors via try/catch
async function send(input) {
  try {
    const res = await fetch('/chat', { method: 'POST', body: JSON.stringify({ text: input }) });
    render(await res.json());
  } catch (e) { showError(e); }
}
```

After this section, **we use async/await for all network/async code for the rest of the project**, even while other old-school patterns (`var`, IIFEs, script tags) stick around until pain #6. History is the pedagogy; modern syntax is the daily practice.

### The event loop and microtask queue

JS is single-threaded — one call stack, one thing running at a time. When code `await`s or registers a callback, the function returns; the runtime picks up waiting work when the queue next drains.

Two queues, same event loop:
- **Task queue.** `setTimeout`, I/O callbacks, DOM events. Each task runs to completion before the loop moves on.
- **Microtask queue.** `Promise.then`, `queueMicrotask`, `MutationObserver`. Drained **fully** after every task, before the next task starts.

```js
setTimeout(function () { console.log('timeout'); }, 0);
Promise.resolve().then(function () { console.log('promise'); });
console.log('sync');
// Output order: sync, promise, timeout
```

Microtasks were formalized with Promises (2015) to guarantee `.then` runs before the browser repaints or handles another event. Historically the distinction barely mattered because nothing scheduled microtasks; now it's load-bearing. Common gotcha: a chain of `await`s can starve a paint you were expecting between them — every `.then` is a microtask, and microtasks drain to empty before the browser gets control back.

### Exercises here:
- Read the three implementations side by side. Rewrite each form into the next (XHR → Promise, Promise → async/await) until the translation feels mechanical.
- Flatten a nested callback chain ("send a message → fetch suggestions based on the reply → render both") into async/await. Five levels of indentation collapse to five lines.
- Puzzle: predict the log order for a tangle of `setTimeout(fn, 0)`, `queueMicrotask(fn)`, `Promise.resolve().then(fn)`, and synchronous `console.log`. Run and verify.
- (Optional) A debounced input that fires a request on every keystroke has a race: an older request resolves after a newer one, and stale suggestions render. Fix with an "is-this-the-latest" check or `AbortController`.

### References:
- Jake Archibald, "Tasks, microtasks, queues and schedules" (2015) — the canonical explainer, with animations.
- MDN: "The event loop."
- Deno blog, "A brief history of JavaScript" — has the original IE5 `ActiveXObject` XHR snippet and the Gmail/AJAX timeline.
- Ryan Dahl's original Node.js talk (2009) — the whole pitch is "non-blocking I/O is why Node exists."

---

## 2. Code can't be split across files

Early JS: one `<script>` tag, or several, all sharing one global namespace. Two files both define `handleClick` → one silently overwrites the other. There's no `import`, no `require`, no modules of any kind.

**Why this mattered**: 
Forced the IIFE pattern and "namespace object" pattern as poor-man's modules. Modern module systems grew out of these patterns.
- **IIFE** (Immediately Invoked Function Expression) — `(function(){ ... })()`. A function you define and call in the same expression. Everything declared inside is scoped to the function, not leaked to `window`.
- **Namespace object pattern** — instead of 30 globals (`addMessage`, `renderAll`, `sendToApi`, ...), you make *one* global (`APP`) and hang everything off it: `APP.state.addMessage(...)`, `APP.render.renderAll()`. Poor-man's modules.


**Chat app step:** 
v1 is one `index.html` + one `<script>` tag. 

As we add features — message list rendering, input handling, fetch to the proxy, markdown display — the script crosses 300 lines. We split it into `api.js`, `render.js`, `state.js`, each as its own `<script>` tag. 

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

## 3. No way to reuse other people's code reproducibly

Pre-2010: you wanted jQuery, you downloaded `jquery.min.js` and committed it to your repo. No version numbers, no dependency graph, no way to update. Transitive dependencies were manual.

**Why it matters historically:** 
Motivated npm (2010, originally for Node), later Bower (for browser, now dead), and eventually the idea that a JS project has a *manifest* (`package.json`) and a *lockfile*. Half your `package.json` fields trace back to solving this.

**Chat app step:** 
LLM responses come back as markdown. We want them rendered as real HTML — headings, lists, inline code, code blocks. Writing our own markdown parser is a rabbit hole; we reach for `marked`. Without a package manager we'd download a zip, commit it, pin to whatever version was in the zip, and hope updates don't break us. Instead: `npm init`, `npm install marked`, and a `package.json` + lockfile appear.

`npm install marked` is the moment the manifest-and-lockfile pattern stops feeling like bureaucracy and starts feeling like the only way to say "I depend on marked 9.x" reproducibly.

### Plan (Opus 4.7):

**Feel the pain first (no package manager, just zips):**
Give the group three pre-built libs, zipped, to drop into a `/vendor/` folder and load via `<script>` tags:
- `marked@2.x` — markdown parser
- `sanitize@1.x` — HTML sanitizer that exposes `window.Sanitize`
- `markdown-safe@0.5` — wrapper that calls `marked` then `sanitize`

The trap: `markdown-safe` was written against `marked@1.x` (breaking API change in 2.x). Separately, `marked@2.x` bundles its *own* copy of sanitize at a different version, also assigned to `window.Sanitize`, so whichever script tag loads last clobbers the other. Running the app: markdown kinda renders, code blocks mangle, some links get stripped. No manifest → no way to see the conflict without reading three minified bundles. This is the authentic 2008 pain.

Then we build our package manager and each lib ships with a real manifest declaring its deps and version ranges. Registry serves them. Resolver picks a compatible set. Install lays them out in `node_modules/`. The app `require`s them cleanly.

**Scaffolded (we write upfront so students don't get stuck on plumbing):**
- `registry/` — a local directory of `{name}/{version}/package.json` + source files. No tarballs, no network.
- `manifest.js` — read/write a project's `package.json` dependencies.
- `install.js` — given a resolved tree, write files into `node_modules/`.
- `semver.js` — stub signature `satisfies(version, range)`, empty body.
- `resolve.js` — stub signature `resolve(rootManifest) → tree`, empty body.

Loading is just Node's real `require` — no need to reimplement module resolution here.

**Students fill in:**
- `semver.satisfies` — capped at `MAJOR.MINOR.PATCH` + `^` / `~` / exact. Full spec (prereleases, build metadata) is a swamp and not the lesson.
- Dep graph construction — recursive walk across manifests.
- Resolver — backtracking search over candidate versions.

**Pseudocode: graph building**

```
function buildConstraintGraph(rootManifest):
  constraints = {}   # { packageName: [ (requiredBy, range), ... ] }
  queue = [rootManifest]
  seen = set()
  while queue not empty:
    manifest = queue.pop()
    for (depName, range) in manifest.dependencies:
      constraints[depName].append((manifest.name, range))
      for version in registry.versionsOf(depName):
        if satisfies(version, range) and (depName, version) not in seen:
          seen.add((depName, version))
          queue.push(registry.manifestFor(depName, version))
  return constraints
```

**Pseudocode: backtracking resolver**

```
function resolve(rootManifest):
  constraints = buildConstraintGraph(rootManifest)
  return backtrack({}, list(constraints.keys()), constraints)

function backtrack(chosen, remaining, constraints):
  if remaining is empty:
    return chosen
  name = remaining[0]
  candidates = registry.versionsOf(name)
               .filter(v => all(satisfies(v, r) for (_, r) in constraints[name]))
               .sortedDescending()
  for candidate in candidates:
    newConstraints = mergeDepsOf(constraints, name, candidate)
    if consistent(newConstraints):   # no range intersects to empty
      result = backtrack(chosen | {name: candidate}, remaining[1:], newConstraints)
      if result: return result
  return None   # conflict, signal backtrack to caller
```

Most of the time highest-matching succeeds on the first try; backtracking only kicks in when a later package narrows an earlier one. That's the pedagogical moment: "see how picking marked@2.x forced us to back up and pick markdown-safe@0.3 instead of @0.5?"

**Designing the fake package set — three flavors to cover:**
1. *Happy path:* `app → marked@^1`. Trivial, warms up the pipeline.
2. *Diamond:* two deps both want `core@^1` → dedupe to one copy.
3. *Conflict requiring backtrack:* `app → a@^1, b@^1`; `a@1.5 → core@^2`, `b@1.2 → core@^1`. Resolver picks `a@1.5` first, hits conflict on `core`, backtracks to `a@1.4` which wants `core@^1`, succeeds.

### Integrating with the chat app (Opus 4.7):

Our package manager writes `node_modules/`, but the browser can't `require` from there — that's pain #5. For now we lean on the convention of the era: each browser lib in our registry ships a `dist/<name>.js` that's an IIFE attaching to a global (marked → `window.marked`, sanitize → `window.Sanitize`). That's what UMD was designed for; our toy versions can be IIFE-only.

After `our-npm install marked sanitize`:

```
node_modules/
  marked/dist/marked.js       ← IIFE, assigns window.marked
  sanitize/dist/sanitize.js   ← IIFE, assigns window.Sanitize
```

`index.html` hand-includes them in topological order, before our code:

```html
<!-- deps first, in topological order -->
<script src="node_modules/sanitize/dist/sanitize.js"></script>
<script src="node_modules/marked/dist/marked.js"></script>

<!-- our namespace + our code -->
<script>window.APP = {};</script>
<script src="state.js"></script>
<script src="render.js"></script>
```

The IIFEs from section 2 just read the new globals:

```js
// render.js
(function () {
  var messagesEl = document.getElementById('messages');

  function renderAll() {
    var list = window.APP.state.getMessages();
    messagesEl.innerHTML = list.map(function (m) {
      var html = window.marked.parse(m.text);       // lib 1
      var safe = window.Sanitize.clean(html);       // lib 2
      return '<div>' + m.role + ': ' + safe + '</div>';
    }).join('');
  }

  window.APP.render = { renderAll: renderAll };
})();
```

**The unsatisfying parts — and that's the point:**
- We hand-write `<script>` load order for every transitive dep. (Stretch: have our package manager emit a `scripts.txt` in topological order — poor-man's bundler output, which is what Grunt/Gulp concat plugins did in 2012.)
- Every lib adds another global to `window`; collisions are still possible.
- The browser makes N requests — one per dep — paying a round-trip each (pain #8).
- We still can't `require('./sibling')` between our *own* files; internally we're stuck with the namespace pattern.

Server side is a different story: the Node proxy `require`s straight from `node_modules/` via Node's built-in resolution, no bundler needed. That contrast — *server-side modules are easy, client-side isn't* — is the setup for pains #4 and #5.

**LSP note:** tsserver handles the syntax (old-style JS is still JS), but cross-file `window.APP.state.addMessage` won't autocomplete without a small `globals.d.ts` declaring `interface Window { APP: { state: ...; render: ... } }`, or JSDoc annotations on each IIFE's published object. Third-party libs are similar — `@types/marked` declares both the module export and the global, so `window.marked` autocompletes once types are installed. The module-less world doesn't give editors enough structure to help much; another authentic pain, and a natural setup for why pain #7 (TypeScript) pairs with pain #4 (modules).

### References:
- **PubGrub** — Natalie Weizenbaum, "PubGrub: Next-Generation Version Solving". The algorithm behind Dart's pub, Python's uv, and Poetry. Better error messages than naive backtracking because it records which constraints conflicted. 
  - https://nex3.medium.com/pubgrub-2fb6470504f
- **Cargo** — Rust's package manager, readable resolver source in `src/cargo/core/resolver/`.
- **uv** (Astral, Rust) — Python package manager, uses PubGrub. Extensive design docs in-repo.
  - "How UV got so fast" 
    - https://news.ycombinator.com/item?id=46393992
    - https://nesbitt.io/2025/12/26/how-uv-got-so-fast.html
- **npm** — greedy heuristics, not a real solver. Hence duplicate installs and hoisting quirks. Good contrast to the solver-based world.

### Caden Todos here: 
- work w claude to impl the plan here

### Exercises: 
- Skim PubGrub. Maybe check how approachable it is first, though.
- Implement dependency graph building, backtracking solving

---

## 4. Server-side JS needs real modules

Node (2009) wanted to write non-trivial server programs. Globals-and-script-tags doesn't fly when you have a 50-file backend. Node adopted **CommonJS**: `const x = require('./foo')`, synchronous, runtime-resolved, filesystem-based.

**Why it matters historically:** CJS became the lingua franca of server JS for a decade. Every npm package shipped CJS. The entire ecosystem's "default" was CJS until ESM started winning around 2020 — and we're still cleaning up the mess.

**Chat app step:** the proxy was one `server.js`. It grows — routes for chat completion, model list, usage stats; middleware for rate limiting and logging. We split it across `server.js`, `routes/chat.js`, `routes/models.js`, `middleware/ratelimit.js`, each with `require('./routes/chat')` etc. But rather than just using Node's built-in `require`, we **build our own** first — then use ours to load the split proxy.

### Plan: toy CJS loader (Opus 4.7)

CJS's runtime mechanism is genuinely ~30 lines. The full loader with resolution is ~100. We build both, in two phases.

**Phase 1 — the mechanism (~30 lines).** Given an absolute path, load and run a module:

```
function require(absPath):
  if cache[absPath]: return cache[absPath].exports
  source = readFileSync(absPath)
  module = { exports: {} }
  cache[absPath] = module                 # cache BEFORE running — supports circular deps
  wrapped = `(function (module, exports, require, __filename, __dirname) {
    ${source}
  })`
  fn = eval(wrapped)                      # or new Function(...) — avoids outer-scope leak
  fn(module, module.exports, scopedRequire(absPath), absPath, dirname(absPath))
  return module.exports
```

`scopedRequire(callerPath)` returns a function that resolves relative specifiers against `callerPath`'s directory — so `require('./foo')` inside `routes/chat.js` means `routes/foo.js`.

**Phase 2 — resolution (~60 lines).** Given a specifier string and the caller's directory, find the absolute file path:

```
function resolve(spec, callerDir):
  if spec starts with "./" or "../":
    base = join(callerDir, spec)
    try: base, base + ".js", base + "/index.js", base + "/package.json".main
  else:
    # bare specifier: walk up looking in node_modules
    dir = callerDir
    while dir != "/":
      candidate = join(dir, "node_modules", spec)
      try: candidate, candidate + ".js", candidate + "/index.js", candidate/package.json".main
      dir = parent(dir)
  throw "Cannot find module " + spec
```

**What this reveals:**
- Why `require.cache` exists and why circular deps return *partially-initialized* exports — you hand back `module.exports` at the moment of re-entry, before the callee finishes. Classic CJS gotcha.
- Why `module.exports = x` and `exports = x` differ. `exports` is just a local parameter pointing at `module.exports`; rebinding the parameter doesn't change the module object.
- Why every Node file has `__filename`, `__dirname`, `module`, `exports`, `require` without importing anything: they're the wrapper function's parameters.
- Why Node's module system is synchronous and filesystem-bound — which is exactly the thing that breaks in the browser and forces bundlers (pain #5).

**Exercises:**
- Implement phase 1 against hand-rolled absolute paths. Get the chat proxy split and loading with your own `require`.
- Implement phase 2. Now `require('marked')` from the proxy walks up to `node_modules/marked/package.json` and loads its `main`.
- Puzzle: write two files that `require` each other and print intermediate `module.exports`. Predict and verify what each side sees.
- Stretch: support `.json` (parse instead of eval) and a third-party `.node` addon noop.

### References:
- Node.js docs, "Modules: CommonJS modules" — the spec in plain English.
- [`require` source in Node](https://github.com/nodejs/node/blob/main/lib/internal/modules/cjs/loader.js) — 2000+ lines, but the core mechanism is recognizable.
- Ryan Dahl, "10 things I regret about Node" (2018) — item #7 is about module resolution. Good "here's why this design is regretted now" counterpoint.

**Tie to JS:** the Node / CJS origin story verbatim, with enough internals that CJS stops being a black box. Because we're building a server and a client at the same time, the contrast with pain #5 is vivid: the exact loader we just wrote *cannot* run in the browser — `readFileSync` doesn't exist, and even async `fetch` can't be used synchronously inside `require(...)` evaluation. That impossibility is what bundlers fix.

### Caden Todos here: 

---

## 5. Browser can't do synchronous `require`

CJS assumes you can block on a local filesystem read. Browsers can't — fetching a module over the network is async. You can't evaluate `require('./foo')` inline because `foo` hasn't arrived yet.

**Why it matters historically:** motivated AMD (`define([...deps], factory)`) as an async alternative, UMD as the "works in both" wrapper, and — critically — **bundlers** as a workaround: pre-compile the whole dep graph into a single file so the browser never has to do runtime resolution. Browserify (2011) and webpack (2012) were born here.

**Chat app step:** we love how the proxy splits across files. We want the same on the client — `require('./render')`, `require('./api')`. The browser can't do `require`. We write a ~150-line zero-dep Node bundler and ship the chat app as one bundled `<script>`.

### Plan: toy bundler, Browserify-shaped (Opus 4.7)

The key insight: do pain #4's resolution work *at build time*, not at runtime. The runtime in the browser is then tiny — basically pain #4's loader minus the filesystem.

Historical framing: this is **Browserify circa 2011** — the first bundler. Webpack (2012) added loaders (CSS, images), a plugin system, and sophisticated code-splitting, and became dominant by ~2016 with React/CRA. Our toy grows webpack-shaped as we extend it in pain #10 (HMR) and pain #9 (code splitting).

**Pipeline (~150 lines, vanilla Node):**

```
function bundle(entryPath):
  modules = {}          # { id: { absPath, code, deps: { spec: id } } }
  byPath = {}           # { absPath: id } — dedupe
  nextId = 0
  queue = [entryPath]
  while queue not empty:
    abs = queue.pop()
    if abs in byPath: continue
    id = nextId++
    byPath[abs] = id
    source = readFileSync(abs)
    deps = {}
    for spec in findRequireCalls(source):       # regex for v1, AST for v2
      depAbs = resolve(spec, dirname(abs))      # reuse pain #4's resolver
      queue.push(depAbs)
      deps[spec] = byPath[depAbs] ?? "pending"  # fix up after queue drains
    modules[id] = { absPath: abs, code: source, deps }
  fixUpPendingIds(modules, byPath)
  return emit(modules, byPath[entryPath])

function emit(modules, entryId):
  # rewrite each module: require("./foo") → require(3)
  for each module in modules:
    module.code = replaceRequireSpecsWithIds(module.code, module.deps)
  return `${runtime}
    const modules = ${serializeModuleTable(modules)};
    require(${entryId});`
```

**The runtime (~15 lines, ships in the bundle):**

```js
(function () {
  var cache = {};
  function require(id) {
    if (cache[id]) return cache[id].exports;
    var module = { exports: {} };
    cache[id] = module;
    modules[id](module, module.exports, require);
    return module.exports;
  }
})();
```

Compare to pain #4's loader: identical shape, except `modules[id]` is a table baked into the bundle instead of a file read off disk. Bundling is just CJS-at-build-time.

**What this reveals:**
- Every bundler output has "module IDs" — they're the artifact of baking resolution into the bundle.
- Why bundling survived ESM shipping natively (pain #8): still one request vs. N.
- Why tree-shaking is hard with CJS (pain #9): `require(x)` where `x` is dynamic can't be statically known. ESM's static `import` structure is the fix.
- Why the bundle's runtime is tiny compared to the build logic — the hard work is the graph walk, the runtime is just a lookup table.

**Exercises:**
- Implement the regex-based version. Bundle a three-file chat client, ship as one `<script>`.
- Hit the regex's limits: a `require` inside a string literal or comment gets matched. Swap to Acorn-based detection of actual `CallExpression` nodes named `require`.
- Puzzle: two modules that `require` each other (circular dep). What does the browser runtime return? Verify it matches the Node-CJS behavior from pain #4.
- Stretch: add a sourcemap emit (just enough to map bundle lines back to source file + line). Pain #13 generalizes this.

### References:
- [Browserify source](https://github.com/browserify/browserify) — the original, ~1k lines for the core.
- James Halliday's [browserify handbook](https://github.com/browserify/browserify-handbook) (2014) — the design philosophy.
- [minipack](https://github.com/ronami/minipack) — an existing ~200-line educational bundler. Good to read after writing your own.
- Webpack's [concepts docs](https://webpack.js.org/concepts/) — see what our toy is *missing* (loaders, plugins, chunks).

**Tie to JS:** Browserify in miniature. Building it ourselves makes bundlers feel like a *natural* solution rather than a mysterious config layer — they exist because the browser can't do what Node can. And once you've written one, webpack stops being magic: it's the same core graph walk + module table, with a loader pipeline bolted on top.

---

## 6. Browsers don't implement new JS fast enough

ES6 (2015) shipped classes, arrow functions, `let`/`const`, destructuring. Developers wanted to use them *immediately*. IE11 and older browsers didn't support them and wouldn't for years.

**Why it matters historically:** motivated **transpilers**. Babel (2014, originally "6to5") compiled ES6 → ES5 so you could write modern code and ship it everywhere. This established the pattern that the JS you *write* is not the JS that *runs*. Every tool downstream (TypeScript, JSX, Svelte compilation) inherits this pattern.

**Chat app step:** we've been writing `var` everywhere, IIFEs, no arrow functions (async/await is the one thing we kept modern, per pain #1). Tiring. We want the full modern toolkit — `let`/`const`, arrows, classes, template strings, destructuring. We add a **transpile step** to our pipeline: write modern source → our tool rewrites to ES5 → bundler concatenates → ship.

### Plan: toy transpiler (Opus 4.7)

**Infrastructure — use Acorn.** Acorn is the JS parser Babel and Rollup use; zero deps, single npm install, produces ESTree AST. For printing back, either use `astring` (tiny printer) or keep source positions and do string splicing (faster, preserves formatting). V1: print with astring. V2: splice in place.

**Pipeline:** parse → walk the AST → rewrite certain node types → print. That's the whole architecture. Every transpiler in the ecosystem (Babel, SWC, esbuild, tsc) is a variation of this.

**Three transforms, hardest-last:**

**(1) TS type stripping (~50 lines).** Use `acorn-typescript` (or `@babel/parser`). Walk the AST, delete every `TypeAnnotation`, `TSInterfaceDeclaration`, `TSTypeAliasDeclaration`, `TSAsExpression`, `ImportDeclaration` with `importKind: "type"`, etc. Print what's left. This is exactly what [`ts-blank-space`](https://github.com/bloomberg/ts-blank-space) (Bloomberg, 2024) does in ~700 lines — our toy is the 50-line version. This transform alone gets us TS support for pain #7.

**(2) Arrow fn → function expression (~40 lines).** The interesting `this`-binding case.

```js
// input
const add = (x) => x + this.y;

// naive (wrong): `this` inside the function is the new function's this
const add = function (x) { return x + this.y; };

// correct: capture `this` in an enclosing scope, reference the capture
var _this = this;
var add = function (x) { return x + _this.y; };
```

The transform: walk the AST, find `ArrowFunctionExpression`, convert to `FunctionExpression`. If the body references `this`, insert a `var _this = this` at the nearest enclosing non-arrow scope and rewrite every `this` inside the arrow to `_this`. This is what Babel does (with uniquer names). Great `this`-binding lesson falls out of doing the transform.

**(3) async/await → generator + Promise state machine (~80 lines, optional stretch).** The crown jewel — the single most instructive transform in the ecosystem.

```js
// input
async function f() {
  const x = await g();
  return x + 1;
}

// output (roughly)
function f() {
  return runGenerator(function* () {
    const x = yield g();
    return x + 1;
  });
}

function runGenerator(gen) {
  return new Promise(function (resolve, reject) {
    var it = gen();
    function step(value) {
      var result;
      try { result = it.next(value); } catch (e) { reject(e); return; }
      if (result.done) { resolve(result.value); return; }
      Promise.resolve(result.value).then(step, reject);
    }
    step();
  });
}
```

Every `await` becomes a `yield`. The runner pumps the generator: call `next()`, get a promise, wait for it, resume with the resolved value. This is what Babel did for years (2015-2017) before browsers shipped async/await. Transform logic: walk the AST, find `async function`, convert to generator, wrap body in `runGenerator(function* () { ... })`, rewrite every `AwaitExpression` to `YieldExpression`. After writing this, you deeply understand what async/await *is*.

**Recommended path:**
- Do (1) first — practical, short, directly supports pain #7 (TS).
- Do (2) second — teaches transform mechanics + `this`-binding.
- Do (3) as a stretch puzzle — challenging but the most rewarding.

Later: pipe through `esbuild --target=es5` for full coverage of the long tail (destructuring, spread, class fields, etc.) we don't want to hand-write.

**What this reveals:**
- Transpilers are three stages: parse → transform → print. Same as any compiler.
- Why TS is strip-only and deliberately unsound (pain #7): the transform is trivial, and runtime behavior is unchanged — deletion can't introduce bugs.
- Why async/await isn't "just sugar" over Promises — the transform uses generators under the hood, which are themselves non-trivial. Real language-level support buys you efficiency the transpile-down version can't match.
- Why source maps (pain #13) are essential once you have transforms — output positions don't match input positions anymore.

**Exercises:**
- Type-stripping pass. Run it on a TS-flavored version of the chat app; verify the output still executes.
- Arrow transform. Include a `this`-inside-arrow test case; if yours prints `function () { return this.y }` you have the footgun demo for free.
- Puzzle: given a deeply-nested arrow that references `this` and its enclosing function is *also* an arrow, how does your transform walk the scope chain? Write a test case. (Babel handles this correctly; early transforms didn't.)
- Stretch: async/await → generator transform. Verify with an await chain + a try/catch around an awaited rejection.

### References:
- [Acorn](https://github.com/acornjs/acorn) — the parser. Single-file, zero-dep.
- [astring](https://github.com/davidbonnet/astring) — AST printer, ~1k lines.
- [`ts-blank-space`](https://github.com/bloomberg/ts-blank-space) — Bloomberg's ~700-line TS stripper. Good to read after writing yours.
- [AST Explorer](https://astexplorer.net) — paste JS, see the AST. Essential for visualizing what you're walking.
- Babel's [plugin handbook](https://github.com/jamiebuilds/babel-handbook/blob/master/translations/en/plugin-handbook.md) — if you want to see how real transforms are structured.
- [Regenerator](https://github.com/facebook/regenerator) — Facebook's async/generator transform. What real async→generator looked like in production.

**Tie to JS:** Babel's exact origin story, told with our tooling. Writing even one transform makes transpilers stop feeling like magic. Writing the async/await one makes *language features themselves* stop feeling like magic.

---

## 7. JS's dynamic typing hurts at scale

Large codebases: refactors break silently, IDE autocomplete is guessing, `undefined is not a function` at runtime. Tolerable at 1k LoC, miserable at 500k.

**Why it matters historically:** Facebook tried Flow (2014), Microsoft built TypeScript (2012, took off ~2016). TS won by being *gradual* and *deliberately unsound* — pragmatism over correctness. The decision to make TS strip-only (types are erased, not enforced at runtime) shaped how every transpiler since treats types.

**Chat app step:** message shapes have gotten complicated — `{ role, content, tokens, error, retryCount, timestamp, citations, ... }`. A refactor renames `content` to `text` along one code path and the renderer silently breaks — messages stop showing up, no error, just a blank message list. We port the app + tooling to TypeScript. Types are stripped at build; runtime is unchanged. The next refactor fails at edit time instead of at 2am during a demo.

**Tie to JS:** mirrors the TS origin story: types bolted onto a dynamic language *after the fact*, stripped at compile time, gradual adoption. The chat app becomes exactly the sort of codebase TS was designed for — lots of interacting data shapes, async edges, easy places to silently mis-wire.

---

## 8. Sending 400 files to the browser is slow

HTTP/1.1 limits concurrent requests. Each request has overhead. A naive "one file per module" browser loader means a waterfall of hundreds of requests before your app boots.

**Why it matters historically:** the practical argument for bundlers. Even after async module loading was possible (AMD, then native ESM), bundling stuck around because one request for a concatenated file beats a hundred requests for tiny files. HTTP/2 multiplexing weakened this argument but didn't kill it.

**Chat app step:** try shipping the chat app using native `<script type="module">` + `import`. It works — but the network tab shows a cascading waterfall of requests as the browser resolves the import chain through marked, our modules, and their transitive deps. We re-enable the bundler and the app loads in one round trip.

**Tie to JS:** bundlers aren't just a module-system hack — they're a performance tool, independent of whether the browser supports modules natively. Why bundling survived ESM shipping.

---

## 9. Bundle sizes are huge

Naive bundling means visiting `/login` downloads your entire app including the admin dashboard and the checkout flow. Users on slow networks suffer.

**Why it matters historically:** motivated **tree-shaking** (drop unused exports — relies on ESM's static structure, which is a big reason ESM was designed to be static), **code-splitting** (lazy chunks loaded on demand), and **dynamic import** (`import()`). This is why Rollup pushed ESM-first: CJS can't be tree-shaken reliably because `require` is dynamic.

**Chat app step:** we add a Settings page (model picker, theme, API-key management, usage history). Our naive bundler produces one monolithic bundle that includes the settings form libs, a color picker, and the admin tools on *every* page — including the main chat route. Set budgets: chat page < 150KB, settings page < 50KB. We miss. Add (a) route-level code splitting — settings becomes a lazy chunk loaded on navigation — (b) tree-shaking, which requires switching import parsing to ESM's static `import`/`export` form so we can tell what's unused, and (c) a minification pass (identifier mangling + whitespace stripping) — and notice the failure modes of minification: code that reads `Function.prototype.name`, accesses properties by stringly-built keys, or relies on implicit globals all break quietly. Hit the budget.

**Tie to JS:** exactly why Rollup/ESM pushed static imports — you can't tree-shake our CJS bundler output because `require` is dynamic; you need ESM's static structure. A language-design decision with concrete downstream consequences. Minification adds a second teaching moment: "your code is valid JS, the output is valid JS, but they behave differently" → motivates source maps (pain #13).

**Exercise idea (Triton-puzzle style):** "The settings page is 180KB. Get it under 50KB without removing features." Group races, measures with their own bundler output, iterates.

---

## 10. Every save triggers a full rebuild

Early bundler dev loops: edit a file → rebuild the whole bundle → reload the page → lose your app state. Painful for anything non-trivial.

**Why it matters historically:** motivated **watch mode**, then **incremental compilation**, then **Hot Module Replacement** (HMR) — swap a module in a running app without losing state. HMR is one of the killer features of modern dev servers and why Vite/webpack-dev-server feel magical.

**Chat app step:** we're iterating on the message renderer constantly — fixing how code blocks display, tweaking spacing, testing edge cases. Every save → rebuild bundle → reload page → the conversation we were testing evaporates. We start sending the LLM "test" over and over to recreate state. Add a file watcher that rebuilds on save, then an HMR protocol (websocket + module swap) so the renderer reloads without blowing away the conversation in memory.

**Tie to JS:** HMR's value is abstract until you lose your test conversation 40 times in one hour. Then it's obvious.

---

## 11. Cold-start dev servers are slow

Webpack-era dev: start the server, wait 30 seconds while it bundles everything, *then* you can open localhost. For large apps, dev startup became minutes.

**Why it matters historically:** motivated Vite's architectural bet — **don't bundle in dev at all**. Serve native ESM to the browser, let it request modules on demand, only transform what's needed. Dev server starts instantly regardless of app size. This is *the* defining idea of modern JS tooling in the 2020s.

**Chat app step:** the chat app + its deps have grown. Our bundler's cold start now takes several seconds before we can open localhost. Switch dev to a Vite-style model: a tiny Node HTTP server serves each module as a native-ESM response on demand, transforms only on request, no eager bundling. Cold start is near-instant regardless of project size.

**Tie to JS:** Vite's insight: don't do the work until the browser asks for it. Obvious in hindsight, non-obvious for a decade.

---

## 12. JS-in-JS tooling is slow

Babel, webpack, Rollup are all written in JavaScript. Parsing JS in JS, for a large codebase, is inherently slow — you're running an interpreter on an interpreter.

**Why it matters historically:** motivated the native-language rewrites: **esbuild** (Go, ~2020), **SWC** (Rust, ~2019), **Turbopack** (Rust, 2022), **Rolldown** (Rust, 2024). The speedups were 10–100x, enough to reshape what tools people use. Vite uses esbuild in dev and is migrating its prod bundler from Rollup to Rolldown.

**Chat app step:** once we have per-page bundle budgets (pain #9), we iterate constantly — remove this import, add that dynamic chunk, rerun the bundler, recheck sizes. Our zero-dep Node bundler takes 3–5 seconds per rebuild; iteration becomes painful. Swap the bundle step to esbuild and watch it drop to ~100ms. Budget-tuning becomes interactive.

**Tie to JS:** native speed isn't just "faster" — it changes what kinds of work are interactive. At 3s/rebuild you test changes serially; at 100ms you explore combinations. That shift is why esbuild/SWC/Rolldown reshaped the ecosystem.

---

## 13. Errors in transpiled/bundled code are unreadable

Stack trace says `bundle.min.js:1:48372`. The original source was `src/components/Checkout.tsx:42`. You can't debug what you can't read.

**Why it matters historically:** motivated **source maps** — a JSON file that maps positions in the output back to the original source. Every transpiler and bundler generates them. Browsers and Node both consume them. Without source maps, the "transpile everything" ecosystem would be unusable in production.

**Chat app step:** someone reports "the chat crashes when I click the retry button on a failed message" and pastes a screenshot: `Uncaught TypeError at bundle.min.js:1:48372`. Useless. Teach our bundler + transpiler to track `{ file, line, col }` positions from each source file through every transform and into the final bundle. Emit a `.map` file alongside; serve it. The browser's devtools now surface the error at `render.js:43` — the actual bug site.

**Tie to JS:** source maps feel like plumbing until you see them light up. Once errors jump to the right file and line, the group understands why *every* transpiler and bundler in the JS world ships them.

---

## 14. Imperative DOM updates don't scale

jQuery-era code: a click handler reads state from the DOM, computes new state, writes it back to the DOM. With many interacting pieces of state, you get a spaghetti of "if this element changes, remember to update those three other elements." Bugs are inevitable.

**Why it matters historically:** motivated **declarative UI frameworks** — React (2013), Vue (2014), Svelte (2016). The shared idea: you describe what the UI *should look like* given the current state, the framework figures out what DOM operations to perform. This is the single biggest shift in how frontend code is written in the last 15 years.

**Chat app step:** a single message send has to coordinate many pieces of UI. The send button disables while the request is in flight. The input clears optimistically. The user's message appears immediately with a "sending" marker. If the request fails, an error overlay shows and the message gets a retry button. The sidebar updates with a new conversation title. Scroll follows the latest message. Meanwhile the settings pane, model picker, and theme toggle have their own state. Imperative DOM is unmanageable — we keep forgetting one of the updates. We write a ~50-line signals-based reactive runtime (`signal`, `effect`, `derived`) and refactor the UI on top of it. Everything updates coherently because each piece just reads the signals it cares about.

**Tie to JS:** chat UIs are the ideal place to feel this pain — every state change touches three other things. Writing the 50-line signals runtime makes React/Vue/Svelte stop being "frameworks you learn" and start being "solutions to a problem you've had." Those 50 lines are the core of SolidJS.

**V8 puzzle (optional, discoverable):** the naive signals impl we wrote is ~10x slower than it should be. Target: 5x speedup. Give them `node --trace-deopt` — the output literally says "wrong map" when a hidden class changes on a hot path. `node --allow-natives-syntax` + `%DebugPrint(node)` shows the map pointer directly. The planted bug: `createNode` adds a `.computed` field conditionally, so two hidden classes feed the same `updateNode` call site — the fix is initializing `.computed = null` up front so the shape is stable from birth. Students end up reading a real V8 deopt trace instead of being told "trust me, hidden classes matter."

---

## 15. Node-isms don't run on the edge or in the browser

Node has `fs`, `path`, `process`, `Buffer`, a specific module resolution algorithm, CJS by default. None of this exists in Cloudflare Workers, Deno, or the browser. Code written for Node doesn't port.

**Why it matters historically:** motivated the **Web-Standard APIs** push — runtimes agreeing on `fetch`, `Request`, `Response`, `ReadableStream` as the common vocabulary. Deno (2020) and Bun (2022) both ship Web APIs as first-class. Node has been back-porting them (`fetch` landed in Node 18). This is an active, ongoing realignment.

**Chat app step:** our proxy runs on a VPS — always-on, bills by the hour even when idle, boot time for deploys. Port it to Cloudflare Workers: per-request billing, instant cold start, closer to users. Problems: the proxy uses `fs.readFileSync` to load prompt templates and `http` for server setup — neither exists on Workers. Migrate prompt loading to `fetch` from a Worker KV binding; swap the `http` server for the Worker `fetch` handler signature. Everything else — `Request`, `Response`, `URL`, `Headers`, `fetch` — already works, because Node back-ported them.

**Tie to JS:** every `fs` call you replace is a lesson in why runtimes are converging on web-standard APIs. Also a good moment to discuss why Workers are especially well-suited to LLM proxies (cheap, global, short-lived).

---

## 16. `node_modules` is a disaster

400MB on disk, 30,000+ files, slow to install, slow to traverse, duplicated across every project on your machine. npm's install algorithm was designed in 2010 and the ecosystem has outgrown it.

**Why it matters historically:** motivated **pnpm** (content-addressable store + symlinks — install once globally, symlink into each project), **yarn PnP** (no `node_modules` at all, zip-based resolution), **bun**'s install (parallelism + native speed). This is also where supply-chain concerns live: lockfiles, `npm audit`, package signing discussions (left-pad, 2016, is the canonical anecdote).

**Chat app step:** we've accumulated marked, a syntax highlighter (Shiki or highlight.js), a test framework, TypeScript, esbuild, wrangler for Workers, plus dev-side tooling. `du -sh node_modules` is alarming. Migrate to pnpm; show the content-addressable store + symlinked `node_modules` structure; compare install time and disk usage against npm on a clean clone.

**Tie to JS:** hands-on "why does pnpm exist?" demonstration. More of a compare-and-discuss moment than a build step — nothing to construct, just to observe.

---

## 17. CJS and ESM don't interop cleanly

Node supports both. Import a CJS package from an ESM file → sometimes works, sometimes gives you `{ default: actualExport }`, sometimes errors. Libraries that ship both have a "dual-package hazard": two copies of the same module, two separate identities.

**Why it matters historically:** this is *the* reason `package.json` got complicated. `"type"`, `"main"`, `"module"`, `"exports"`, conditional exports, `.mjs` vs `.cjs` — all of it is Node trying to support both module systems without breaking the world. Arguably the biggest open wound in the JS ecosystem in 2026.

**Chat app step:** we extract the core chat-loop logic — message state machine, model abstraction, retry policy — into a package, `@our-chat/core`. Then we build a second package `@our-chat/plugin-retry` that depends on core and adds retry-on-failure behavior. Ship core as CJS-only → ESM users importing from Vite complain. Ship ESM-only → older build tools break. We configure the `exports` field with conditional entries (`"import"`, `"require"`, `"types"`) and ship both. Hit the dual-package hazard (two instances of core when one caller is CJS and another is ESM) and debug it.

**Tie to JS:** turns the opaque `exports` field into something with a story. Every condition you add answers a specific "what environment is importing me?" question.

---

## 18. Configuration explosion

A modern project has `package.json`, `tsconfig.json`, `vite.config.ts`, `eslint.config.js`, `.prettierrc`, `postcss.config.js`, `.browserslistrc`, `.npmrc`, sometimes more. Each has its own schema, docs, and gotchas. Onboarding a new developer is mostly explaining config.

**Why it matters historically:** motivated **zero-config tools** (Parcel's original pitch) and **opinionated frameworks** (Next.js, Remix, SvelteKit, Astro) that hide the config behind a single `framework.config.js`. The trade is flexibility for velocity — and most teams are taking it.

**Chat app step:** retrospective. Count every config we've accumulated: `package.json`, `tsconfig.json`, bundler config, dev-server config, `.eslintrc`, `.prettierrc`, `wrangler.toml` for the Worker, `pnpm-workspace.yaml` for the packages split in pain #17. Then: try rebuilding the chat app on SvelteKit or Next. Most configs collapse into one `framework.config.js`. Discuss what's gained (velocity, consistency) and lost (flexibility, transparency).

**Tie to JS:** only lands *after* having felt each config's pain. "Frameworks hide this" is powerful because you paid the cost of every layer they're hiding.

---

# How these map to sessions

Probably too many for three 2-hour sessions. A rough grouping:

- **Session 1 — Async, ship the chat app, feel the module pain:** pains 1, 2, 3, 4, 5, 8. Walk the XHR → Promises → async/await arc + event loop. Build chat app v1 (single HTML + script tag, async/await fetch through a Node proxy). Split into multiple files and feel the globals collision. Install `marked` (via our toy package manager). Split the proxy across files with CJS. Write the zero-dep Node bundler. End with a multi-file chat app running from one bundled `<script>`.
- **Session 2 — Tooling layer:** pains 6, 7, 9, 10, 11, 12, 13. Transpile step (modern JS → ES5), port to TS, route-level code splitting + tree-shaking + minification against per-page bundle budgets, dev server with HMR, Vite-style dev, swap to esbuild for speed, source maps. Biggest session — probably needs trimming.
- **Session 3 — The modern stack:** pains 14, 15, 16, 17, 18. Build a tiny reactive framework (+ optional V8 puzzle) and refactor the UI on top of it, deploy the proxy to Cloudflare Workers, migrate to pnpm, extract + publish core as a dual CJS/ESM package, retrospective on configs.

Open questions:
- Pain 14 (declarative UI / signals) is huge and probably deserves its own session. Could push to a 4th week or leave frameworks as "further reading."
- Session 2 is overloaded. Candidates to lighten: pain 12 can be a ~20min demo (swap bundler step → time it) rather than a full rebuild; pain 9 can focus on the settings-page budget exercise rather than also doing tree-shaking from scratch.
- Token-level streaming (ReadableStream / async iterators) is held as optional — good "what comes after async/await" beat if session 1 has room.
