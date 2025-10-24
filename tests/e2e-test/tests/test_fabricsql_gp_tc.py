import logging
import time

from pages.HomePage import HomePage

import pytest

logger = logging.getLogger(__name__)


def test_validate_home_page(login_logout, request):
    """
    Test case to validate home page is loaded correctly.
    Steps:
    1. Validate home page elements are visible (HOME_PAGE_TEXT)
    2. Clear chat history if available
    3. Ask questions from JSON file and validate responses
    """
    page = login_logout
    home = HomePage(page)
     # Update test node ID for HTML report
    request.node._nodeid = "Golden Path - Fabric SQL- test golden path works properly"
    logger.info("=" * 80)
    logger.info("Starting Home Page Validation Test")
    logger.info("=" * 80)
    start_time = time.time()
    
    try:
        # Step 1: Validate Home Page
        logger.info("\n" + "=" * 80)
        logger.info("STEP 1: Validating Home Page")
        logger.info("=" * 80)
        step1_start = time.time()
        home.validate_home_page()
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
        
        # Step 3: Ask Questions and Validate Responses
        logger.info("\n" + "=" * 80)
        logger.info("STEP 3: Asking Questions and Validating Responses")
        logger.info("=" * 80)
        step3_start = time.time()
        json_file_path = "testdata/prompt.json"
        
        
        
        # Ask questions and validate UI responses
        results = home.ask_questions_from_json(json_file_path)
        
        # Ensure new conversation is started at the end
        logger.info("Ensuring new conversation is started...")
        home.click_new_conversation()
        
        step3_end = time.time()
        logger.info(f"Step 3 completed in {step3_end - step3_start:.2f} seconds")
        
        end_time = time.time()
        total_duration = end_time - start_time
        logger.info("\n" + "=" * 80)
        logger.info("TEST EXECUTION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Step 1 (Home Page Validation): {step1_end - step1_start:.2f}s")
        logger.info(f"Step 2 (Clear Chat History): {step2_end - step2_start:.2f}s")
        logger.info(f"Step 3 (Ask Questions & Validate): {step3_end - step3_start:.2f}s")
        logger.info(f"Total Questions Processed: {len(results)}")
        logger.info(f"Total Execution Time: {total_duration:.2f}s")
        logger.info("=" * 80)
        logger.info("✓ Home Page Validation Test PASSED")
        logger.info("=" * 80)
        
        # Show chat history for 3 seconds and close the page/app
        logger.info("Showing chat history and closing application...")
        home.show_chat_history_and_close()
        
        # Attach execution time to pytest report
        request.node._report_sections.append(
            ("call", "log", f"Total execution time: {total_duration:.2f}s")
        )
    except Exception as e:
        end_time = time.time()
        total_duration = end_time - start_time
        logger.error("\n" + "=" * 80)
        logger.error("TEST EXECUTION FAILED")
        logger.error("=" * 80)
        logger.error(f"Error: {str(e)}")
        logger.error(f"Execution time before failure: {total_duration:.2f}s")
        logger.error("=" * 80)
        raise

