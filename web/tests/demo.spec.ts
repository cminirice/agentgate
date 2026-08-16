import { expect, test } from '@playwright/test'

test('configures an evaluation and reports real persisted metrics and evidence', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '评估配置' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '结果报告' })).toBeVisible()
  await expect(page.getByText('Evaluators & Metrics')).toBeVisible()

  await page.getByTestId('agent-select').click()
  await page.getByRole('option', { name: /风险版本/ }).click()
  await page.getByRole('button', { name: /运行评估/ }).click()

  await expect(page.getByText('发布门槛未通过')).toBeVisible()
  await expect(page.getByTestId('metric-tool_accuracy')).toContainText('工具准确率')
  await expect(page.getByTestId('metric-tool_accuracy')).toContainText('0%')
  await page.getByRole('button', { name: /高风险申请需要人工复核.*查看轨迹/ }).first().click()
  await expect(page.getByText('失败用例轨迹')).toBeVisible()
  await expect(page.getByText('approve_loan', { exact: true })).toBeVisible()
})
