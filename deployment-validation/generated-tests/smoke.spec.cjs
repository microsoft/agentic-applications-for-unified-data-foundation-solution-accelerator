const { test, expect } = require('@playwright/test');

async function createDisposableConversation(page) {
  await page.goto('/');
  const question = page.locator('textarea[placeholder="Ask a question..."]');
  await question.fill('List five products for smoke-test history validation.');
  await page.locator('button[title="Send Question"]').click();
  await expect(page.locator('div.chat-message.assistant').last()).toBeVisible({ timeout: 90000 });
}

test.describe('Generated deployment smoke validation', () => {
  test("Authentication and session establishment", async ({ page }) => {
    const response = await page.request.get('/.auth/me');
    expect(response.ok()).toBeTruthy();
    const identities = await response.json();
    expect(Array.isArray(identities)).toBeTruthy();
    expect(identities.length).toBeGreaterThan(0);
  });

  test("Authenticated UI shell loads", async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('button', { name: /user menu for/i })).toBeVisible();
  });

  test("User identity menu is available", async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /user menu for/i }).click();
    await expect(page.getByRole('menuitem', { name: /sign out/i })).toBeVisible();
  });

  test("Application shell page load", async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('textarea[placeholder="Ask a question..."]')).toBeVisible();
    await expect(page.getByText('Start Chatting')).toBeVisible();
  });

  test("Send message by button", async ({ page }) => {
    await page.goto('/');
    const question = page.locator('textarea[placeholder="Ask a question..."]');
    await expect(question).toBeVisible();
    await question.fill("What are my top-performing products?");
    const send = page.locator('button[title="Send Question"]');
    await expect(send).toBeEnabled();
    await send.click();
    const response = page.locator('div.chat-message.assistant').last();
    await expect(response).toBeVisible({ timeout: 90000 });
    await expect.poll(async () => (await response.innerText()).trim().length).toBeGreaterThan(10);
    await expect(response).not.toContainText(/cannot answer|unable to answer|do not have information/i);
  });

  test("Send message by Enter", async ({ page }) => {
    await page.goto('/');
    const question = page.locator('textarea[placeholder="Ask a question..."]');
    await question.fill("Show total revenue by year for the last 5 years.");
    await question.press('Enter');
    await expect(page.locator('div.chat-message.user').last()).toContainText("Show total revenue by year for the last 5 years.");
    await expect(page.locator('div.chat-message.assistant').last()).toBeVisible({ timeout: 90000 });
  });

  test("Text response rendering", async ({ page }) => {
    await page.goto('/');
    const question = page.locator('textarea[placeholder="Ask a question..."]');
    await expect(question).toBeVisible();
    await question.fill("Which segments show the highest YoY growth?");
    const send = page.locator('button[title="Send Question"]');
    await expect(send).toBeEnabled();
    await send.click();
    const response = page.locator('div.chat-message.assistant').last();
    await expect(response).toBeVisible({ timeout: 90000 });
    await expect.poll(async () => (await response.innerText()).trim().length).toBeGreaterThan(10);
    await expect(response).not.toContainText(/cannot answer|unable to answer|do not have information/i);
  });

  test("Chart response rendering", async ({ page }) => {
    await page.goto('/');
    await page.locator('textarea[placeholder="Ask a question..."]').fill("Show total revenue by year for the last 5 years as a line chart.");
    await page.locator('button[title="Send Question"]').click();
    await expect(page.locator('div.chat-message.assistant canvas').last()).toBeVisible({ timeout: 90000 });
  });

  test("Citation rendering from repository documents", async ({ page }) => {
    await page.goto('/');
    await page.locator('textarea[placeholder="Ask a question..."]').fill("According to the deployment guide, what is the default scenario used when no scenario is specified?");
    await page.locator('button[title="Send Question"]').click();
    const response = page.locator('div.chat-message.assistant').last();
    await expect(response).toBeVisible({ timeout: 90000 });
    const citation = response.locator('.citationContainer').first();
    await expect(citation).toBeVisible();
    await citation.click();
    await expect(page.getByText('Citations', { exact: true })).toBeVisible();
  });

  test("New chat starts a fresh conversation", async ({ page }) => {
    await page.goto('/');
    const question = page.locator('textarea[placeholder="Ask a question..."]');
    await question.fill('Temporary smoke test text');
    await page.locator('button[title="Create new Conversation"]').click();
    await expect(question).toHaveValue('');
    await expect(page.getByText('Start Chatting')).toBeVisible();
  });

  test("Show and hide chat history", async ({ page }) => {
    await createDisposableConversation(page);
    await page.getByRole('button', { name: 'Show Chat History' }).click();
    const item = page.getByLabel('chat history item').first();
    await expect(item).toBeVisible({ timeout: 30000 });
    await item.click();
    await expect(page.locator('div.chat-message').first()).toBeVisible();
  });

  test("Select conversation from history", async ({ page }) => {
    await createDisposableConversation(page);
    await page.getByRole('button', { name: 'Show Chat History' }).click();
    const item = page.getByLabel('chat history item').first();
    await expect(item).toBeVisible({ timeout: 30000 });
    await item.click();
    await expect(page.locator('div.chat-message').first()).toBeVisible();
  });

  test("Rename conversation", async ({ page }) => {
    await createDisposableConversation(page);
    await page.getByRole('button', { name: 'Show Chat History' }).click();
    const item = page.getByLabel('chat history item').first();
    await item.hover();
    await item.locator('button[title="Edit"]').click();
    const title = item.getByRole('textbox');
    await title.fill(`Smoke conversation ${Date.now()}`);
    await item.getByRole('button', { name: 'confirm new title' }).click();
    await expect(item.getByText(/Smoke conversation/)).toBeVisible();
  });

  test("Cancel rename conversation", async ({ page }) => {
    await createDisposableConversation(page);
    await page.getByRole('button', { name: 'Show Chat History' }).click();
    const item = page.getByLabel('chat history item').first();
    const originalTitle = await item.innerText();
    await item.hover();
    await item.locator('button[title="Edit"]').click();
    await item.getByRole('textbox').fill('Title that must not be saved');
    await item.getByRole('button', { name: 'cancel edit title' }).click();
    await expect(item).toContainText(originalTitle.trim());
  });

  test("Delete conversation", async ({ page }) => {
    await createDisposableConversation(page);
    await page.getByRole('button', { name: 'Show Chat History' }).click();
    const item = page.getByLabel('chat history item').first();
    await item.hover();
    await item.locator('button[title="Delete"]').click();
    const dialog = page.getByRole('dialog', { name: 'Are you sure you want to delete this item?' });
    await expect(dialog).toBeVisible();
    await dialog.getByRole('button', { name: 'Delete' }).click();
    await expect(item).toBeHidden();
  });

  test("Cancel delete conversation", async ({ page }) => {
    await createDisposableConversation(page);
    await page.getByRole('button', { name: 'Show Chat History' }).click();
    const item = page.getByLabel('chat history item').first();
    await item.hover();
    await item.locator('button[title="Delete"]').click();
    const dialog = page.getByRole('dialog', { name: 'Are you sure you want to delete this item?' });
    await dialog.getByRole('button', { name: 'Cancel' }).click();
    await expect(item).toBeVisible();
  });

  test("Clear all conversations", async ({ page }) => {
    test.skip(process.env.ALLOW_DESTRUCTIVE_SMOKE_TESTS !== 'true', 'Requires an isolated test identity');
    await createDisposableConversation(page);
    await page.getByRole('button', { name: 'Show Chat History' }).click();
    await page.getByRole('button', { name: 'clear all chat history' }).click();
    await page.getByText('Clear all chat history', { exact: true }).click();
    const dialog = page.getByRole('dialog', { name: 'Are you sure you want to clear all chat history?' });
    await expect(dialog).toBeVisible();
    await dialog.getByRole('button', { name: 'Clear All' }).click();
    await expect(page.getByLabel('chat history item')).toHaveCount(0);
  });

  test("Cancel clear all conversations", async ({ page }) => {
    await createDisposableConversation(page);
    await page.getByRole('button', { name: 'Show Chat History' }).click();
    const items = page.getByLabel('chat history item');
    const originalCount = await items.count();
    await page.getByRole('button', { name: 'clear all chat history' }).click();
    await page.getByText('Clear all chat history', { exact: true }).click();
    const dialog = page.getByRole('dialog', { name: 'Are you sure you want to clear all chat history?' });
    await dialog.getByRole('button', { name: 'Cancel' }).click();
    await expect(items).toHaveCount(originalCount);
  });

  test("Conversation persistence across reload", async ({ page }) => {
    await page.goto('/');
    const question = page.locator('textarea[placeholder="Ask a question..."]');
    await question.fill("Show the top 5 products by total quantity sold.");
    await page.locator('button[title="Send Question"]').click();
    await expect(page.locator('div.chat-message.assistant').last()).toBeVisible({ timeout: 90000 });
    await page.reload();
    await page.getByRole('button', { name: 'Show Chat History' }).click();
    await expect(page.getByLabel('chat history item').first()).toBeVisible({ timeout: 30000 });
  });

  test("Open chat history", async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Show Chat History' }).click();
    await expect(page.getByRole('region', { name: 'chat history panel' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Chat history' })).toBeVisible();
    await page.getByRole('button', { name: 'Hide Chat History' }).click();
    await expect(page.getByRole('region', { name: 'chat history panel' })).toBeHidden();
  });
});
