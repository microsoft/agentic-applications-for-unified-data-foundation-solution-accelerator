import os.path
import logging
import json
import re

from base.base import BasePage

from playwright.sync_api import expect

logger = logging.getLogger(__name__)


class HomePage(BasePage):
    # ---------- LOCATORS ----------
    HOME_PAGE_TEXT = "//span[normalize-space()='Start Chatting']"
    SHOW_CHAT_HISTORY_BUTTON = "//button[normalize-space()='Show Chat History']"
    HIDE_CHAT_HISTORY_BUTTON = "//button[normalize-space()='Hide Chat History']"
    
    # Updated menu & clear chat locators
    THREE_DOT_MENU = "//i[@class='ms-Icon root-89 css-115 ms-Button-icon icon-111']"
    CLEAR_CHAT_BUTTON = "//span[@class='ms-ContextualMenu-itemText label-133']"
    CLEARALL_BUTTON = "//span[contains(text(),'Clear All')]"
    
    NO_CHAT_HISTORY_TEXT = "//span[contains(text(),'No chat history.')]"
    CHAT_THREAD_TITLE = "//div[contains(@class, 'ChatHistoryListItemCell_chatTitle')]"
    ASK_QUESTION_TEXTAREA = "//textarea[@placeholder='Ask a question...']"
    SEND_BUTTON = "//button[@title='Send Question']"
    RESPONSE_CONTAINER = "//div[contains(@class, 'chat-message') and contains(@class, 'assistant')]"
    LINE_CHART = "//canvas[contains(@aria-label, 'Line chart')]"
    DONUT_CHART = "//canvas[contains(@aria-label, 'Donut chart')]"
    NEW_CHAT_BUTTON = "//button[@title='Create new Conversation']"


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
        no_history_element = self.page.locator(self.NO_CHAT_HISTORY_TEXT)
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

    def _validate_response(self, question, response_text):
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
                is_valid, error_message = self._validate_response(question, response_text)
                
                if is_valid:
                    logger.info(f"✓ Question answered successfully on attempt {attempt}")
                    return response_text
                else:
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
                    raise AssertionError(error_msg)
        
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
        """Click on 'Create new Conversation' button to start a fresh chat session."""
        logger.info("Clicking on 'Create new Conversation' button...")
        try:
            new_chat_btn = self.page.locator(self.NEW_CHAT_BUTTON)
            if new_chat_btn.count() > 0:
                new_chat_btn.click()
                self.page.wait_for_timeout(3000)
                logger.info("✓ Successfully clicked 'Create new Conversation' button")
            else:
                logger.warning("⚠️ 'Create new Conversation' button not found")
        except Exception as e:
            logger.error(f"❌ Failed to click 'Create new Conversation' button: {str(e)}")
            raise

    def show_chat_history_and_close(self):
        """Show chat history for 3 seconds and then close the page/app."""
        logger.info("Showing chat history for 3 seconds before closing...")
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
                
                # Close the page/app
                logger.info("Closing the page/app...")
                self.page.close()
                logger.info("✓ Page/app closed successfully")
            else:
                logger.warning("⚠️ 'Show Chat History' button not found, closing page directly...")
                self.page.close()
                logger.info("✓ Page/app closed successfully")
                
        except Exception as e:
            logger.error(f"❌ Error during show chat history and close: {str(e)}")
            # Still try to close the page even if there's an error
            try:
                self.page.close()
                logger.info("✓ Page/app closed after error")
            except:
                logger.error("❌ Failed to close page after error")
            raise
       
       