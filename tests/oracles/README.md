# Extraction behavior oracles

The three JSON files in this directory are the durable observable-behavior
contract for the real examples:

- `bash-extract.json`
- `devenv-extract.json`
- `devenv-subset.json`

`tests/test_oracles.py` builds fresh grammar bundles from the committed
grammar/scanner sources, runs each example's own extraction code over its own
corpus, and compares the result with these JSON files. It also checks that the
oracles agree with the examples' independently maintained ground truth.

Regenerate the JSON after an intentional behavior change, then review the diff:

```bash
devenv shell -- python tests/test_oracles.py --generate
devenv shell -- python -m pytest tests/test_oracles.py -q
```

Native bundles are deliberately not committed. They are platform- and
toolchain-specific build outputs, generated in temporary directories by the
suite. The project does not guarantee backward compatibility for previously
generated bundle binaries or metadata; the supported contract is a fresh build
through the current pipeline producing the saved extraction behavior.
