import atexit
import io
import logging
import os


from bs4 import BeautifulSoup

from config.constants import URL

from playwright.sync_api import sync_playwright

import pytest


@pytest.fixture(scope="session")
def login_logout():
    # perform login and browser close once in a session
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--start-maximized"])
        context = browser.new_context(no_viewport=True)
        context.set_default_timeout(80000)
        page = context.new_page()
        # Navigate to the login URL
        page.goto(URL, wait_until="domcontentloaded")

        yield page
        # perform close the browser
        browser.close()


@pytest.hookimpl(tryfirst=True)
def pytest_html_report_title(report):
    report.title = "Automation_CodeGen"


# Add a column for descriptions
# def pytest_html_results_table_header(cells):
#     cells.insert(1, html.th("Description"))


# def pytest_html_results_table_row(report, cells):
#     cells.insert(
#         1, html.td(report.description if hasattr(report, "description") else "")
#     )


log_streams = {}


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    # Prepare StringIO for capturing logs
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.INFO)

    logger = logging.getLogger()
    logger.addHandler(handler)

    # Save handler and stream
    log_streams[item.nodeid] = (handler, stream)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()

    handler, stream = log_streams.get(item.nodeid, (None, None))

    if handler and stream:
        # Make sure logs are flushed
        handler.flush()
        log_output = stream.getvalue()

        # Only remove the handler, don't close the stream yet
        logger = logging.getLogger()
        logger.removeHandler(handler)

        # Store the log output on the report object for HTML reporting
        report.description = f"<pre>{log_output.strip()}</pre>"

        # Clean up references
        log_streams.pop(item.nodeid, None)
    else:
        report.description = ""


def pytest_collection_modifyitems(items):
    for item in items:
        if hasattr(item, 'callspec'):
            prompt = item.callspec.params.get("prompt")
            if prompt:
                item._nodeid = prompt  # This controls how the test name appears in the report


def rename_duration_column():
    report_path = os.path.abspath("report.html")  # or your report filename
    if not os.path.exists(report_path):
        print("Report file not found, skipping column rename.")
        return

    with open(report_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')

    # Find and rename the header
    headers = soup.select('table#results-table thead th')
    for th in headers:
        if th.text.strip() == 'Duration':
            th.string = 'Execution Time'
            # print("Renamed 'Duration' to 'Execution Time'")
            break
    else:
        print("'Duration' column not found in report.")

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(str(soup))


# Register this function to run after everything is done
atexit.register(rename_duration_column)


# Add logs and docstring to report
# @pytest.hookimpl(hookwrapper=True)
# def pytest_runtest_makereport(item, call):
#     outcome = yield
#     report = outcome.get_result()
#     report.description = str(item.function.__doc__)
#     os.makedirs("logs", exist_ok=True)
#     extra = getattr(report, "extra", [])
#     report.extra = extra
