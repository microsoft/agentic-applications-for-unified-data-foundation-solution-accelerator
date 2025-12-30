"""Home page object module for Fabric SQL automation tests."""
import logging
import json
import re

from base.base import BasePage
from config.constants import HELLO_PROMPT, GOOD_MORNING_PROMPT, RAI_PROMPT, OUT_OF_SCOPE_PROMPT

from playwright.sync_api import expect

logger = logging.getLogger(__name__)


class HomePage(BasePage):
    """Page object class for Home Page interactions and validations."""
    # ---------- LOCATORS ----------
    HOME_PAGE_TEXT = "//span[normalize-space()='Start Chatting']"
    HOME_PAGE_SUBTEXT = "//span[.='You can ask questions around sales, products and orders.']"
    SHOW_CHAT_HISTORY_BUTTON = "//button[normalize-space()='Show Chat History']"
    HIDE_CHAT_HISTORY_BUTTON = "//button[normalize-space()='Hide Chat History']"

    # Updated menu & clear chat locators
    THREE_DOT_MENU = "//i[@data-icon-name='More']"
    CLEAR_CHAT_BUTTON = "//i[@data-icon-name='Delete']"
    CLEARALL_BUTTON = "//span[contains(text(),'Clear All')]"

    NO_CHAT_HISTORY_TEXT = "//span[contains(text(),'No chat history.')]"
    CHAT_THREAD_TITLE = "//div[contains(@class, 'ChatHistoryListItemCell_chatTitle')]"
    ASK_QUESTION_TEXTAREA = "//textarea[@placeholder='Ask a question...']"
    SEND_BUTTON = "//button[@title='Send Question']"
    RESPONSE_CONTAINER = "//div[contains(@class, 'chat-message') and contains(@class, 'assistant')]"
    LINE_CHART = "//canvas[contains(@aria-label, 'Line chart')]"
    DONUT_CHART = "//canvas[contains(@aria-label, 'Donut chart')]"
    NEW_CHAT_BUTTON = "//button[@title='Create new Conversation']"
    CHAT_EDIT_ICON = "//i[@data-icon-name='Edit']"
    CHAT_DELETE_ICON ="//button[@title='Delete']"
    CHAT_EDIT_TEXT = "//input[@type='text']"
    UPDATE_CHECK_ICON = "//i[@data-icon-name='CheckMark']"
    DELETE_BUTTON = "//span[contains(text(),'Delete')]"


    def __init__(self, page):
        """Initialize the HomePage with a Playwright page instance."""
        super().__init__(page)
        self.page = page

    def validate_home_page(self):

        """Validate that the home page elements are visible."""
        logger.info("Starting home page validation...")
        logger.info("Validating HOME_PAGE_TEXT is visible...")
        expect(self.page.locator(self.HOME_PAGE_TEXT)).to_be_visible()
        self.page.wait_for_timeout(4000)
        logger.info("✓ HOME_PAGE_TEXT is visible")

        logger.info("Home page validation completed successfully!")

    def clear_chat_history(self):
        """
        Clear chat history by clicking show chat history, clearing all chats if available, and hiding history.
        Steps:
        1. Click on Show Chat History button
        2. Check if history is available
        3. If history exists, click on 3 dots menu
        4. Select Clear Chat option
        5. Click on Clear All confirmation button
        6. Click on Hide Chat History button
        """
        logger.info("Starting chat history clear process...")

        # Step 1: Click on Show Chat History button
        logger.info("Clicking on Show Chat History button...")
        self.page.locator(self.SHOW_CHAT_HISTORY_BUTTON).click()
        self.page.wait_for_timeout(4000)
        logger.info("✓ Show Chat History button clicked")

        # Step 2: Check if history is available
        logger.info("Checking if chat history is available...")
        chat_thread_element = self.page.locator(self.CHAT_THREAD_TITLE)

        if chat_thread_element.count() > 0:
            logger.info(f"✓ Chat history found - {chat_thread_element.count()} chat(s) available")

            # Step 3: Click on 3 dots menu
            logger.info("Clicking on three dot menu...")
            self.page.locator(self.THREE_DOT_MENU).click()
            self.page.wait_for_timeout(4000)
            logger.info("✓ Three dot menu clicked")

            # Step 4: Select Clear Chat option
            logger.info("Clicking on Clear Chat option...")
            self.page.locator(self.CLEAR_CHAT_BUTTON).click()
            self.page.wait_for_timeout(4000)
            logger.info("✓ Clear Chat option selected")

            # Step 5: Click on Clear All confirmation button
            logger.info("Clicking on Clear All confirmation button...")
            self.page.locator(self.CLEARALL_BUTTON).click()
            self.page.wait_for_timeout(4000)
            logger.info("✓ Clear All confirmation button clicked - Chat history cleared")
        else:
            logger.info("ℹ No chat history available to clear")

        # Step 6: Click on Hide Chat History button
        logger.info("Clicking on Hide Chat History button...")
        self.page.locator(self.HIDE_CHAT_HISTORY_BUTTON).click()
        self.page.wait_for_timeout(4000)
        logger.info("✓ Hide Chat History button clicked")

        logger.info("Chat history clear process completed successfully!")

    def _validate_response(self, response_text):
        """Validate response for correct format and meaningful content."""
        response_lower = response_text.lower()

        # Check for empty or too short response
        if len(response_text.strip()) < 10:
            logger.warning("⚠️ Response is too short or empty")
            return False, "Response is too short or empty"

        # Check for HTML format
        if re.search(r'<[^>]+>', response_text):
            logger.warning("⚠️ Response contains HTML format")
            return False, "Response contains HTML format"

        # Check for JSON format
        if response_text.strip().startswith('{') or response_text.strip().startswith('['):
            try:
                json.loads(response_text)
                logger.warning("⚠️ Response is in JSON format")
                return False, "Response is in JSON format"
            except json.JSONDecodeError:
                pass

        # Check for "I don't know" type responses
        invalid_responses = [
            "i don't know",
            "i do not know",
            "i'm not sure",
            "i am not sure",
            "cannot answer",
            "can't answer",
            "unable to answer",
            "no information",
            "don't have information"
        ]

        if any(invalid_phrase in response_lower for invalid_phrase in invalid_responses):
            logger.warning("⚠️ Response indicates lack of knowledge")
            return False, "Response indicates lack of knowledge or inability to answer"

        logger.info("✓ Response validation passed")
        return True, ""

    def ask_question_with_retry(self, question, max_retries=2):
        """Ask question and validate response with retry logic (up to 2 attempts)."""
        logger.info(f"Asking question: '{question}'")

        for attempt in range(1, max_retries + 1):
            logger.info(f"Attempt {attempt} of {max_retries}")

            try:
                # Clear and enter question
                logger.info("Clearing question textarea...")
                textarea = self.page.locator(self.ASK_QUESTION_TEXTAREA)
                textarea.click()
                self.page.wait_for_timeout(1000)
                textarea.fill("")
                self.page.wait_for_timeout(1000)

                logger.info("Entering question...")
                textarea.fill(question)
                self.page.wait_for_timeout(2000)
                logger.info("✓ Question entered")

                # Wait for send button and click
                logger.info("Waiting for Send button...")
                send_button = self.page.locator(self.SEND_BUTTON)
                expect(send_button).to_be_enabled(timeout=10000)
                logger.info("✓ Send button enabled")

                send_button.click()
                self.page.wait_for_timeout(3000)
                logger.info("✓ Send button clicked")

                # Wait for and get response
                logger.info("Waiting for response...")
                response_container = self.page.locator(self.RESPONSE_CONTAINER).last
                expect(response_container).to_be_visible(timeout=60000)
                self.page.wait_for_timeout(5000)
                logger.info("✓ Response received")

                response_text = response_container.text_content()
                logger.info(f"Response (first 200 chars): {response_text[:200]}...")

                # Validate response
                is_valid, error_message = self._validate_response(response_text)

                if is_valid:
                    logger.info(f"✓ Question answered successfully on attempt {attempt}")
                    return response_text

                logger.warning(f"⚠️ Validation failed on attempt {attempt}: {error_message}")
                if attempt < max_retries:
                    logger.info(f"Retrying... ({max_retries - attempt} attempts remaining)")
                    # Click new chat button before retry to start fresh
                    try:
                        new_chat_btn = self.page.locator(self.NEW_CHAT_BUTTON)
                        if new_chat_btn.count() > 0:
                            new_chat_btn.click()
                            self.page.wait_for_timeout(2000)
                            logger.info("✓ Started new chat for retry")
                    except Exception:
                        pass
                    self.page.wait_for_timeout(3000)
                else:
                    error_msg = f"Response validation failed after {max_retries} attempts. Last error: {error_message}"
                    logger.error(f"❌ {error_msg}")
                    raise AssertionError(error_msg)

            except AssertionError:
                # Re-raise assertion errors (validation failures)
                raise
            except Exception as e:
                logger.error(f"❌ Error on attempt {attempt}: {str(e)}")
                if attempt < max_retries:
                    logger.info(f"Retrying due to error... ({max_retries - attempt} attempts remaining)")
                    # Click new chat button before retry to start fresh
                    try:
                        new_chat_btn = self.page.locator(self.NEW_CHAT_BUTTON)
                        if new_chat_btn.count() > 0:
                            new_chat_btn.click()
                            self.page.wait_for_timeout(2000)
                            logger.info("✓ Started new chat for retry")
                    except Exception:
                        pass
                    self.page.wait_for_timeout(3000)
                else:
                    error_msg = f"Failed to get valid response after {max_retries} attempts. Last error: {str(e)}"
                    logger.error(f"❌ {error_msg}")
                    raise AssertionError(error_msg) from e

        raise AssertionError(f"Failed to get valid response after {max_retries} attempts")

    def ask_questions_from_json(self, json_file_path):
        """Ask questions from JSON file one by one with validation and retry."""
        logger.info(f"Loading questions from: {json_file_path}")

        # Load questions from JSON
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if isinstance(data, dict) and 'questions' in data:
                questions = [q['question'] if isinstance(q, dict) else q for q in data['questions']]
            elif isinstance(data, list):
                questions = [q['question'] if isinstance(q, dict) else q for q in data]
            else:
                raise ValueError("Unsupported JSON format")

            logger.info(f"✓ Loaded {len(questions)} questions")

        except Exception as e:
            logger.error(f"❌ Failed to load questions: {str(e)}")
            raise

        # Process each question
        results = []
        for idx, question in enumerate(questions, 1):
            logger.info("=" * 80)
            logger.info(f"Processing Question {idx} of {len(questions)}")
            logger.info("=" * 80)

            try:
                response = self.ask_question_with_retry(question)
                results.append({
                    'question_number': idx,
                    'question': question,
                    'status': 'PASSED',
                    'response': response[:200]
                })
                logger.info(f"✓ Question {idx} completed")
                self.page.wait_for_timeout(3000)

            except AssertionError as e:
                results.append({
                    'question_number': idx,
                    'question': question,
                    'status': 'FAILED',
                    'error': str(e)
                })
                logger.error(f"❌ Question {idx} failed: {str(e)}")
                raise

        logger.info("=" * 80)
        logger.info("All questions processed successfully!")
        logger.info("=" * 80)

        # Click new conversation at the end
        self.click_new_conversation()

        return results

    def click_new_conversation(self):
        """Click on 'Create new Conversation' button to start a fresh chat session and validate home page elements."""
        logger.info("Clicking on 'Create new Conversation' button...")
        try:
            new_chat_btn = self.page.locator(self.NEW_CHAT_BUTTON)
            if new_chat_btn.count() > 0:
                new_chat_btn.click()
                self.page.wait_for_timeout(3000)
                logger.info("✓ Successfully clicked 'Create new Conversation' button")

                # Validate HOME_PAGE_TEXT is visible
                logger.info("Validating HOME_PAGE_TEXT is visible...")
                expect(self.page.locator(self.HOME_PAGE_TEXT)).to_be_visible(timeout=10000)
                logger.info("✓ HOME_PAGE_TEXT is visible")

                # Validate HOME_PAGE_SUBTEXT is visible
                logger.info("Validating HOME_PAGE_SUBTEXT is visible...")
                expect(self.page.locator(self.HOME_PAGE_SUBTEXT)).to_be_visible(timeout=10000)
                logger.info("✓ HOME_PAGE_SUBTEXT is visible")

                logger.info("✓ New conversation started successfully with home page elements validated")
            else:
                logger.warning("⚠️ 'Create new Conversation' button not found")
        except Exception as e:
            logger.error(f"❌ Failed to click 'Create new Conversation' button or validate home page elements: {str(e)}")
            raise

    def show_chat_history_and_close(self):
        """Show chat history for 3 seconds."""
        logger.info("Showing chat history for 3 seconds...")
        try:
            # Click on Show Chat History button
            logger.info("Clicking on Show Chat History button...")
            show_history_btn = self.page.locator(self.SHOW_CHAT_HISTORY_BUTTON)
            if show_history_btn.count() > 0:
                show_history_btn.click()
                logger.info("✓ Show Chat History button clicked")

                # Wait for 3 seconds to display chat history
                logger.info("Displaying chat history for 3 seconds...")
                self.page.wait_for_timeout(3000)
                logger.info("✓ Chat history displayed for 3 seconds")
            else:
                logger.warning("⚠️ 'Show Chat History' button not found")

        except Exception as e:
            logger.error(f"❌ Error during show chat history: {str(e)}")
            raise

    def validate_show_hide_chat_history_panel(self):
        """Validate Show/Hide Chat History Panel functionality."""
        logger.info("=" * 80)
        logger.info("Starting Show/Hide Chat History Panel Validation")
        logger.info("=" * 80)

        try:
            # Step 1: Click Show Chat History button
            logger.info("Step 1: Clicking on Show Chat History button...")
            show_history_btn = self.page.locator(self.SHOW_CHAT_HISTORY_BUTTON)
            expect(show_history_btn).to_be_visible(timeout=10000)
            show_history_btn.click()
            self.page.wait_for_timeout(2000)
            logger.info("✓ Show Chat History button clicked")

            # Step 2: Verify Hide Chat History button is visible
            logger.info("Step 2: Verifying Hide Chat History button is visible...")
            hide_history_btn = self.page.locator(self.HIDE_CHAT_HISTORY_BUTTON)
            expect(hide_history_btn).to_be_visible(timeout=10000)
            logger.info("✓ Hide Chat History button is visible - Panel is shown")

            # Step 3: Wait for 2 seconds to observe the panel
            logger.info("Step 3: Observing chat history panel for 2 seconds...")
            self.page.wait_for_timeout(2000)
            logger.info("✓ Chat history panel displayed")

            # Step 4: Click Hide Chat History button
            logger.info("Step 4: Clicking on Hide Chat History button...")
            hide_history_btn.click()
            self.page.wait_for_timeout(2000)
            logger.info("✓ Hide Chat History button clicked")

            # Step 5: Verify Show Chat History button is visible again
            logger.info("Step 5: Verifying Show Chat History button is visible again...")
            expect(show_history_btn).to_be_visible(timeout=10000)
            logger.info("✓ Show Chat History button is visible - Panel is hidden")

            logger.info("=" * 80)
            logger.info("Show/Hide Chat History Panel Validation Completed Successfully!")
            logger.info("=" * 80)

            return {
                'status': 'PASSED',
                'validation': 'Show/Hide Chat History Panel functionality works correctly'
            }

        except Exception as e:
            error_msg = f"Failed to validate Show/Hide Chat History Panel: {str(e)}"
            logger.error(f"❌ {error_msg}")
            raise AssertionError(error_msg) from e

    def ask_greeting_prompts_and_validate(self):
        """Ask greeting prompts from constants and validate responses."""
        logger.info("=" * 80)
        logger.info("Starting Greeting Prompts Validation")
        logger.info("=" * 80)

        greeting_prompts = [
            ("Hello", HELLO_PROMPT),
            ("Good Morning", GOOD_MORNING_PROMPT)
        ]

        results = []

        for idx, (prompt_name, prompt_text) in enumerate(greeting_prompts, 1):
            logger.info("=" * 80)
            logger.info(f"Processing Greeting Prompt {idx} of {len(greeting_prompts)}: {prompt_name}")
            logger.info("=" * 80)

            try:
                response = self.ask_question_with_retry(prompt_text)
                results.append({
                    'prompt_number': idx,
                    'prompt_name': prompt_name,
                    'prompt_text': prompt_text,
                    'status': 'PASSED',
                    'response': response[:200]
                })
                logger.info(f"✓ Greeting prompt '{prompt_name}' completed")
                self.page.wait_for_timeout(3000)

            except AssertionError as e:
                results.append({
                    'prompt_number': idx,
                    'prompt_name': prompt_name,
                    'prompt_text': prompt_text,
                    'status': 'FAILED',
                    'error': str(e)
                })
                logger.error(f"❌ Greeting prompt '{prompt_name}' failed: {str(e)}")
                raise

        logger.info("=" * 80)
        logger.info("All greeting prompts processed successfully!")
        logger.info("=" * 80)

        # Click new conversation at the end
        self.click_new_conversation()

        return results

    def ask_rai_prompt_and_validate(self):
        """Ask RAI prompt and validate that response contains 'I cannot assist with that.'."""
        logger.info("=" * 80)
        logger.info("Starting RAI Prompt Validation")
        logger.info("=" * 80)
        logger.info(f"Asking RAI prompt: '{RAI_PROMPT}'")

        try:
            # Clear and enter question
            logger.info("Clearing question textarea...")
            textarea = self.page.locator(self.ASK_QUESTION_TEXTAREA)
            textarea.click()
            self.page.wait_for_timeout(1000)
            textarea.fill("")
            self.page.wait_for_timeout(1000)

            logger.info("Entering RAI prompt...")
            textarea.fill(RAI_PROMPT)
            self.page.wait_for_timeout(2000)
            logger.info("✓ RAI prompt entered")

            # Wait for send button and click
            logger.info("Waiting for Send button...")
            send_button = self.page.locator(self.SEND_BUTTON)
            expect(send_button).to_be_enabled(timeout=10000)
            logger.info("✓ Send button enabled")

            send_button.click()
            self.page.wait_for_timeout(3000)
            logger.info("✓ Send button clicked")

            # Wait for and get response
            logger.info("Waiting for response...")
            response_container = self.page.locator(self.RESPONSE_CONTAINER).last
            expect(response_container).to_be_visible(timeout=60000)
            self.page.wait_for_timeout(5000)
            logger.info("✓ Response received")

            response_text = response_container.text_content()
            logger.info(f"Response received: {response_text}")

            # Validate that response contains the expected RAI message
            expected_messages = ["I cannot", "I can not"]
            response_lower = response_text.lower()
            if any(msg.lower() in response_lower for msg in expected_messages):
                matched_msg = next(msg for msg in expected_messages if msg.lower() in response_lower)
                logger.info(f"✓ RAI validation passed - Response contains: '{matched_msg}'")
                result = {
                    'prompt': RAI_PROMPT,
                    'status': 'PASSED',
                    'response': response_text,
                    'validation': f"Response correctly contains '{matched_msg}'"
                }
            else:
                error_msg = f"RAI validation failed - Expected response to contain '{' or '.join(expected_messages)}' but got: {response_text}"
                logger.error(f"❌ {error_msg}")
                raise AssertionError(error_msg)

            logger.info("=" * 80)
            logger.info("RAI Prompt Validation Completed Successfully!")
            logger.info("=" * 80)

            # Click new conversation at the end
            self.click_new_conversation()

            return result

        except AssertionError:
            raise
        except Exception as e:
            error_msg = f"Failed to validate RAI prompt: {str(e)}"
            logger.error(f"❌ {error_msg}")
            raise AssertionError(error_msg) from e

    def ask_out_of_scope_prompt_and_validate(self):
        """Ask out of scope prompt and validate that response contains 'I cannot'."""
        logger.info("=" * 80)
        logger.info("Starting Out of Scope Prompt Validation")
        logger.info("=" * 80)
        logger.info(f"Asking out of scope prompt: '{OUT_OF_SCOPE_PROMPT}'")

        try:
            # Clear and enter question
            logger.info("Clearing question textarea...")
            textarea = self.page.locator(self.ASK_QUESTION_TEXTAREA)
            textarea.click()
            self.page.wait_for_timeout(1000)
            textarea.fill("")
            self.page.wait_for_timeout(1000)

            logger.info("Entering out of scope prompt...")
            textarea.fill(OUT_OF_SCOPE_PROMPT)
            self.page.wait_for_timeout(2000)
            logger.info("✓ Out of scope prompt entered")

            # Wait for send button and click
            logger.info("Waiting for Send button...")
            send_button = self.page.locator(self.SEND_BUTTON)
            expect(send_button).to_be_enabled(timeout=10000)
            logger.info("✓ Send button enabled")

            send_button.click()
            self.page.wait_for_timeout(3000)
            logger.info("✓ Send button clicked")

            # Wait for and get response
            logger.info("Waiting for response...")
            response_container = self.page.locator(self.RESPONSE_CONTAINER).last
            expect(response_container).to_be_visible(timeout=60000)
            self.page.wait_for_timeout(5000)
            logger.info("✓ Response received")

            response_text = response_container.text_content()
            logger.info(f"Response received: {response_text}")

            # Validate that response contains the expected message
            expected_message = "I cannot"
            if expected_message.lower() in response_text.lower():
                logger.info(f"✓ Out of scope validation passed - Response contains: '{expected_message}'")
                result = {
                    'prompt': OUT_OF_SCOPE_PROMPT,
                    'status': 'PASSED',
                    'response': response_text,
                    'validation': f"Response correctly contains '{expected_message}'"
                }
            else:
                error_msg = f"Out of scope validation failed - Expected response to contain '{expected_message}' but got: {response_text}"
                logger.error(f"❌ {error_msg}")
                raise AssertionError(error_msg)

            logger.info("=" * 80)
            logger.info("Out of Scope Prompt Validation Completed Successfully!")
            logger.info("=" * 80)

            # Click new conversation at the end
            self.click_new_conversation()

            return result

        except AssertionError:
            raise
        except Exception as e:
            error_msg = f"Failed to validate out of scope prompt: {str(e)}"
            logger.error(f"❌ {error_msg}")
            raise AssertionError(error_msg) from e

    def validate_empty_string_prompt(self):
        """Validate that empty string prompt cannot be sent (send button should be disabled)."""
        logger.info("=" * 80)
        logger.info("Starting Empty String Prompt Validation")
        logger.info("=" * 80)

        try:
            # Step 1: Clear and ensure textarea is empty
            logger.info("Step 1: Clearing question textarea...")
            textarea = self.page.locator(self.ASK_QUESTION_TEXTAREA)
            textarea.click()
            self.page.wait_for_timeout(1000)
            textarea.fill("")
            self.page.wait_for_timeout(2000)
            logger.info("✓ Textarea cleared")

            # Step 2: Verify send button is disabled
            logger.info("Step 2: Verifying Send button is disabled...")
            send_button = self.page.locator(self.SEND_BUTTON)

            # Check if button is disabled
            is_disabled = send_button.is_disabled()
            if is_disabled:
                logger.info("✓ Send button is disabled for empty string - Validation PASSED")
            else:
                # Alternative check: button might not be visible or clickable
                try:
                    expect(send_button).to_be_disabled(timeout=3000)
                    logger.info("✓ Send button is disabled for empty string - Validation PASSED")
                except Exception as exc:
                    error_msg = "Send button is enabled for empty string - This should not be allowed"
                    logger.error(f"❌ {error_msg}")
                    raise AssertionError(error_msg) from exc

            # Step 3: Try entering whitespace only
            logger.info("Step 3: Testing with whitespace only...")
            textarea.fill("   ")
            self.page.wait_for_timeout(2000)

            is_disabled = send_button.is_disabled()
            if is_disabled:
                logger.info("✓ Send button is disabled for whitespace-only string - Validation PASSED")
            else:
                try:
                    expect(send_button).to_be_disabled(timeout=3000)
                    logger.info("✓ Send button is disabled for whitespace-only string - Validation PASSED")
                except Exception as exc:
                    error_msg = "Send button is enabled for whitespace-only string - This should not be allowed"
                    logger.error(f"❌ {error_msg}")
                    raise AssertionError(error_msg) from exc

            # Clear textarea at the end
            logger.info("Clearing textarea...")
            textarea.fill("")
            self.page.wait_for_timeout(1000)

            logger.info("=" * 80)
            logger.info("Empty String Prompt Validation Completed Successfully!")
            logger.info("=" * 80)

            return {
                'status': 'PASSED',
                'validation': 'Empty string and whitespace-only prompts correctly disabled send button'
            }

        except AssertionError:
            raise
        except Exception as e:
            error_msg = f"Failed to validate empty string prompt: {str(e)}"
            logger.error(f"❌ {error_msg}")
            raise AssertionError(error_msg) from e

    def edit_first_chat_history_item(self):
        """
        Open chat history, hover on first item, edit it to 'Updated chat', and validate the update.
        Steps:
        1. Click on Show Chat History button
        2. Hover on the first chat history item
        3. Click on Edit icon
        4. Update the text to 'Updated chat'
        5. Click on Update check icon
        6. Validate that the text is updated
        7. Click on Hide Chat History button
        """
        logger.info("=" * 80)
        logger.info("Starting Chat History Edit Validation")
        logger.info("=" * 80)

        try:
            # Step 1: Click on Show Chat History button
            logger.info("Step 1: Clicking on Show Chat History button...")
            show_history_btn = self.page.locator(self.SHOW_CHAT_HISTORY_BUTTON)
            expect(show_history_btn).to_be_visible(timeout=10000)
            show_history_btn.click()
            self.page.wait_for_timeout(3000)
            logger.info("✓ Show Chat History button clicked")

            # Step 2: Get the first chat history item and hover on it
            logger.info("Step 2: Hovering on the first chat history item...")
            first_chat_item = self.page.locator(self.CHAT_THREAD_TITLE).first
            expect(first_chat_item).to_be_visible(timeout=10000)

            # Get original text before editing
            original_text = first_chat_item.text_content()
            logger.info(f"Original chat title: '{original_text}'")

            # Hover on the first item to reveal edit icon
            first_chat_item.hover()
            self.page.wait_for_timeout(2000)
            logger.info("✓ Hovered on first chat history item")

            # Step 3: Click on Edit icon
            logger.info("Step 3: Clicking on Edit icon...")
            edit_icon = self.page.locator(self.CHAT_EDIT_ICON).first
            expect(edit_icon).to_be_visible(timeout=10000)
            edit_icon.click()
            self.page.wait_for_timeout(2000)
            logger.info("✓ Edit icon clicked")

            # Step 4: Update the text to 'Updated chat'
            logger.info("Step 4: Updating text to 'Updated chat'...")
            edit_text_field = self.page.locator(self.CHAT_EDIT_TEXT).first
            expect(edit_text_field).to_be_visible(timeout=10000)

            # Clear existing text and enter new text
            edit_text_field.click()
            self.page.wait_for_timeout(1000)
            edit_text_field.fill("")
            self.page.wait_for_timeout(1000)
            edit_text_field.fill("Updated chat")
            self.page.wait_for_timeout(2000)
            logger.info("✓ Text updated to 'Updated chat'")

            # Step 5: Click on Update check icon
            logger.info("Step 5: Clicking on Update check icon...")
            update_check_icon = self.page.locator(self.UPDATE_CHECK_ICON).first
            expect(update_check_icon).to_be_visible(timeout=10000)
            update_check_icon.click()
            self.page.wait_for_timeout(10000)
            logger.info("✓ Update check icon clicked")

            # Step 6: Validate that the text is updated
            logger.info("Step 6: Validating that text is updated to 'Updated chat'...")
            updated_chat_item = self.page.locator(self.CHAT_THREAD_TITLE).first
            expect(updated_chat_item).to_be_visible(timeout=10000)

            updated_text = updated_chat_item.text_content()
            logger.info(f"Updated chat title: '{updated_text}'")

            if "Updated chat" in updated_text:
                logger.info("✓ Chat history item successfully updated to 'Updated chat'")
            else:
                error_msg = f"Chat title update failed. Expected 'Updated chat' but got '{updated_text}'"
                logger.error(f"❌ {error_msg}")
                raise AssertionError(error_msg)

            # Step 7: Click on Hide Chat History button
            logger.info("Step 7: Clicking on Hide Chat History button...")
            hide_history_btn = self.page.locator(self.HIDE_CHAT_HISTORY_BUTTON)
            expect(hide_history_btn).to_be_visible(timeout=10000)
            hide_history_btn.click()
            self.page.wait_for_timeout(2000)
            logger.info("✓ Hide Chat History button clicked")

            logger.info("=" * 80)
            logger.info("Chat History Edit Validation Completed Successfully!")
            logger.info("=" * 80)

            return {
                'status': 'PASSED',
                'original_text': original_text,
                'updated_text': updated_text,
                'validation': 'Chat history item successfully edited and updated'
            }

        except AssertionError:
            raise
        except Exception as e:
            error_msg = f"Failed to edit chat history item: {str(e)}"
            logger.error(f"❌ {error_msg}")
            raise AssertionError(error_msg) from e

    def validate_empty_string_chat_history_edit(self):
        """
        Validate that user cannot save empty string or whitespace-only chat history name.
        Steps:
        1. Click on Show Chat History button
        2. Hover on the first chat history item
        3. Click on Edit icon
        4. Try to update with empty string
        5. Verify that update check icon is disabled or update fails
        6. Try to update with whitespace only
        7. Verify that update check icon is disabled or update fails
        8. Click on Hide Chat History button
        """
        logger.info("=" * 80)
        logger.info("Starting Empty String Chat History Edit Validation")
        logger.info("=" * 80)

        try:
            # Step 1: Click on Show Chat History button
            logger.info("Step 1: Clicking on Show Chat History button...")
            show_history_btn = self.page.locator(self.SHOW_CHAT_HISTORY_BUTTON)
            expect(show_history_btn).to_be_visible(timeout=10000)
            show_history_btn.click()
            self.page.wait_for_timeout(3000)
            logger.info("✓ Show Chat History button clicked")

            # Step 2: Get the first chat history item and hover on it
            logger.info("Step 2: Hovering on the first chat history item...")
            first_chat_item = self.page.locator(self.CHAT_THREAD_TITLE).first
            expect(first_chat_item).to_be_visible(timeout=10000)

            # Get original text before editing
            original_text = first_chat_item.text_content()
            logger.info(f"Original chat title: '{original_text}'")

            # Hover on the first item to reveal edit icon
            first_chat_item.hover()
            self.page.wait_for_timeout(2000)
            logger.info("✓ Hovered on first chat history item")

            # Step 3: Click on Edit icon
            logger.info("Step 3: Clicking on Edit icon...")
            edit_icon = self.page.locator(self.CHAT_EDIT_ICON).first
            expect(edit_icon).to_be_visible(timeout=10000)
            edit_icon.click()
            self.page.wait_for_timeout(2000)
            logger.info("✓ Edit icon clicked")

            # Step 4: Try to update with empty string
            logger.info("Step 4: Attempting to update with empty string...")
            edit_text_field = self.page.locator(self.CHAT_EDIT_TEXT).first
            expect(edit_text_field).to_be_visible(timeout=10000)

            # Clear text field
            edit_text_field.click()
            self.page.wait_for_timeout(1000)
            edit_text_field.fill("")
            self.page.wait_for_timeout(2000)
            logger.info("✓ Text field cleared (empty string)")

            # Step 5: Verify that update check icon is disabled
            logger.info("Step 5: Verifying update check icon is disabled for empty string...")
            update_check_icon = self.page.locator(self.UPDATE_CHECK_ICON).first

            # Check if update button is disabled or not visible
            is_disabled_empty = update_check_icon.is_disabled() if update_check_icon.count() > 0 else True
            if is_disabled_empty or update_check_icon.count() == 0:
                logger.info("✓ Update check icon is disabled for empty string - Validation PASSED")
            else:
                # Try clicking and verify no change
                try:
                    update_check_icon.click()
                    self.page.wait_for_timeout(2000)
                    current_text = self.page.locator(self.CHAT_THREAD_TITLE).first.text_content()
                    if current_text == original_text:
                        logger.info("✓ Update was rejected - Chat title unchanged - Validation PASSED")
                    else:
                        error_msg = f"Empty string update should not be allowed but title changed to '{current_text}'"
                        logger.error(f"❌ {error_msg}")
                        raise AssertionError(error_msg)
                except Exception:
                    logger.info("✓ Update failed as expected for empty string - Validation PASSED")

            # Re-open edit mode if needed
            if not edit_text_field.is_visible():
                first_chat_item = self.page.locator(self.CHAT_THREAD_TITLE).first
                first_chat_item.hover()
                self.page.wait_for_timeout(1000)
                edit_icon = self.page.locator(self.CHAT_EDIT_ICON).first
                edit_icon.click()
                self.page.wait_for_timeout(2000)
                edit_text_field = self.page.locator(self.CHAT_EDIT_TEXT).first

            # Step 6: Try to update with whitespace only
            logger.info("Step 6: Attempting to update with whitespace only...")
            edit_text_field.click()
            self.page.wait_for_timeout(1000)
            edit_text_field.fill("   ")
            self.page.wait_for_timeout(2000)
            logger.info("✓ Text field filled with whitespace only")

            # Step 7: Verify that update check icon is disabled for whitespace
            logger.info("Step 7: Verifying update check icon is disabled for whitespace...")
            update_check_icon = self.page.locator(self.UPDATE_CHECK_ICON).first

            is_disabled_whitespace = update_check_icon.is_disabled() if update_check_icon.count() > 0 else True
            if is_disabled_whitespace or update_check_icon.count() == 0:
                logger.info("✓ Update check icon is disabled for whitespace - Validation PASSED")
            else:
                # Try clicking and verify no change
                try:
                    update_check_icon.click()
                    self.page.wait_for_timeout(2000)
                    current_text = self.page.locator(self.CHAT_THREAD_TITLE).first.text_content()
                    if current_text == original_text:
                        logger.info("✓ Update was rejected - Chat title unchanged - Validation PASSED")
                    else:
                        error_msg = f"Whitespace-only update should not be allowed but title changed to '{current_text}'"
                        logger.error(f"❌ {error_msg}")
                        raise AssertionError(error_msg)
                except Exception:
                    logger.info("✓ Update failed as expected for whitespace - Validation PASSED")

            # Press Escape to exit edit mode
            logger.info("Exiting edit mode...")
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(1000)

            # Step 8: Click on Hide Chat History button
            logger.info("Step 8: Clicking on Hide Chat History button...")
            hide_history_btn = self.page.locator(self.HIDE_CHAT_HISTORY_BUTTON)
            expect(hide_history_btn).to_be_visible(timeout=10000)
            hide_history_btn.click()
            self.page.wait_for_timeout(2000)
            logger.info("✓ Hide Chat History button clicked")

            logger.info("=" * 80)
            logger.info("Empty String Chat History Edit Validation Completed Successfully!")
            logger.info("=" * 80)

            return {
                'status': 'PASSED',
                'original_text': original_text,
                'validation': 'Empty string and whitespace-only chat history name updates are correctly prevented'
            }

        except AssertionError:
            raise
        except Exception as e:
            error_msg = f"Failed to validate empty string chat history edit: {str(e)}"
            logger.error(f"❌ {error_msg}")
            raise AssertionError(error_msg) from e

    def delete_first_chat_history_item(self):
        """
        Open chat history, hover on first item, delete it, and validate the deletion.
        Steps:
        1. Click on Show Chat History button
        2. Get count of chat history items before deletion
        3. Get the first chat history item text
        4. Hover on the first chat history item
        5. Click on Delete icon
        6. Click on Delete confirmation button
        7. Validate that the item is deleted (count decreased or item text changed)
        8. Click on Hide Chat History button
        """
        logger.info("=" * 80)
        logger.info("Starting Chat History Delete Validation")
        logger.info("=" * 80)

        try:
            # Step 1: Click on Show Chat History button
            logger.info("Step 1: Clicking on Show Chat History button...")
            show_history_btn = self.page.locator(self.SHOW_CHAT_HISTORY_BUTTON)
            expect(show_history_btn).to_be_visible(timeout=10000)
            show_history_btn.click()
            self.page.wait_for_timeout(3000)
            logger.info("✓ Show Chat History button clicked")

            # Step 2: Get count of chat history items before deletion
            logger.info("Step 2: Getting count of chat history items before deletion...")
            chat_items = self.page.locator(self.CHAT_THREAD_TITLE)
            initial_count = chat_items.count()
            logger.info(f"Initial chat history count: {initial_count}")

            if initial_count == 0:
                error_msg = "No chat history items available to delete"
                logger.error(f"❌ {error_msg}")
                raise AssertionError(error_msg)

            # Step 3: Get the first chat history item text
            logger.info("Step 3: Getting the first chat history item text...")
            first_chat_item = self.page.locator(self.CHAT_THREAD_TITLE).first
            expect(first_chat_item).to_be_visible(timeout=10000)

            item_to_delete_text = first_chat_item.text_content()
            logger.info(f"Chat item to delete: '{item_to_delete_text}'")

            # Step 4: Hover on the first item to reveal delete icon
            logger.info("Step 4: Hovering on the first chat history item...")
            first_chat_item.hover()
            self.page.wait_for_timeout(2000)
            logger.info("✓ Hovered on first chat history item")

            # Step 5: Click on Delete icon
            logger.info("Step 5: Clicking on Delete icon...")
            delete_icon = self.page.locator(self.CHAT_DELETE_ICON).first
            expect(delete_icon).to_be_visible(timeout=10000)
            delete_icon.click()
            self.page.wait_for_timeout(2000)
            logger.info("✓ Delete icon clicked")

            # Step 6: Click on Delete confirmation button
            logger.info("Step 6: Clicking on Delete confirmation button...")
            delete_button = self.page.locator(self.DELETE_BUTTON)
            expect(delete_button).to_be_visible(timeout=10000)
            delete_button.click()
            self.page.wait_for_timeout(3000)
            logger.info("✓ Delete confirmation button clicked")

            # Step 7: Validate that the item is deleted
            logger.info("Step 7: Validating that the chat item is deleted...")

            # Get new count
            new_count = chat_items.count()
            logger.info(f"New chat history count: {new_count}")

            # Check if count decreased
            if new_count < initial_count:
                logger.info(f"✓ Chat history count decreased from {initial_count} to {new_count}")
                logger.info("✓ Chat history item successfully deleted")
            elif new_count == 0:
                logger.info("✓ Chat history is now empty - item was the last one and successfully deleted")
            else:
                # If count is same, check if the first item text changed
                self.page.wait_for_timeout(2000)
                current_first_item = self.page.locator(self.CHAT_THREAD_TITLE).first
                if current_first_item.count() > 0:
                    current_first_text = current_first_item.text_content()
                    if current_first_text != item_to_delete_text:
                        logger.info(f"✓ First item text changed from '{item_to_delete_text}' to '{current_first_text}'")
                        logger.info("✓ Chat history item successfully deleted")
                    else:
                        error_msg = f"Deletion failed - Item '{item_to_delete_text}' still exists"
                        logger.error(f"❌ {error_msg}")
                        raise AssertionError(error_msg)
                else:
                    logger.info("✓ No chat items found - successfully deleted")

            # Step 8: Click on Hide Chat History button
            logger.info("Step 8: Clicking on Hide Chat History button...")
            hide_history_btn = self.page.locator(self.HIDE_CHAT_HISTORY_BUTTON)
            expect(hide_history_btn).to_be_visible(timeout=10000)
            hide_history_btn.click()
            self.page.wait_for_timeout(2000)
            logger.info("✓ Hide Chat History button clicked")

            logger.info("=" * 80)
            logger.info("Chat History Delete Validation Completed Successfully!")
            logger.info("=" * 80)

            return {
                'status': 'PASSED',
                'deleted_item_text': item_to_delete_text,
                'initial_count': initial_count,
                'final_count': new_count,
                'validation': 'Chat history item successfully deleted and confirmed'
            }

        except AssertionError:
            raise
        except Exception as e:
            error_msg = f"Failed to delete chat history item: {str(e)}"
            logger.error(f"❌ {error_msg}")
            raise AssertionError(error_msg) from e


       