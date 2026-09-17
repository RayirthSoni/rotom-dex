import { expect, test } from '@playwright/test'
import { readStorage } from './helpers'

const KEY='test-visitor-key-not-real'
const answer = {game:{slug:'emerald'},snapshot_id:'test',coverage_status:'partial',coverage:[],assumptions:[],evidence:[],data:{version:2,games:['emerald'],prose:'In Emerald, Ralts has 25 base Attack.',abstained:false,facts:[],cards:[],recommendations:[],actions:[{kind:'mark_milestone',label:'Mark Stone Badge complete',payload:{milestone:'stone-badge'}}],references:[],assumptions:[],follow_ups:['What about Diamond?']}}
async function connect(page: import('@playwright/test').Page) {
  await page.route('**/api/chat/connect',route => route.fulfill({json:{connected:true}}))
  await page.getByRole('button',{name:'Connect Gemini',exact:true}).click()
  await page.getByLabel('Gemini API key', {exact:true}).fill(KEY)
  await page.getByRole('button',{name:'Connect',exact:true}).click()
  await expect(page.getByRole('button',{name:'Gemini connected',exact:true})).toBeVisible()
}

test('first visit has a composer without a playthrough',async({page}) => {
  await page.goto('/')
  await expect(page.getByRole('heading',{name:'A little guidance. A better adventure.'})).toBeVisible()
  await page.getByLabel('Ask Rotom a question').fill('Where can I catch Ralts in Emerald?')
  await page.getByRole('button',{name:'Ask Rotom ↗'}).click()
  await expect(page.getByLabel('Gemini API key', {exact:true})).toBeVisible()
  await expect(page.getByRole('status')).toContainText('Connect your Gemini key')
  await page.goto('/g/emerald/dex')
  await page.getByLabel('Search by name or number').fill('ralts')
  await expect(page.getByRole('link',{name:/Ralts/}).first()).toBeVisible()
})

test('streamed answer survives navigation and reload, but the key does not',async({page}) => {
  await page.goto('/')
  await connect(page)
  await page.route('**/api/v2/chat/stream',route => {
    expect(route.request().headers()['x-rotom-gemini-key']).toBe(KEY)
    expect(route.request().postData()).not.toContain(KEY)
    return route.fulfill({contentType:'text/event-stream',body:`event: progress\ndata: {"message":"Checking game data…"}\n\nevent: answer\ndata: ${JSON.stringify(answer)}\n\nevent: done\ndata: {}\n\n`})
  })
  await page.getByLabel('Ask Rotom a question').fill('What are Ralts stats in Emerald?')
  await page.getByRole('button',{name:'Ask Rotom ↗'}).click()
  await expect(page.getByTestId('chat-answer')).toContainText('25 base Attack')
  await page.getByRole('button',{name:'Mark Stone Badge complete'}).click()
  await page.getByRole('link',{name:'Ask',exact:true}).click()
  await expect(page.getByTestId('chat-answer')).toContainText('25 base Attack')
  await page.reload()
  await expect(page.getByTestId('chat-answer')).toContainText('25 base Attack')
  await expect(page.getByRole('button',{name:'Connect Gemini',exact:true})).toBeVisible()
  const saved=await page.evaluate(() => JSON.stringify({...localStorage}))
  expect(saved).not.toContain(KEY)
  // Applying an old action twice is idempotent across reloads.
  await page.getByRole('button',{name:'Mark Stone Badge complete'}).click()
  const progress=await readStorage(page)
  expect(Object.values(progress.playthroughs).map(p=>p.completedMilestones)).toEqual([['stone-badge']])
})

test('quota errors are recoverable and retry is available',async({page}) => {
  await page.goto('/')
  await connect(page)
  await page.route('**/api/v2/chat/stream',route => route.fulfill({status:429,json:{detail:'Gemini quota reached. Try again later.'}}))
  await page.getByLabel('Ask Rotom a question').fill('Find Ralts in Emerald')
  await page.getByRole('button',{name:'Ask Rotom ↗'}).click()
  await expect(page.getByRole('alert')).toContainText('quota reached')
  await expect(page.getByRole('button',{name:'Retry question'})).toBeVisible()
})

test('keyboard submission and multiline input work',async({page}) => {
  await page.goto('/')
  const composer=page.getByLabel('Ask Rotom a question')
  await composer.fill('First line')
  await composer.press('Shift+Enter')
  await expect(composer).toHaveValue('First line\n')
  await composer.press('Enter')
  await expect(page.getByLabel('Gemini API key',{exact:true})).toBeVisible()
})

test('choosing and clearing a game updates one conversation',async({page}) => {
  await page.goto('/')
  const selector=page.getByLabel('Game for this conversation')
  await selector.selectOption('emerald')
  await expect(selector).toHaveValue('emerald')
  await selector.selectOption('')
  await expect(selector).toHaveValue('')
  const saved=await page.evaluate(() => JSON.parse(localStorage.getItem('rotom-dex.conversations')!).state)
  expect(saved.conversations).toHaveLength(1)
  expect(saved.conversations[0].game).toBeNull()
})
