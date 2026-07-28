# flakyradar-upload

Wire FlakyRadar into your CI in 5 minutes. Example workflow for your repo:

```yaml
name: test
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: pytest --junitxml=junit.xml
        continue-on-error: true  # upload the report even when tests fail
      - uses: your-org/flakyradar/examples/github-action/flakyradar-upload@main
        with:
          server-url: ${{ secrets.FLAKYRADAR_URL }}
          api-key: ${{ secrets.FLAKYRADAR_API_KEY }}
          report-path: junit.xml
```

Get the `api-key` from Django Admin after creating a `Project` (each project has
its own API key).
