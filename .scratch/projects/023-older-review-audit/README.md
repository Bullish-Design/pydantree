# Review 023 — older-review audit

**Date:** 2026-09-08

This project records a live audit of the older adversarial and verification
reviews (014, 018, 019, 020, and 021). Historical findings are preserved in
their original project directories. This audit adds dated resolution notes and
fresh evidence; it does not rewrite those records.

The audit used the current source, the existing regression/oracle tests, and
`probes/probe_older_reviews.py`. Commands were run inside `devenv shell`.

The resulting status is **ready with documented limitations** for regular
personal use. The previously identified silent wrong-answer paths in the
trusted extraction and grammar-build paths have regression coverage or an
explicit failure policy. The documented escape hatches and scope boundaries
remain intentional limitations; they are not a claim of universal schema
validation or publication readiness.
