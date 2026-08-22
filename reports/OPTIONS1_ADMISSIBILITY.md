# OPTIONS-1 — admissibility pilot: VIX-mean-reversion reopening and a full options extension

**Date: 2026-08-22. Class: admissibility pilot, following the `Family10_*` template.
0 budget slots spent. No forward return read. No option was priced, no greek was computed,
no options position was modelled.**

**Authorisation basis.** On 2026-08-22 the account holder was shown, and chose to override,
two standing facts: `pine.vix_fix` was measured by HT-1 and rejected (one of the worst
performers on the board — §1), and options selling / premium harvesting is a different
instrument class the desk does not currently touch. The account holder's direction was
**"full options extension"** — options chain data, greeks, and margin/tail-risk modelling.
This document is the first, mandatory step before any of that is built: **can it be built at
all under this programme's own free-data-only constraint (roadmap §27B)?**

**The answer, established without any predictive measurement, is: partially, and the
partial gap is structural, not a matter of more searching.**

---

## 1. Why VIX-mean-reversion reuse needs its own reformulation, not just a directive

`pine.vix_fix` was measured by HT-1 (`reports/HT1_TOURNAMENT_RESULT.md` §2.3) as a
single-name **directional equity signal** — does an extreme VIX-Fix score predict *this
stock's* forward price direction. It was among the worst performers at the 5-week horizon
(−0.1166 advantage, one of 18 of 27 candidates with an interval entirely below zero).
Re-entering that exact candidate, unmodified, would be barred by HT-1's own §0.1: *"a
candidate that failed is not re-entered with more epochs, a longer window or another
threshold."*

**The reformulation that makes reopening admissible follows PEAD-1's template
(`alpha/PEAD1_CHARTER.md` §2.3): a genuinely different dependent variable.** VIX mean
reversion's actual, classical use is not "predict next week's stock return" — it is "time
volatility-selling entries," which asks whether an **elevated, mean-reverting VIX level
predicts a subsequent contraction in realised volatility** (an IV/RV timing question), not
whether it predicts price direction. That is a different random variable from anything HT-1
measured, on the same six-condition reuse logic PEAD-1 applies to SUE:

| # | Condition | Status |
|---|---|---|
| 1 | Materially different target | **MET** — realised-vol contraction, not directional price return |
| 2 | Materially different arm/use | **MET** — a timing gate for a premium-selling decision, not a standalone directional signal |
| 3 | No HT-1 result rescored | **MET** — HT-1's `pine.vix_fix` row is unchanged and not reread as evidence here |
| 4 | No sign flip on an HT-1 outcome | **MET** — this is not `pine.vix_fix` inverted; it is a different measurement of the same underlying VIX-Fix construction |
| 5 | No HT-1 parameter retuned from HT-1's own results | **MET** — the construction, if reused, would be copied verbatim from `agent/*.txt`'s Pine source, not retuned |
| 6 | Fresh budget/stopping rule | **MET** — see §5 |

**This part of the reopening is admissible in principle.** What blocks it is not the
reformulation — it is what comes next.

---

## 2. The data question, checked directly rather than assumed

The account holder's directive named "full options extension: options chain data, greeks,
margin/tail-risk modelling." Before designing any of that, the programme's own free-data-only
rule (§27B) must be checked against what actually exists for free. §27B's pre-approved
shortlist — SEC EDGAR XBRL, Form 4, 13F, FRED/ALFRED — **does not include options data of any
kind**, so this was never pre-cleared; it must be established from scratch.

**Checked directly, 2026-08-22**, via `yfinance` (the programme's existing default data
source, roadmap §0.1):

```
>>> yf.Ticker('AAPL').options
('2026-08-24', '2026-08-26', '2026-08-28', ...)   # 20 expirations, all current/future
>>> yf.Ticker('AAPL').option_chain(exps[0]).calls.columns
['contractSymbol', 'lastTradeDate', 'strike', 'lastPrice', 'bid', 'ask', ...,
 'impliedVolatility', 'openInterest', ...]
```

**This is a live snapshot of currently-listed contracts only.** There is no parameter, no
endpoint, and no cached history that returns "the chain as it stood on 2023-04-11" or "the
implied volatility surface six months ago." `lastTradeDate` on a returned row reflects when
that specific contract last traded *before today's call* — it is metadata on a live quote,
not a historical database key. Once a contract expires, yfinance has no record of it at all.

