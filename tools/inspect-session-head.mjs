/**
 * 只读诊断：为什么某个 DSH 会话文件加载失败 / 迁移被拒绝。
 *
 * 不写盘、不改文件，只做三件事：
 *   1. 解压会话的 zstd 分帧，按行还原事件；
 *   2. 按 DSH 的两条真实校验路径各跑一遍并复现报错：
 *        validation="current"     —— 读「已存储日志」用的路径（**v4 文件走这条**）
 *        validation="transformed" —— 迁移产物校验用的路径（v3 文件走这条）
 *   3. 单步重放「受保护系统头」状态机，指出是哪一个 seq 触发了拒绝。
 *
 * ★ 关键教训：v4 文件必须用 current 校验才等价于 DSH 的真实加载路径。
 *   只用 transformed 会把损坏的 v4 文件误判为「通过」（v4→v4 无迁移，transformed 直接放行）。
 *
 * 用法：
 *   node tools/inspect-session-head.mjs "<session.v3.jsonl.zstd | session.v4.jsonl.zstd | 目录>"
 * 依赖 DSH 模块位置可用 DSH_MODULES 覆盖。
 */
import fs from 'node:fs'
import path from 'node:path'
import zlib from 'node:zlib'
import { pathToFileURL } from 'node:url'

const DSH_MODULES = process.env.DSH_MODULES
  ?? 'C:\\Users\\seeku\\AppData\\Roaming\\npm\\node_modules\\@deepseek-ai\\dsh\\node_modules'

const MAGIC = Buffer.from([0x28, 0xb5, 0x2f, 0xfd])
/** 与 worker.cjs 中受保护头校验使用的 SURFACE_TYPES 一致。 */
const SURFACE_TYPES = new Set(['system/message', 'user/message', 'assistant/message', 'tool/result'])

const target = process.argv[2]
if (target === undefined) {
  console.error('用法: node tools/inspect-session-head.mjs <session.*.jsonl.zstd | 目录>')
  process.exit(2)
}

const catalog = await import(pathToFileURL(path.join(DSH_MODULES, '@deepseek-ai/dsh-session-format-catalog', 'lib', 'index.js')).href)
const persistence = await import(pathToFileURL(path.join(DSH_MODULES, '@deepseek-ai/dsh-session-persistence', 'lib', 'index.js')).href)

/** 按 zstd 魔数切帧并逐帧解压，返回摊平后的行。 */
function readLines(file) {
  const buffer = fs.readFileSync(file)
  const positions = []
  let at = buffer.indexOf(MAGIC)
  while (at >= 0) {
    positions.push(at)
    at = buffer.indexOf(MAGIC, at + 4)
  }
  positions.push(buffer.length)
  const lines = []
  let frames = 0
  let undecodable = 0
  for (let i = 0; i < positions.length - 1; i += 1) {
    let text
    try {
      text = zlib.zstdDecompressSync(buffer.subarray(positions[i], positions[i + 1])).toString('utf8')
    } catch {
      undecodable += 1
      continue
    }
    frames += 1
    const parts = text.split('\n')
    if (parts.length > 0 && parts[parts.length - 1] === '') parts.pop()
    for (const line of parts) lines.push(line)
  }
  return { lines, frames, undecodable }
}

/** 走 DSH 真实加载路径；validation 取 "current" 或 "transformed"。 */
function verify(lines, id, validation) {
  try {
    const header = JSON.parse(lines[0])
    const restore = catalog.createSessionFormatCatalogWithChildren([])
      .createRestore(header, { recovery: 'recoverable', validation })
    for (let i = 1; i < lines.length; i += 1) restore.decodeRow(JSON.parse(lines[i]))
    const artifact = restore.finish()
    persistence.validateStoredEvents(
      { id, version: artifact.header.version, kind: 'jsonl', path: '' },
      (artifact.events ?? []).slice(),
      id,
    )
    return { ok: true, version: artifact.header.version }
  } catch (error) {
    return { ok: false, error: String(error.message) }
  }
}

/**
 * 单步重放受保护系统头状态机（worker.cjs:10403-10425 与 :11313 同源）。
 * @returns 触发拒绝的 seq 列表
 */
function headViolationSeqs(events) {
  const violations = []
  let hasSurface = false
  let head
  for (const event of events) {
    if (event.type === 'system/message') {
      const operation = event.surfaceOp
      if (hasSurface && head === undefined) violations.push(event.seq)
      else if (operation === 'append') {
        if (!hasSurface) head = event.seq
      } else if (operation !== undefined && operation !== null && typeof operation === 'object') {
        if (operation.startSeq === head || operation.endSeq === head) head = event.seq
      }
    }
    if (SURFACE_TYPES.has(event.type)) hasSurface = true
  }
  return violations
}

