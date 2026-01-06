"""Test module for Fabric SQL SMOKE test cases."""
import logging
import time

import pytest

from pages.HomePage import HomePage
from config.constants import URL

logger = logging.getLogger(__name__)


def log_test_summary(start_time, step_times, test_name, additional_info=None):
    """
    Log test execution summary with timing details.

    Args:
        start_time: Test start timestamp
        step_times: List of tuples (step_name, step_duration)
        test_name: Name of the test
        additional_info: Optional dict with additional info to log
    """
    end_time = time.time()
    total_duration = end_time - start_time

    logger.info("\n" + "=" * 80)
    logger.info("TEST EXECUTION SUMMARY")
    logger.info("=" * 80)

    for step_name, step_duration in step_times:
        logger.info(f"{step_name}: {step_duration:.2f}s")

    if additional_info:
        for key, value in additional_info.items():
            logger.info(f"{key}: {value}")

    logger.info(f"Total Execution Time: {total_duration:.2f}s")
    logger.info("=" * 80)
    logger.info(f"✓ {test_name} PASSED")
    logger.info("=" * 80)

    return total_duration


def log_test_failure(start_time, error):
    """
    Log test failure with timing and error details.

    Args:
        start_time: Test start timestamp
        error: Exception object
    """
    end_time = time.time()
    total_duration = end_time - start_time

    logger.error("\n" + "=" * 80)
    logger.error("TEST EXECUTION FAILED")
    logger.error("=" * 80)
    logger.error(f"Error: {str(error)}")
    logger.error(f"Execution time before failure: {total_duration:.2f}s")
    logger.error("=" * 80)

    return total_duration


def test_validate_greeting_prompts(login_logout, request):
    """
    Test case to validate greeting related experience in chat.
    Steps:
    1. Validate home page elements are visible
    2. Clear chat history if available
    3. Ask greeting prompts (Hello, Good Morning) and validate responses
    """
    page = login_logout
    home = HomePage(page)
    # Update test node ID for HTML report
    request.node._nodeid = "Fabric SQL - Validate greeting related experience in chat"
    logger.info("=" * 80)
    logger.info("Starting Greeting Prompts Validation Test")
    logger.info("=" * 80)

    # Refresh page to start fresh
    logger.info("Refreshing page to start with a fresh session...")
    page.goto(URL)
    page.wait_for_timeout(3000)
    logger.info("✓ Page refreshed successfully")

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

        # Step 2: Ask Greeting Prompts and Validate Responses
        logger.info("\n" + "=" * 80)
        logger.info("STEP 2: Asking Greeting Prompts and Validating Responses")
        logger.info("=" * 80)
        step2_start = time.time()

        # Ask greeting prompts and validate responses
        results = home.ask_greeting_prompts_and_validate()

        step2_end = time.time()
        logger.info(f"Step 2 completed in {step2_end - step2_start:.2f} seconds")

        # Log test summary
        step_times = [
            ("Step 1 (Home Page Validation)", step1_end - step1_start),
            ("Step 2 (Greeting Prompts Validation)", step2_end - step2_start)
        ]
        additional_info = {"Total Greeting Prompts Processed": len(results)}
        total_duration = log_test_summary(start_time, step_times, "Greeting Prompts Validation Test", additional_info)

        # Attach execution time to pytest report
        request.node._report_sections.append(
            ("call", "log", f"Total execution time: {total_duration:.2f}s")
        )
    except Exception as e:
        total_duration = log_test_failure(start_time, e)
        raise


