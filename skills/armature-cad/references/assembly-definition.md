# Assembly definition — structure and stack-up method

## Structure (one file per assembly, cad/assemblies/<ASM-ID>.md)

- **Scope & tree:** which PART-IDs and OTS items, and the sub-assembly
  hierarchy.
- **Mate scheme:** one row per mate — parts, mate type (planar/cylindrical/
  fastened...), the datum features carrying it. The assembly's position
  authority: which part's datums locate the rest.
- **Fasteners:** one row per fastener group — spec (M3×8 SHCS, A2-70),
  quantity, torque, thread engagement, locking method (nyloc/threadlocker/
  none and why).
- **Assembly order:** numbered steps. At each step: can the tool physically
  reach (name the tool and its swing)? Can the part be inserted with
  neighbors already placed? Any step needing three hands gets a jig.
- **Jigs & fixtures:** each with what it holds, to what accuracy, and
  whether it's printed/machined/bought.
- **Stack-ups:** per critical fit, the table below.

## Worst-case stack-up method

For each critical fit (a bearing bore pair's alignment, a shaft end-play,
a gear center distance):

1. Chain the dimensions from one side of the fit to the other through the
   parts that control it. Every link: nominal ± tolerance, from its part
   definition or datasheet.
2. Sum nominals; sum tolerances (worst case: straight sum — this scale of
   build rarely justifies RSS, and worst-case is the honest default).
3. Compare the resulting extreme fits against the functional requirement
   (min clearance, max misalignment a bearing tolerates per its datasheet).
4. If it doesn't close: tighten the *fewest* tolerances (each tightening is
   money), re-datum so fewer links are in the chain, or add an adjustment
   feature (shim, slot) — in that order of preference.

| # | Dimension (part, feature) | Nominal | Tol ± | Source |
| --- | --- | --- | --- | --- |
|  | **Result: extreme fit vs. requirement** | | | |
