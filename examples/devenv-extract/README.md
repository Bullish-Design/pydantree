# devenv-extract

The fleet example uses the vendored Nix schema and `Grammar` to find typed
`Binding` and `ListExpression` nodes in sanitized configuration files.

```bash
devenv shell -- python examples/devenv-extract/extract.py
devenv shell -- python examples/devenv-extract/extract.py --bundle /path/to/bundle
```