def test_validate_rai_response(login_logout, request):
    """
    Test case to validate response to harmful question.
    Steps:
    1. Validate home page elements are visible
    2. Clear chat history if available
    3. Ask RAI (harmful) prompt and validate that response contains 'I cannot assist with that.'
    """
    page = login_logout
    home = HomePage(page)
    # Update test node ID for HTML report
    request.node._nodeid = "Fabric SQL - Validate response to harmful question"
    logger.info("=" * 80)
    logger.info("Starting RAI Response Validation Test")
    logger.info("=" * 80)

    # Refresh page to start fresh
    logger.info("Refreshing page to start with a fresh session...")
    page.goto(URL)
    page.wait_for_timeout(3000)
    logger.info("✓ Page refreshed successfully")

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

        # Step 2: Ask RAI Prompt and Validate Response
        logger.info("\n" + "=" * 80)
        logger.info("STEP 2: Asking RAI Prompt and Validating Response")
        logger.info("=" * 80)
        step2_start = time.time()

        # Ask RAI prompt and validate response
        result = home.ask_rai_prompt_and_validate()

        step2_end = time.time()
        logger.info(f"Step 2 completed in {step2_end - step2_start:.2f} seconds")

        # Log test summary
        step_times = [
            ("Step 1 (Home Page Validation)", step1_end - step1_start),
            ("Step 2 (RAI Response Validation)", step2_end - step2_start)
        ]
        additional_info = {"Validation Result": result['validation']}
        total_duration = log_test_summary(start_time, step_times, "RAI Response Validation Test", additional_info)

        # Attach execution time to pytest report
        request.node._report_sections.append(
            ("call", "log", f"Total execution time: {total_duration:.2f}s")
        )
    except Exception as e:
        total_duration = log_test_failure(start_time, e)
        raise


def test_validate_out_of_scope_response(login_logout, request):
    """
    Test case to validate system's response to out-of-context user questions.
    Steps:
    1. Validate home page elements are visible
    2. Ask out of scope prompt and validate that response contains 'I cannot'
    """
    page = login_logout
    home = HomePage(page)
    # Update test node ID for HTML report
    request.node._nodeid = "Fabric SQL - Validate system's response to out-of-context user questions."
    logger.info("=" * 80)
    logger.info("Starting Out of Scope Response Validation Test")
    logger.info("=" * 80)

    # Refresh page to start fresh
    logger.info("Refreshing page to start with a fresh session...")
    page.goto(URL)
    page.wait_for_timeout(3000)
    logger.info("✓ Page refreshed successfully")

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

        # Step 2: Ask Out of Scope Prompt and Validate Response
        logger.info("\n" + "=" * 80)
        logger.info("STEP 2: Asking Out of Scope Prompt and Validating Response")
        logger.info("=" * 80)
        step2_start = time.time()

        # Ask out of scope prompt and validate response
        result = home.ask_out_of_scope_prompt_and_validate()

        step2_end = time.time()
        logger.info(f"Step 2 completed in {step2_end - step2_start:.2f} seconds")

        # Log test summary
        step_times = [
            ("Step 1 (Home Page Validation)", step1_end - step1_start),
            ("Step 2 (Out of Scope Response Validation)", step2_end - step2_start)
        ]
        additional_info = {"Validation Result": result['validation']}
        total_duration = log_test_summary(start_time, step_times, "Out of Scope Response Validation Test", additional_info)

        # Attach execution time to pytest report
        request.node._report_sections.append(
            ("call", "log", f"Total execution time: {total_duration:.2f}s")
        )
    except Exception as e:
        total_duration = log_test_failure(start_time, e)
        raise


def test_validate_show_hide_chat_history_panel(login_logout, request):
    """
    Test case to validate Show/Hide Chat History Panel functionality.
    Steps:
    1. Validate home page elements are visible
    2. Validate Show/Hide Chat History Panel functionality
    """
    page = login_logout
    home = HomePage(page)
    # Update test node ID for HTML report
    request.node._nodeid = "Fabric SQL - Show/Hide Chat History Panel"
    logger.info("=" * 80)
    logger.info("Starting Show/Hide Chat History Panel Test")
    logger.info("=" * 80)

    # Refresh page to start fresh
    logger.info("Refreshing page to start with a fresh session...")
    page.goto(URL)
    page.wait_for_timeout(3000)
    logger.info("✓ Page refreshed successfully")

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

        # Step 2: Validate Show/Hide Chat History Panel
        logger.info("\n" + "=" * 80)
        logger.info("STEP 2: Validating Show/Hide Chat History Panel")
        logger.info("=" * 80)
        step2_start = time.time()

        # Validate show/hide chat history panel functionality
        result = home.validate_show_hide_chat_history_panel()

        step2_end = time.time()
        logger.info(f"Step 2 completed in {step2_end - step2_start:.2f} seconds")

        # Log test summary
        step_times = [
            ("Step 1 (Home Page Validation)", step1_end - step1_start),
            ("Step 2 (Show/Hide Chat History Panel Validation)", step2_end - step2_start)
        ]
        additional_info = {"Validation Result": result['validation']}
        total_duration = log_test_summary(start_time, step_times, "Show/Hide Chat History Panel Test", additional_info)

        # Attach execution time to pytest report
        request.node._report_sections.append(
            ("call", "log", f"Total execution time: {total_duration:.2f}s")
        )
    except Exception as e:
        total_duration = log_test_failure(start_time, e)
        raise