function describe(event) {
  const data = event.data !== null && typeof event.data === 'object' ? event.data : {}
  const op = event.surfaceOp
  const opText = op === undefined
    ? ''
    : op === 'append' ? ' surfaceOp=append' : ` surfaceOp=replace(${op.startSeq}..${op.endSeq})`
  let extra = ''
  if (event.type === 'turn/start') extra = ` turn=${data.turn}`
  else if (event.type === 'step/start' || event.type === 'step/end') extra = ` turn=${data.turn} step=${data.step}`
  if (SURFACE_TYPES.has(event.type)) extra += ` turn=${data.turn} step=${data.step}`
  if (event.type === 'system/message' || event.type === 'user/message' || event.type === 'assistant/message') {
    if (typeof data.role === 'string') extra += ` role=${data.role}`
    if (data.message !== null && typeof data.message === 'object' && typeof data.message.role === 'string') extra += ` message.role=${data.message.role}`
  }
  return `seq=${String(event.seq)} type=${event.type}${opText}${extra}`
}

function walk(target) {
  const stats = fs.statSync(target)
  if (stats.isFile()) return [target]
  const found = []
  for (const entry of fs.readdirSync(target, { withFileTypes: true })) {
    const full = path.join(target, entry.name)
    if (entry.isDirectory()) found.push(...walk(full))
    else if (entry.isFile() && entry.name.endsWith('.jsonl.zstd')) found.push(full)
  }
  return found
}

const files = walk(target)
const forceDetail = process.argv.includes('--dump')
const detail = files.length === 1 || forceDetail
console.log(`扫描 ${String(files.length)} 个会话文件（DSH_MODULES=${DSH_MODULES}）`)
for (const file of files) {
  const id = path.basename(path.dirname(file))
  const { lines, frames, undecodable } = readLines(file)
  let version
  try {
    version = JSON.parse(lines[0]).version
  } catch {
    version = '?'
  }
  const asCurrent = verify(lines, id, 'current')
  const asTransformed = verify(lines, id, 'transformed')
  const sizeMb = (fs.statSync(file).size / 1048576).toFixed(2)
  console.log(`\n=== ${id} ===`)
  console.log(`  文件 ${file}`)
  console.log(`  ${sizeMb} MB · v${String(version)} · ${String(frames)} 帧 · ${String(lines.length)} 行 · 解压失败 ${String(undecodable)} 帧 · 判定 ${asCurrent.ok ? '正常' : '损坏'}`)
  console.log(`  current 校验（已存储日志的真实路径）：${asCurrent.ok ? '通过' : `拒绝 —— ${asCurrent.error}`}`)
  console.log(`  transformed 校验（迁移产物路径）：${asTransformed.ok ? '通过' : `拒绝 —— ${asTransformed.error}`}`)

  if (asCurrent.ok && asTransformed.ok && !forceDetail) continue

  const events = []
  for (let i = 1; i < lines.length; i += 1) {
    try {
      events.push(JSON.parse(lines[i]))
    } catch { /* 跳过坏行 */ }
  }

  if (!detail) {
    const violations = headViolationSeqs(events)
    if (violations.length > 0) console.log(`  受保护头违规 seq：${violations.slice(0, 10).join(', ')}`)
    continue
  }

  const rawWanted = (process.argv.find((arg) => arg.startsWith('--raw=')) ?? '').slice('--raw='.length)
  if (rawWanted !== '') {
    const wanted = Number(rawWanted)
    for (const event of events) if (event.seq === wanted) {
      const raw = JSON.stringify(event)
      console.log(`  RAW seq=${rawWanted} (${String(raw.length)} 字符): ${raw.slice(0, 700)}`)
      const message = event.data !== null && typeof event.data === 'object' ? event.data.message : undefined
      if (message !== null && typeof message === 'object') {
        console.log(`  RAW-META keys=${Object.keys(message).join(',')} id=${String(message.id)} source=${JSON.stringify(message.source)}`)
      }
    }
  }

  const histogram = new Map()
  for (const event of events) histogram.set(event.type, (histogram.get(event.type) ?? 0) + 1)
  const watched = [...histogram.entries()]
    .filter(([type]) => type.includes('orphan') || type === 'system/message')
    .map(([type, count]) => `${type}×${String(count)}`)
  console.log(`  事件 ${String(events.length)} 个 · 关注类型：${watched.length > 0 ? watched.join(' · ') : '（无 system/message、无 orphan）'}`)
  console.log('  --- 前 12 个事件 ---')
  for (const event of events.slice(0, 12)) console.log(`    ${describe(event)}`)

  const systems = events.filter((event) => event.type === 'system/message')
  console.log(`  --- system/message 共 ${String(systems.length)} 个 ---`)
  for (const event of systems.slice(0, 20)) console.log(`    ${describe(event)}`)

  const violations = headViolationSeqs(events)
  console.log('  --- 受保护系统头状态机 ---')
  if (violations.length === 0) {
    console.log('    未发现系统头违规（报错来自其它校验环节）')
  } else {
    console.log(`    违规 seq：${violations.join(', ')} —— 表面已开始但受保护头仍未建立`)
    for (const seq of violations.slice(0, 3)) {
      const index = events.findIndex((event) => event.seq === seq)
      console.log(`    seq=${String(seq)} 现场：`)
      for (const event of events.slice(Math.max(0, index - 2), index + 2)) console.log(`      ${describe(event)}`)
    }
  }
}
