# flakyradar-upload

Cắm FlakyRadar vào CI trong 5 phút. Ví dụ workflow của repo bạn:

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
        continue-on-error: true  # đẩy report kể cả khi test fail
      - uses: your-org/flakyradar/examples/github-action/flakyradar-upload@main
        with:
          server-url: ${{ secrets.FLAKYRADAR_URL }}
          api-key: ${{ secrets.FLAKYRADAR_API_KEY }}
          report-path: junit.xml
```

`api-key` lấy từ Django Admin sau khi tạo `Project` (mỗi project có 1 API key).