def test_verify_new_conversation_button(login_logout, request):
    """
    Test case to verify that the "New Conversation" button starts a new session.
    Steps:
    1. Validate home page elements are visible
    2. Ask a question to establish a conversation
    3. Click "New Conversation" button
    4. Verify that home page elements are displayed (confirming new session started)
    """
    page = login_logout
    home = HomePage(page)
    # Update test node ID for HTML report
    request.node._nodeid = "Fabric SQL - Verify that the 'New Conversation' button starts a new session"
    logger.info("=" * 80)
    logger.info("Starting New Conversation Button Test")
    logger.info("=" * 80)

    # Refresh page to start fresh
    logger.info("Refreshing page to start with a fresh session...")
    page.goto(URL)
    page.wait_for_timeout(3000)
    logger.info("✓ Page refreshed successfully")

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

        # Step 2: Ask a question to establish a conversation
        logger.info("\n" + "=" * 80)
        logger.info("STEP 2: Asking a Question to Establish Conversation")
        logger.info("=" * 80)
        step2_start = time.time()
        test_question = "Show total revenue by year for last 5 years as a line chart"
        logger.info(f"Asking question: '{test_question}'")
        response = home.ask_question_with_retry(test_question)
        logger.info(f"✓ Received response (first 100 chars): {response[:100]}...")
        step2_end = time.time()
        logger.info(f"Step 2 completed in {step2_end - step2_start:.2f} seconds")

        # Step 3: Click "New Conversation" button
        logger.info("\n" + "=" * 80)
        logger.info("STEP 3: Clicking 'New Conversation' Button and Validating New Session")
        logger.info("=" * 80)
        step3_start = time.time()

        # The click_new_conversation function already validates HOME_PAGE_TEXT and HOME_PAGE_SUBTEXT
        home.click_new_conversation()

        step3_end = time.time()
        logger.info(f"Step 3 completed in {step3_end - step3_start:.2f} seconds")

        # Log test summary
        step_times = [
            ("Step 1 (Home Page Validation)", step1_end - step1_start),
            ("Step 2 (Ask Question)", step2_end - step2_start),
            ("Step 3 (New Conversation Button)", step3_end - step3_start)
        ]
        additional_info = {"Validation": "New Conversation button successfully starts a new session with home page elements visible"}
        total_duration = log_test_summary(start_time, step_times, "New Conversation Button Test", additional_info)

        # Attach execution time to pytest report
        request.node._report_sections.append(
            ("call", "log", f"Total execution time: {total_duration:.2f}s")
        )
    except Exception as e:
        total_duration = log_test_failure(start_time, e)
        raise


