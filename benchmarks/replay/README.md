# Synthetic replay fixtures — not video benchmarks

The three `.json` files in this directory contain only hand-authored coordinates and frame indices.
They are original synthetic test data, **not** Meta SAM 3.1 model results and **not** third-party footage.
They exist to test the deterministic rule engine and the browser evidence workflow without API charges.
Do not report their test success as real-world precision, recall, accuracy, or model capability.

For real benchmark videos, obtain explicit rights to the source material, document provenance/consent,
manually annotate ground-truth events, keep private video outside Git, and record both positive and
negative results. Include SAM frame-stride reports and cases with occlusion and identity uncertainty.
