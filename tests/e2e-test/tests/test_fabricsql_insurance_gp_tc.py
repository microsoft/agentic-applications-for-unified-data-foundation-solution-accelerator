"""Test module for Fabric SQL Insurance golden path and feature test cases."""
import logging
import time

from pages.HomePage import HomePage
from config.constants import URL
from tests.test_utils import log_test_summary, log_test_failure

logger = logging.getLogger(__name__)


def test_validate_insurance_gp(login_logout, request):
    """
    Test case to validate Insurance golden path works properly.
    Steps:
    1. Validate home page elements are visible (HOME_PAGE_TEXT)
    2. Clear chat history if available
    3. Ask Insurance-specific questions from JSON file and validate responses
    """
    page = login_logout
    home = HomePage(page)
     # Update test node ID for HTML report
    request.node._nodeid = "Golden Path - Fabric SQL Insurance - test golden path works properly"
    logger.info("=" * 80)
    logger.info("Starting Insurance Golden Path Validation Test")
    logger.info("=" * 80)
    start_time = time.time()

    try:
        # Step 1: Validate Home Page
        logger.info("\n" + "=" * 80)
        logger.info("STEP 1: Validating Home Page")
        logger.info("=" * 80)
        step1_start = time.time()
        home.validate_home_page(use_case="insurance")
        step1_end = time.time()
        logger.info(f"Step 1 completed in {step1_end - step1_start:.2f} seconds")

        # Step 2: Clear Chat History
        logger.info("\n" + "=" * 80)
        logger.info("STEP 2: Clearing Chat History")
        logger.info("=" * 80)
        step2_start = time.time()
        home.clear_chat_history()
        step2_end = time.time()
        logger.info(f"Step 2 completed in {step2_end - step2_start:.2f} seconds")

        # Step 3: Ask Insurance Questions and Validate Responses
        logger.info("\n" + "=" * 80)
        logger.info("STEP 3: Asking Insurance Questions and Validating Responses")
        logger.info("=" * 80)
        step3_start = time.time()
        json_file_path = "testdata/prompt_insurance.json"

        # Ask questions and validate UI responses
        results = home.ask_questions_from_json(json_file_path, use_case="insurance")

        # Ensure new conversation is started at the end
        logger.info("Ensuring new conversation is started...")
        home.click_new_conversation(use_case="insurance")

        step3_end = time.time()
        logger.info(f"Step 3 completed in {step3_end - step3_start:.2f} seconds")

        # Log test summary
        step_times = [
            ("Step 1 (Home Page Validation)", step1_end - step1_start),
            ("Step 2 (Clear Chat History)", step2_end - step2_start),
            ("Step 3 (Ask Insurance Questions & Validate)", step3_end - step3_start)
        ]
        additional_info = {"Total Insurance Questions Processed": len(results)}
        total_duration = log_test_summary(start_time, step_times, "Insurance Golden Path Validation Test", additional_info)

        # Show chat history for 3 seconds and close the page/app
        logger.info("Showing chat history and closing application...")
        home.show_chat_history_and_close()

        # Attach execution time to pytest report
        request.node._report_sections.append(
            ("call", "log", f"Total execution time: {total_duration:.2f}s")
        )
    except Exception as e:
        total_duration = log_test_failure(start_time, e)
        raise