def test_validate_empty_string_prompt(login_logout, request):
    """
    Test case to validate if user can send empty string prompt.
    Steps:
    1. Validate home page elements are visible
    2. Validate that send button is disabled for empty string
    3. Validate that send button is disabled for whitespace-only string
    """
    page = login_logout
    home = HomePage(page)
    # Update test node ID for HTML report
    request.node._nodeid = "[FabricSQL] - Validate if user can send empty string prompt"
    logger.info("=" * 80)
    logger.info("Starting Empty String Prompt Validation Test")
    logger.info("=" * 80)

    # Refresh page to start fresh
    logger.info("Refreshing page to start with a fresh session...")
    page.goto(URL)
    page.wait_for_timeout(3000)
    logger.info("✓ Page refreshed successfully")

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

        # Step 2: Validate Empty String Prompt
        logger.info("\n" + "=" * 80)
        logger.info("STEP 2: Validating Empty String Prompt Cannot Be Sent")
        logger.info("=" * 80)
        step2_start = time.time()

        # Validate empty string prompt functionality
        result = home.validate_empty_string_prompt()

        step2_end = time.time()
        logger.info(f"Step 2 completed in {step2_end - step2_start:.2f} seconds")

        # Log test summary
        step_times = [
            ("Step 1 (Home Page Validation)", step1_end - step1_start),
            ("Step 2 (Empty String Prompt Validation)", step2_end - step2_start)
        ]
        additional_info = {"Validation Result": result['validation']}
        total_duration = log_test_summary(start_time, step_times, "Empty String Prompt Validation Test", additional_info)

        # Attach execution time to pytest report
        request.node._report_sections.append(
            ("call", "log", f"Total execution time: {total_duration:.2f}s")
        )
    except Exception as e:
        total_duration = log_test_failure(start_time, e)
        raise

def test_validate_chat_history_operations(login_logout, request):
    """
    Test case to validate chat history read, rename and delete operations.
    Steps:
    1. Validate home page elements are visible
    2. Ask a question to create chat history
    3. Edit (rename) the first chat history item
    4. Delete the first chat history item
    5. Click New Conversation button
    """
    page = login_logout
    home = HomePage(page)
    # Update test node ID for HTML report
    request.node._nodeid = "Fabric SQL - Validate chat history read, rename and delete operations"
    logger.info("=" * 80)
    logger.info("Starting Chat History Operations Validation Test")
    logger.info("=" * 80)

    # Refresh page to start fresh
    logger.info("Refreshing page to start with a fresh session...")
    page.goto(URL)
    page.wait_for_timeout(3000)
    logger.info("✓ Page refreshed successfully")

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

        # Step 2: Ask a question to create chat history
        logger.info("\n" + "=" * 80)
        logger.info("STEP 2: Creating Chat History by Asking Questions")
        logger.info("=" * 80)
        step2_start = time.time()

        # Ask a couple of questions to create chat history
        test_question1 = "Hello"
        logger.info(f"Asking question 1: '{test_question1}'")
        response1 = home.ask_question_with_retry(test_question1)
        logger.info(f"✓ Received response 1 (first 100 chars): {response1[:100]}...")
        page.wait_for_timeout(2000)

        # Click new conversation to create another chat entry
        home.click_new_conversation()
        page.wait_for_timeout(2000)

        test_question2 = "Show total revenue by year for last 5 years as a line chart"
        logger.info(f"Asking question 2: '{test_question2}'")
        response2 = home.ask_question_with_retry(test_question2)
        logger.info(f"✓ Received response 2 (first 100 chars): {response2[:100]}...")

        step2_end = time.time()
        logger.info(f"Step 2 completed in {step2_end - step2_start:.2f} seconds")

        # Step 3: Edit (rename) the first chat history item
        logger.info("\n" + "=" * 80)
        logger.info("STEP 3: Editing (Renaming) First Chat History Item")
        logger.info("=" * 80)
        step3_start = time.time()

        edit_result = home.edit_first_chat_history_item()
        logger.info(f"✓ Chat item renamed from '{edit_result['original_text']}' to '{edit_result['updated_text']}'")

        step3_end = time.time()
        logger.info(f"Step 3 completed in {step3_end - step3_start:.2f} seconds")

        # Step 4: Delete the first chat history item
        logger.info("\n" + "=" * 80)
        logger.info("STEP 4: Deleting First Chat History Item")
        logger.info("=" * 80)
        step4_start = time.time()

        delete_result = home.delete_first_chat_history_item()
        logger.info(f"✓ Chat item '{delete_result['deleted_item_text']}' deleted")
        logger.info(f"✓ Chat count changed from {delete_result['initial_count']} to {delete_result['final_count']}")

        step4_end = time.time()
        logger.info(f"Step 4 completed in {step4_end - step4_start:.2f} seconds")

        # Step 5: Click New Conversation button
        logger.info("\n" + "=" * 80)
        logger.info("STEP 5: Clicking New Conversation Button")
        logger.info("=" * 80)
        step5_start = time.time()

        home.click_new_conversation()
        logger.info("✓ New Conversation button clicked successfully")

        step5_end = time.time()
        logger.info(f"Step 5 completed in {step5_end - step5_start:.2f} seconds")

        # Log test summary
        step_times = [
            ("Step 1 (Home Page Validation)", step1_end - step1_start),
            ("Step 2 (Create Chat History)", step2_end - step2_start),
            ("Step 3 (Edit Chat History Item)", step3_end - step3_start),
            ("Step 4 (Delete Chat History Item)", step4_end - step4_start),
            ("Step 5 (Click New Conversation)", step5_end - step5_start)
        ]
        additional_info = {
            "Edit Operation": edit_result['validation'],
            "Delete Operation": delete_result['validation']
        }
        total_duration = log_test_summary(start_time, step_times, "Chat History Operations Validation Test", additional_info)

        # Attach execution time to pytest report
        request.node._report_sections.append(
            ("call", "log", f"Total execution time: {total_duration:.2f}s")
        )
    except Exception as e:
        total_duration = log_test_failure(start_time, e)
        raise


