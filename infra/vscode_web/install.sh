PIP_INDEX_URL="${PIP_INDEX_URL:-https://packagefeedproxy.microsoft.io/pypi/simple/}" \
  pip install -r requirements.txt --user -q

azd init -t microsoft/agentic-applications-for-unified-data-foundation-solution-accelerator