/**
 * 只读诊断：为什么某个 DSH 会话文件在 v3→v4 迁移时被拒绝。
 *
 * 不写盘、不改文件，只做三件事：
 *   1. 解压会话的 zstd 分帧，按行还原事件；
 *   2. 走 DSH 真实加载路径（catalog.createRestore + persistence.validateStoredEvents）复现报错；
 *   3. 单步重放「受保护系统头」状态机，指出是哪一个 seq 触发了拒绝。
 *
 * 用法：
 *   node tools/inspect-session-head.mjs "<session.v3.jsonl.zstd>"
 *   node tools/inspect-session-head.mjs "<某个会话目录或 sessions 根目录>"   # 批量只看结论
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
  console.error('用法: node tools/inspect-session-head.mjs <session.v3.jsonl.zstd | 目录>')
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

/** DSH 真实加载路径：v3→v4 迁移（含表面折叠与关系校验）+ 存储形状校验。 */
function verify(lines, id) {
  try {
    const header = JSON.parse(lines[0])
    const restore = catalog.createSessionFormatCatalogWithChildren([])
      .createRestore(header, { recovery: 'recoverable', validation: 'transformed' })
    for (let i = 1; i < lines.length; i += 1) restore.decodeRow(JSON.parse(lines[i]))
    const artifact = restore.finish()
    persistence.validateStoredEvents(
      { id, version: artifact.header.version, kind: 'jsonl', path: '' },
      (artifact.events ?? []).slice(),
      id,
    )
    return { ok: true, header, version: artifact.header.version }
  } catch (error) {
    return { ok: false, error: String(error.message) }
  }
}

/**
 * 单步重放 worker.cjs:10403-10425 的受保护系统头状态机。
 * @returns 触发拒绝的 seq（没有则为 null）
 */
function firstHeadViolation(events) {
  let hasSurface = false
  let head
  for (const event of events) {
    if (event.type === 'system/message') {
      const operation = event.surfaceOp
      if (hasSurface && head === undefined) {
        return { seq: event.seq, head, hasSurface, surfaceBefore: true }
      }
      if (operation === 'append') {
        if (!hasSurface) head = event.seq
      } else if (operation !== undefined && operation !== null && typeof operation === 'object') {
        if (operation.startSeq === head || operation.endSeq === head) head = event.seq
      }
    }
    if (SURFACE_TYPES.has(event.type)) hasSurface = true
  }
  return null
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
const detail = files.length === 1
console.log(`扫描 ${String(files.length)} 个会话文件（DSH_MODULES=${DSH_MODULES}）`)
for (const file of files) {
  const id = path.basename(path.dirname(file))
  const { lines, frames, undecodable } = readLines(file)
  const result = verify(lines, id)
  const sizeMb = (fs.statSync(file).size / 1048576).toFixed(2)
  console.log(`\n=== ${id} ===`)
  console.log(`  文件 ${file}`)
  console.log(`  ${sizeMb} MB · ${String(frames)} 帧 · ${String(lines.length)} 行 · 解压失败 ${String(undecodable)} 帧`)
  if (result.ok) {
    console.log(`  迁移校验：通过（v${String(result.version)}）`)
    continue
  }
  console.log(`  迁移校验：拒绝`)
  console.log(`  报错：${result.error}`)

  if (!detail) continue

  // 详细模式：把事件解析出来做单步重放
  const events = []
  for (let i = 1; i < lines.length; i += 1) {
    try {
      events.push(JSON.parse(lines[i]))
    } catch { /* 跳过坏行 */ }
  }
  console.log(`  事件 ${String(events.length)} 个（header: ${lines[0].slice(0, 200)}）`)
  console.log('  --- 前 12 个事件 ---')
  for (const event of events.slice(0, 12)) console.log(`    ${describe(event)}`)

  const violations = events.filter((e) => e.type === 'system/message')
  console.log(`  --- system/message 共 ${String(violations.length)} 个 ---`)
  for (const event of violations.slice(0, 12)) console.log(`    ${describe(event)}`)

  const violation = firstHeadViolation(events)
  console.log('  --- 受保护系统头状态机 ---')
  if (violation === null) {
    console.log('    未发现系统头违规（报错来自其它校验环节）')
  } else {
    console.log(`    首个违规：seq=${String(violation.seq)} —— 表面已开始但受保护头仍未建立，该 system/message 被拒`)
    const index = events.findIndex((e) => e.seq === violation.seq)
    const around = events.slice(Math.max(0, index - 3), index + 2)
    console.log('    现场事件：')
    for (const event of around) console.log(`      ${describe(event)}`)
  }
}