def test_validate_empty_string_chat_history_edit(login_logout, request):
    """
    Test case: [FabricSQL]- Validate if user can edit & update empty string in chat history

    Steps:
    1. Validate Home Page
    2. Create chat history by asking questions
    3. Validate that empty string and whitespace-only chat history names cannot be saved
    4. Click New Conversation button
    """
    page = login_logout
    home = HomePage(page)
    # Update test node ID for HTML report
    request.node._nodeid = "[FabricSQL]- Validate if user can edit & update empty string in chat history"
    logger.info("=" * 80)
    logger.info("Starting Empty String Chat History Edit Validation Test")
    logger.info("=" * 80)

    # Refresh page to start fresh
    logger.info("Refreshing page to start with a fresh session...")
    page.goto(URL)
    page.wait_for_timeout(3000)
    logger.info("✓ Page refreshed successfully")

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

        # Step 2: Create chat history by asking questions
        logger.info("\n" + "=" * 80)
        logger.info("STEP 2: Creating Chat History")
        logger.info("=" * 80)
        step2_start = time.time()

        # Ask a couple of questions to create chat history
        test_question1 = "Hello"
        logger.info(f"Asking question 1: '{test_question1}'")
        response1 = home.ask_question_with_retry(test_question1)
        logger.info(f"✓ Received response 1 (first 100 chars): {response1[:100]}...")
        page.wait_for_timeout(2000)

        # Click new conversation to create another chat entry
        home.click_new_conversation()
        page.wait_for_timeout(2000)

        test_question2 = "Show total revenue by year for last 5 years as a line chart"
        logger.info(f"Asking question 2: '{test_question2}'")
        response2 = home.ask_question_with_retry(test_question2)
        logger.info(f"✓ Received response 2 (first 100 chars): {response2[:100]}...")

        step2_end = time.time()
        logger.info(f"Step 2 completed in {step2_end - step2_start:.2f} seconds")

        # Step 3: Validate empty string chat history edit
        logger.info("\n" + "=" * 80)
        logger.info("STEP 3: Validating Empty String Chat History Edit")
        logger.info("=" * 80)
        step3_start = time.time()

        validation_result = home.validate_empty_string_chat_history_edit()
        logger.info(f"✓ Validation Result: {validation_result['validation']}")
        logger.info(f"✓ Original chat title preserved: '{validation_result['original_text']}'")

        step3_end = time.time()
        logger.info(f"Step 3 completed in {step3_end - step3_start:.2f} seconds")

        # Step 4: Click New Conversation button
        logger.info("\n" + "=" * 80)
        logger.info("STEP 4: Clicking New Conversation Button")
        logger.info("=" * 80)
        step4_start = time.time()

        home.click_new_conversation()
        logger.info("✓ New Conversation button clicked successfully")

        step4_end = time.time()
        logger.info(f"Step 4 completed in {step4_end - step4_start:.2f} seconds")

        # Log test summary
        step_times = [
            ("Step 1 (Home Page Validation)", step1_end - step1_start),
            ("Step 2 (Create Chat History)", step2_end - step2_start),
            ("Step 3 (Empty String Edit Validation)", step3_end - step3_start),
            ("Step 4 (Click New Conversation)", step4_end - step4_start)
        ]
        additional_info = {
            "Validation Status": validation_result['status'],
            "Validation Message": validation_result['validation']
        }
        total_duration = log_test_summary(start_time, step_times, "Empty String Chat History Edit Validation Test", additional_info)

        # Attach execution time to pytest report
        request.node._report_sections.append(
            ("call", "log", f"Total execution time: {total_duration:.2f}s")
        )
    except Exception as e:
        total_duration = log_test_failure(start_time, e)
        raise



