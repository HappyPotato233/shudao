import { chromium } from 'playwright-core';

const browser = await chromium.launch({ executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [];
page.on('pageerror', e => errors.push('PAGEERROR: ' + e.message));

await page.goto('http://localhost:5173/login', { waitUntil: 'networkidle' });
await page.fill('input[placeholder="用户名"]', 'admin');
await page.fill('input[placeholder="密码"]', 'Abc@123456');
await page.click('button:has-text("登录")');
await page.waitForTimeout(3000);

// 进入 AI 问答
await page.click('text=AI 智能问答');
await page.waitForTimeout(2500);

// 验证复选框存在
const checkboxCount = await page.locator('.history-item .el-checkbox').count();
console.log('历史记录复选框数量:', checkboxCount);

// 验证单条删除按钮（hover 后出现，但 DOM 中存在）
const deleteBtnCount = await page.locator('.history-item .item-delete').count();
console.log('单条删除按钮数量:', deleteBtnCount);

// 选中第一个复选框
await page.locator('.history-item .el-checkbox').first().click();
await page.waitForTimeout(800);

// 验证批量删除按钮出现
const batchText = await page.evaluate(() => document.body.innerText);
console.log('选中后出现批量删除按钮:', batchText.includes('删除(1)'));

// 选中第二个复选框
await page.locator('.history-item .el-checkbox').nth(1).click();
await page.waitForTimeout(800);
const batchText2 = await page.evaluate(() => document.body.innerText);
console.log('选中两个后按钮显示删除(2):', batchText2.includes('删除(2)'));

await page.screenshot({ path: 'ai-delete-check.png' });
console.log('ERRORS:', errors.join('\n') || '无');
await browser.close();
console.log('done');
