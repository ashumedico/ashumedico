---
name: screen-proof
description: Prove a UI actually works by looking at it, not by asserting it rendered. Use after any change to a Streamlit/web page, a dashboard, a layout, colours, or anything the user will read on a screen — and before claiming a visual change is done. Covers screenshot-driven verification, measuring fit to a real viewport, and interrogating the DOM for which element is expensive.
---

# SCREEN-PROOF — rendered and visible are different claims

The test suite said both elements were present, correct, and in the right order. The
screenshot showed a blank strip where the header should be. Both were true: the elements
had rendered *underneath* Streamlit's own fixed toolbar, because the container's top
padding had been cut.

**No element-level test can catch that.** Only looking can.

---

## THE THREE MOVES

### 1. SCREENSHOT — look at it before saying it works

Drive a real browser at the size the user actually owns. His desk is 21 inches — 1920×940
of usable viewport after browser chrome. Not "desktop", not "wide": the number.

```python
pg = await b.new_page(viewport={"width": 1920, "height": 940})
await pg.goto(url, wait_until="networkidle", timeout=240000)
await pg.wait_for_selector('[data-testid="stTabs"]', timeout=240000)   # a real anchor
await pg.wait_for_timeout(9000)                                        # Streamlit paints late
await pg.screenshot(path=...)
```

Then **read the image**. Things found this way and no other way: a wordmark clipped by its
own glow above cap height; heatmap colours in `rgba()` that a hex-based check missed; a
scan button pushed off the right edge because six metrics beside tall HTML do not make a
row; the blank header above.

Environment notes that cost time to rediscover: Chromium lives at
`/opt/pw-browsers/chromium-*/chrome-linux/chrome`, needs `--no-sandbox`, and **Streamlit
scrolls an inner container, not the window** — `window.scrollTo` does nothing.

### 2. MEASURE — turn "looks about right" into arithmetic

Eyeballing cost three rounds. Measuring turned it into a sequence that said which change
actually paid: **2124 → 1537 → 1242 → 1143 → fits.**

```js
const el = document.querySelector('[data-testid="stMainBlockContainer"]');
const s  = el.closest('section') || el.parentElement;
return {content: el.scrollHeight, view: s.clientHeight};   // overflow = content − view
```

Ship the measurement as a test (`test_layout.py`), not as a one-off script — a layout
that fits today regresses tomorrow. And when the number is **adjusted** — subtracting
banners that only exist on a machine without a token — print the raw figure beside the
adjusted one. *An adjusted number that hides its adjustment is the same lie as a wrong
one.*

### 3. ASK THE DOM WHICH ELEMENT IS EXPENSIVE

Guessing what to cut wasted two rounds. Enumerating every child's height took one query
and found a three-line caption costing 45px on a tab that was 29px over.

```js
const vb = container.querySelector('[data-testid="stVerticalBlock"]') || container;
[...vb.children].map(el => [Math.round(el.getBoundingClientRect().height),
                            (el.innerText||'').slice(0,50)]);
```

**The most expensive thing on a page is rarely the thing that looks big.**

---

## LAYOUT RULES THAT CAME OUT OF THIS

- **Shrink the margins, never the numbers.** On a trading screen, smaller type is how a
  5418 gets read as a 5413. Cut padding, gaps and duplication first.
- **Tabs beat scroll** when the content genuinely exceeds one screen. A decision made by
  scrolling back and forth is a decision made from memory.
- **Things that must share a line belong in one element** whose CSS knows they are on a
  line together. Streamlit columns of `st.metric` beside tall HTML stack, grow the row to
  the tallest child, and push the last widget off the edge.
- **Never cut `.block-container` padding without removing the fixed toolbar** that padding
  exists to clear.
- **Wide content scrolls inside its own container**, never the page body.
- **Duplication is the cheapest thing to cut.** A metric row repeating every number that
  is already on the ticket below it cost 300px of a 940px screen.

---

## THE BAR

A visual change is not done when the code is written, nor when the tests pass. It is done
when a screenshot at the real viewport shows the intended result, the overflow measures
zero, and the check that proves it is committed so it can fail later.
