import { expect, test } from '@playwright/test'

test('launches a real evaluation and drills into persisted failure evidence', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'AgentGate 评估台' })).toBeVisible()
  await page.locator('.actions .el-select').click()
  await page.getByRole('option', { name: /风险版本/ }).click()
  await page.getByRole('button', { name: '立即评估' }).click()
  await expect(page.getByText('发布门槛未通过')).toBeVisible()
  await page.getByRole('button', { name: /高风险申请需要人工复核.*查看轨迹/ }).first().click()
  await expect(page.getByText('失败用例轨迹')).toBeVisible()
  await expect(page.getByText('approve_loan', { exact: true })).toBeVisible()
})
