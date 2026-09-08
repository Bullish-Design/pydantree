# devenv-subset

This is the small both-products example. Product B authors a grammar and
packages it; Product A loads the bundle and traverses generated typed `Pair`
nodes. The schema is part of the bundle, so the consumer has no build-time
dependency on the authoring package.

```bash
devenv shell -- python examples/devenv-subset/extract.py
```
