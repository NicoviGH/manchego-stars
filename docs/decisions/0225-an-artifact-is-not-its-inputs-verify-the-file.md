---
id: 225
title: "An artifact is not its inputs — verify the FILE you are shipping"
date: "2026-08-14"
section: "Operational Gotchas (durable)"
issues: [25]
---

# An artifact is not its inputs — verify the FILE you are shipping

The scene-3 review GIF was assembled three times. Two of those runs read the frame directory
before the scene was re-filmed, and one finished last and won the filename. The committed clip was
therefore a **pre-fix capture showing the exact defect the commit above fixed**, and it went onto
the PR that way; Nicolas caught it.

The source frames had been checked by eye and were correct. **Checking the inputs is not checking
the output.** Verify a review artifact by decoding the artifact — for a GIF, iterate its own
frames — and be wary of the same output path being written by more than one job.