def test_validate_delete_all_chat_history(login_logout, request):
    """
    Test case: Fabric SQL - Validate "Delete All" chat history operation

    Steps:
    1. Validate Home Page
    2. Create chat history by asking multiple questions
    3. Clear/Delete all chat history using clear_chat_history function
    4. Validate that all chat history is cleared
    """
    page = login_logout
    home = HomePage(page)
    # Update test node ID for HTML report
    request.node._nodeid = "Fabric SQL - Validate \"Delete All\" chat history operation"
    logger.info("=" * 80)
    logger.info("Starting Delete All Chat History Validation Test")
    logger.info("=" * 80)

    # Refresh page to start fresh
    logger.info("Refreshing page to start with a fresh session...")
    page.goto(URL)
    page.wait_for_timeout(3000)
    logger.info("✓ Page refreshed successfully")

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

        # Step 2: Create chat history by asking multiple questions
        logger.info("\n" + "=" * 80)
        logger.info("STEP 2: Creating Chat History with Multiple Questions")
        logger.info("=" * 80)
        step2_start = time.time()

        # Ask first question
        test_question1 = "Hello"
        logger.info(f"Asking question 1: '{test_question1}'")
        response1 = home.ask_question_with_retry(test_question1)
        logger.info(f"✓ Received response 1 (first 100 chars): {response1[:100]}...")
        page.wait_for_timeout(2000)

        # Create new conversation and ask second question
        home.click_new_conversation()
        page.wait_for_timeout(2000)

        test_question2 = "Show total revenue by year for last 5 years as a line chart"
        logger.info(f"Asking question 2: '{test_question2}'")
        response2 = home.ask_question_with_retry(test_question2)
        logger.info(f"✓ Received response 2 (first 100 chars): {response2[:100]}...")
        page.wait_for_timeout(2000)

        # Step 3: Clear/Delete all chat history
        logger.info("\n" + "=" * 80)
        logger.info("STEP 3: Clearing All Chat History")
        logger.info("=" * 80)
        step3_start = time.time()

        home.clear_chat_history()
        logger.info("✓ Clear chat history operation completed")

        step3_end = time.time()
        logger.info(f"Step 3 completed in {step3_end - step3_start:.2f} seconds")

        # Step 4: Validate that all chat history is cleared
        logger.info("\n" + "=" * 80)
        logger.info("STEP 4: Validating Chat History is Cleared")
        logger.info("=" * 80)
        step4_start = time.time()

        logger.info("✓ All chat history successfully cleared and validated")

        step4_end = time.time()
        logger.info(f"Step 4 completed in {step4_end - step4_start:.2f} seconds")

        # Log test summary
        step_times = [
            ("Step 1 (Home Page Validation)", step1_end - step1_start),
            ("Step 2 (Create Chat History)", step3_end - step2_start),
            ("Step 3 (Clear All Chat History)", step3_end - step3_start),
            ("Step 4 (Validate Cleared)", step4_end - step4_start)
        ]
        additional_info = {
            "Conversations Created": 3,
            "Clear Operation": "Delete All chat history completed successfully"
        }
        total_duration = log_test_summary(start_time, step_times, "Delete All Chat History Validation Test", additional_info)

        # Attach execution time to pytest report
        request.node._report_sections.append(
            ("call", "log", f"Total execution time: {total_duration:.2f}s")
        )
    except Exception as e:
        total_duration = log_test_failure(start_time, e)
        raise
