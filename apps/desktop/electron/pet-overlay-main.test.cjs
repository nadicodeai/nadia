'use strict'

const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')

test('main process does not keep pet overlay window wiring', () => {
  const source = fs.readFileSync(path.join(__dirname, 'main.cjs'), 'utf8')

  assert.equal(source.includes('petOverlayWindow'), false)
})
