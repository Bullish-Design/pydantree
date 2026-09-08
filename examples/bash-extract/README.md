# bash-extract

This example loads the vendored `node-schema.json` with the
`tree_sitter_bash` wheel and traverses generated typed nodes. A compiled bundle
may be supplied with `--bundle`; the consumer remains Product-A only.

```bash
devenv shell -- python examples/bash-extract/extract.py
devenv shell -- python examples/bash-extract/extract.py --bundle /path/to/bundle
```
