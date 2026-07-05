'use strict'

const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')

test('desktop no longer bridges the VS Code Marketplace theme gallery', () => {
  const mainSource = fs.readFileSync(path.join(__dirname, 'main.cjs'), 'utf8')
  const preloadSource = fs.readFileSync(path.join(__dirname, 'preload.cjs'), 'utf8')

  assert.equal(mainSource.includes('vscode-marketplace'), false)
  assert.equal(mainSource.includes('vscode-theme'), false)
  assert.equal(preloadSource.includes('fetchMarketplace'), false)
  assert.equal(preloadSource.includes('searchMarketplace'), false)
  assert.equal(fs.existsSync(path.join(__dirname, 'vscode-marketplace.cjs')), false)
  assert.equal(fs.existsSync(path.join(__dirname, 'vscode-marketplace.test.cjs')), false)
})