**This is the same class of problem Family-10 hit and recorded, not a new kind of failure:**
a free data source that answers today's question but cannot answer "what would this have
shown as of a past date," which is the one property any point-in-time backtest requires
(roadmap §2.1, `CLAUDE.md` §2.1). Options chains are additionally worse than Family-10's
8-K case in one respect: 8-K filings are permanently retrievable from EDGAR regardless of
age; expired option contracts are not retrievable from any free source once they roll off —
the data does not merely lack a timestamp, it ceases to exist anywhere free.

**Greeks compound the problem rather than sidestep it.** `impliedVolatility` in the snapshot
above is Yahoo's own model output at query time, not a raw market observable with a
documented history either. A margin or tail-risk model needs a *time series* of strikes,
mid-prices and implied vols to backtest against — exactly what does not exist for free.

---

## 3. The verdict

> **`OPTIONS-1 STAGE 1 (DATA ADMISSIBILITY): FAIL for the execution layer.`**
> **Options chain data, historical implied volatility, and greeks cannot be obtained
> point-in-time from any free source this programme is authorised to use (§27B).** Building
> option pricing, margin modelling, or tail-risk simulation on top of live-only snapshot data
> would silently convert every backtest into a look-ahead study — reading today's
> options-market shape and treating it as if it were known in the past, which is precisely
> what `CLAUDE.md` §2.1 forbids at the data-door level, not just at the feature level.

**This is not a power problem, a coverage problem, or a resolution problem — it is
non-existence.** Family-10's own lesson (`family10-pilot-result` memory: "no block-length
rescue is permitted" and "the effect might be huge is also barred") does not even apply
here, because there is no honest way to construct the backtest at all, at any resolution,
before asking whether an effect is big enough to see.

**What did NOT fail:** the VIX-mean-reversion reformulation itself (§1's six conditions),
which remains admissible as a **signal-research question**, because that question does not
require an options chain at all — it requires only VIX's own historical daily closes
(`^VIX`, freely available with full history) and realised volatility computed from the
existing daily price history already in this programme's data door. Those two series answer
"does elevated VIX-mean-reversion predict a subsequent realised-vol contraction" without
touching a single option contract.

---

## 4. What this means for "full options extension" as directed

Stated plainly rather than softened, because §27B is the account holder's own standing rule
and this document does not have authority to waive it:

* **The mechanical build-out — chains, greeks, margin, tail-risk modelling — cannot proceed
  under the free-data-only constraint as it stands.** The only way to obtain the required
  history is a paid provider (CBOE DataShop, ORATS, OptionMetrics, or similar), which §27B
  currently prohibits outright: *"No provider spend, barred at §27B."*
* **This is the account holder's decision to make, not this session's.** Two paths exist,
  and neither is chosen here:
  1. **Amend §27B** to permit a paid options data source for this specific extension —
     a deliberate, named exception, the same weight of decision this charter's own
     reopening required.
  2. **Scope the options track down to what free data can support**: the VIX/realised-vol
     signal-research question in §1, which produces a *timing indicator* usable as
     information but not a backtested options P&L, margin model, or tail-risk simulation —
     because none of those can be honestly built without the missing history.
* **Nothing about §1's admissible reformulation is wasted under either path.** If a paid
  source is later authorised, the signal work becomes the entry condition for a real
  execution study; if it is not, the signal work is still a legitimate, free, testable
  question in its own right and does not depend on the answer.

---

## 5. If the account holder chooses the free-data-only path: VIX1 budget and next step

Recorded now so the reusable-asset trail is not lost, **not run**:

> **VIX1 budget: ONE confirmatory study** of "elevated VIX-mean-reversion predicts
> subsequent realised-volatility contraction," on `^VIX` daily closes and realised
> volatility from existing price history. Own budget slot, drawing nothing from V3, V4,
> PEAD-1, or HT-1's diagnostic instrument.

Before any slot is spent, VIX1 needs the same sequencing PEAD-1 requires: a power gate
(what half-width can this history resolve for a vol-contraction target, before any
predictive quantity is read), then a confirmatory pre-registration fixing the window and
CONTINUE rule, then the first measurement. **None of that is done here.** This document's
job was solely to answer whether the *options* half of the directive is buildable, and the
answer is: not without a data-source decision only the account holder can make.

---

## 6. Preservation statement

No forward return of any kind was read. No option was priced. No implied volatility surface
was modelled. No greek was computed. `pine.vix_fix`'s HT-1 record is unchanged. No V3, V4,
HT-1 or AMS-1 artefact was edited. The exam remains sealed. Production weight remains `0.0`.
Nothing was pushed. **Neither VIX1 nor any options execution study is authorised to run by
this document.**
