/**
 * 修复 + 预防 DSH 会话格式的「受保护系统头」问题（v3 / v4 日志）。
 *
 * 症状：
 *   历史加载失败：stored session "X" is corrupt: ... SessionFormatError:
 *   system/message requires a protected first surface head
 *
 * 成因（两个包联合作用）：
 *   1. 校验侧（dsh-session-persistence-jsonl/lib/worker.cjs:10403-10425 与 :11313）：
 *      「受保护头」只在某个 system/message 以 surfaceOp="append" 进入、且此刻表面仍为空时建立。
 *      从 reasonix 导入的 import-desktop-* 会话，表面节点 0 是导入插件写的环境变更通知
 *      （user/message），天生没有这个头；一旦日志里出现 system/message，整份文件就被判损坏。
 *   2. 写入侧（dsh-agent-loop/lib/index.js:264-270 SystemPromptProjection.project）：
 *      surface 上找不到存活的 system/message 节点时，**每一步都会追加一条新的系统提示**。
 *      所以哪怕把违规的那条删掉/降级（旧版脚本的做法），下一次运行必然再追加一条 —— 问题复发。
 *
 * 因此唯一稳定的修法是**让表面节点 0 真的是一条 system/message**：把已经在日志里的那条
 * 系统提示（或一条空头）连同它所在 turn 的 turn/start、step/start 一起挪到最前面，
 * 并相应重编号。装好头之后，写入侧永远能找到头、不会再追加，校验侧也不再报错。
 *
 * 用法：
 *   node tools\repair-surface-head.mjs "<会话文件或目录>"              # 预览（默认，不写盘）
 *   node tools\repair-surface-head.mjs "<会话文件或目录>" --apply      # 落盘，留 .headfix-bak 备份
 *   node tools\repair-surface-head.mjs "<会话文件或目录>" --preventive # 连「现在能打开但缺头」的也装头
 *   node tools\repair-surface-head.mjs "<会话文件或目录>" --apply --preventive --debug
 * 依赖 DSH 模块位置可用 DSH_MODULES 覆盖。
 */
import fs from 'node:fs'
import path from 'node:path'
import zlib from 'node:zlib'
import { randomUUID } from 'node:crypto'
import { pathToFileURL } from 'node:url'

const DSH_MODULES = process.env.DSH_MODULES
  ?? 'C:\\Users\\seeku\\AppData\\Roaming\\npm\\node_modules\\@deepseek-ai\\dsh\\node_modules'

const MAGIC = Buffer.from([0x28, 0xb5, 0x2f, 0xfd])
/** 与 worker.cjs 受保护头校验一致的表面事件类型集合。 */
const SURFACE_TYPES = new Set(['system/message', 'user/message', 'assistant/message', 'tool/result'])
/** 最近仍在写入的会话不动。 */
const ACTIVE_WINDOW_MS = 45 * 1000

const args = process.argv.slice(2)
const apply = args.includes('--apply')
const preventive = args.includes('--preventive')
const debug = args.includes('--debug')
const target = args.find((value) => !value.startsWith('-'))
if (target === undefined) {
  console.error('用法: node tools/repair-surface-head.mjs <会话文件或目录> [--apply] [--preventive] [--debug]')
  process.exit(2)
}

const catalog = await import(pathToFileURL(path.join(DSH_MODULES, '@deepseek-ai/dsh-session-format-catalog', 'lib', 'index.js')).href)
const persistence = await import(pathToFileURL(path.join(DSH_MODULES, '@deepseek-ai/dsh-session-persistence', 'lib', 'index.js')).href)

/** 按 zstd 魔数切帧后逐帧解压；保留帧原文。 */
function readFrames(file) {
  const buffer = fs.readFileSync(file)
  const positions = []
  let at = buffer.indexOf(MAGIC)
  while (at >= 0) {
    positions.push(at)
    at = buffer.indexOf(MAGIC, at + 4)
  }
  positions.push(buffer.length)
  const frames = []
  for (let i = 0; i < positions.length - 1; i += 1) {
    const raw = buffer.subarray(positions[i], positions[i + 1])
    let text = null
    try {
      text = zlib.zstdDecompressSync(raw).toString('utf8')
    } catch {
      text = null
    }
    frames.push({ raw, text })
  }
  return frames
}

function frameLines(frames) {
  const lines = []
  for (const frame of frames) {
    if (frame.text === null) continue
    const parts = frame.text.split('\n')
    if (parts.length > 0 && parts[parts.length - 1] === '') parts.pop()
    for (const line of parts) lines.push(line)
  }
  return lines
}

/** 第一帧必须恰好一行 header；其余行写成第二个帧。 */
function writeTwoFrames(file, lines) {
  const head = zlib.zstdCompressSync(Buffer.from(lines[0] + '\n', 'utf8'))
  const body = lines.length > 1
    ? zlib.zstdCompressSync(Buffer.from(lines.slice(1).join('\n') + '\n', 'utf8'))
    : Buffer.alloc(0)
  fs.writeFileSync(file, Buffer.concat([head, body]))
}

function checkFrameLayout(file) {
  const buffer = fs.readFileSync(file)
  const positions = []
  let at = buffer.indexOf(MAGIC)
  while (at >= 0) {
    positions.push(at)
    at = buffer.indexOf(MAGIC, at + 4)
  }
  positions.push(buffer.length)
  if (positions.length < 2) throw new Error('文件里没有 zstd 帧')
  const first = zlib.zstdDecompressSync(buffer.subarray(positions[0], positions[1]))
  const onlyOneLine = first.length > 0 && first[first.length - 1] === 10 && first.indexOf(10) === first.length - 1
  if (!onlyOneLine) throw new Error('第一帧不是恰好一行 header')
}

/** v4 已存储日志走 current；更早版本走 transformed（迁移产物路径）。 */
function validationFor(version) {
  return version >= 4 ? 'current' : 'transformed'
}

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

/** 单步重放受保护头状态机。 */
function analyzeHead(events) {
  let hasSurface = false
  let head
  let firstSurfaceSeq
  const violations = []
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
    if (SURFACE_TYPES.has(event.type)) {
      if (firstSurfaceSeq === undefined) firstSurfaceSeq = event.seq
      hasSurface = true
    }
  }
  return { violations, headSeq: head, firstSurfaceSeq }
}

/**
 * 规划「装头」：把首个表面事件之后的 turn/start、step/start，以及一条 system/message
 * 一起挪到最前面。已有可挪的 system/message 就搬它（真实系统提示，事件数不变）；
 * 否则合成一条空头（事件数 +1，写入侧下次运行会用真实提示替换它）。
 */
function planHead(events) {
  const firstSurfaceIdx = events.findIndex((event) => SURFACE_TYPES.has(event.type))
  if (firstSurfaceIdx < 0) return { error: '日志里没有表面事件' }
  const tsIdx = events.findIndex((event, index) => index > firstSurfaceIdx && event.type === 'turn/start')
  if (tsIdx < 0) return { error: '首个表面事件之后找不到 turn/start' }
  const ssIdx = events.findIndex((event, index) => index > tsIdx && event.type === 'step/start')
  if (ssIdx < 0) return { error: 'turn/start 之后找不到 step/start' }
  const sysIdx = events.findIndex((event) => event.type === 'system/message' && event.surfaceOp === 'append')
  return { firstSurfaceIdx, tsIdx, ssIdx, sysIdx }
}

function buildCandidate(events, plan, source) {
  const turnStart = JSON.parse(JSON.stringify(events[plan.tsIdx]))
  const stepStart = JSON.parse(JSON.stringify(events[plan.ssIdx]))
  const moved = plan.sysIdx >= 0
  const systemMessage = moved
    ? JSON.parse(JSON.stringify(events[plan.sysIdx]))
    : {
        type: 'system/message',
        seq: 0,
        time: turnStart.time,
        data: {
          turn: turnStart.data.turn,
          step: stepStart.data.step,
          message: {
            role: 'system',
            content: [{
              type: 'text',
              text: 'This session was imported from reasonix; its original system prompt was not recorded. '
                + 'This placeholder head satisfies the session format protected-system-head rule and will be '
                + 'replaced by the current rendered system prompt on the next turn.',
            }],
            source,
            id: randomUUID(),
          },
        },
        surfaceOp: 'append',
      }
  systemMessage.data = { ...systemMessage.data, turn: turnStart.data.turn, step: stepStart.data.step }

  const removed = new Set([plan.tsIdx, plan.ssIdx])
  if (moved) removed.add(plan.sysIdx)
  const pairs = [
    { event: turnStart, oldSeq: events[plan.tsIdx].seq },
    { event: stepStart, oldSeq: events[plan.ssIdx].seq },
    { event: systemMessage, oldSeq: moved ? events[plan.sysIdx].seq : undefined },
  ]
  for (let i = 0; i < events.length; i += 1) {
    if (removed.has(i)) continue
    pairs.push({ event: JSON.parse(JSON.stringify(events[i])), oldSeq: events[i].seq })
  }

  const oldToNew = new Map()
  pairs.forEach((pair, index) => {
    if (pair.oldSeq !== undefined) oldToNew.set(pair.oldSeq, index)
  })

  const mapSeq = (seq) => {
    const next = oldToNew.get(seq)
    if (next === undefined) throw new Error(`无法映射被引用的 seq ${String(seq)}`)
    return next
  }

  pairs.forEach((pair, index) => {
    const event = pair.event
    event.seq = index
    if (event.surfaceOp !== undefined && event.surfaceOp !== null && typeof event.surfaceOp === 'object') {
      event.surfaceOp = {
        op: 'replace',
        startSeq: mapSeq(event.surfaceOp.startSeq),
        endSeq: mapSeq(event.surfaceOp.endSeq),
      }
    }
    if (Array.isArray(event.sourceEventSeqs)) event.sourceEventSeqs = event.sourceEventSeqs.map(mapSeq)
    const data = event.data
    if (data !== null && typeof data === 'object') {
      if (typeof data.headerSeq === 'number') data.headerSeq = mapSeq(data.headerSeq)
      if (Array.isArray(data.shadowedSeqs)) data.shadowedSeqs = data.shadowedSeqs.map(mapSeq)
    }
  })

  return { events: pairs.map((pair) => pair.event), moved, oldToNew }
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
const now = Date.now()
let healthy = 0
let pending = 0
let fixed = 0
let dead = 0
let skipped = 0
for (const file of files) {
  const id = path.basename(path.dirname(file))
  const stats = fs.statSync(file)
  if (now - stats.mtimeMs < ACTIVE_WINDOW_MS) {
    skipped += 1
    console.log(`跳过 ${id} :: 最近 ${String(ACTIVE_WINDOW_MS / 1000)} 秒内仍在写入`)
    continue
  }
  const frames = readFrames(file)
  const lines = frameLines(frames)
  if (lines.length === 0) continue
  let version
  try {
    version = JSON.parse(lines[0]).version
  } catch {
    version = undefined
  }
  const validation = validationFor(version ?? 0)
  const before = verify(lines, id, validation)
  const events = []
  for (let i = 1; i < lines.length; i += 1) {
    try {
      events.push(JSON.parse(lines[i]))
    } catch { /* 交给校验报错 */ }
  }
  const head = analyzeHead(events)
  const broken = !before.ok
  const headClass = broken && /requires a protected first surface head/.test(before.error)
  const missingHead = head.headSeq === undefined && head.firstSurfaceSeq !== undefined
  if (broken && !headClass) {
    dead += 1
    console.log(`修不了 ${id} :: 非「受保护系统头」类损坏 —— ${before.error.slice(0, 140)}`)
    continue
  }
  if (!broken && !(preventive && missingHead)) {
    healthy += 1
    continue
  }
  if (!broken && (version ?? 0) < 4) {
    skipped += 1
    console.log(`跳过 ${id} :: v${String(version)} 预防性装头受 v3/v4 source 校验冲突限制（它迁移成 v4 后再修）`)
    continue
  }

  const plan = planHead(events)
  if (plan.error !== undefined) {
    dead += 1
    console.log(`修不了 ${id} :: ${plan.error}（报错：${before.ok ? '—' : before.error.slice(0, 120)}）`)
    continue
  }
  // 合成头时 source 形状随格式版本而异：v4 用 system-prompt，v3 行要求 plugin+plugin 名。
  const sources = [
    { kind: 'system-prompt' },
    { kind: 'plugin', plugin: 'repair-surface-head' },
  ]
  let chosen
  let lastError = ''
  for (const source of sources) {
    let candidate
    try {
      candidate = buildCandidate(events, plan, source)
    } catch (error) {
      lastError = String(error.message)
      continue
    }
    const candidateLines = [lines[0], ...candidate.events.map((event) => JSON.stringify(event))]
    const after = verify(candidateLines, id, validation)
    if (after.ok) {
      chosen = { candidate, candidateLines }
      break
    }
    lastError = after.error
  }
  if (chosen === undefined) {
    dead += 1
    console.log(`修不了 ${id} :: 装头后 ${validation} 校验仍失败 —— ${lastError.slice(0, 160)}`)
    if (debug) console.log(`    [debug] 事件 ${String(events.length)}`)
    continue
  }
  const { candidate, candidateLines } = chosen
  pending += 1
  const kind = candidate.moved ? '搬来已有系统提示' : '合成空头'
  const summary = `${broken ? '损坏' : '缺头'} · ${kind} · 事件 ${String(events.length)} → ${String(candidate.events.length)}`
  if (!apply) {
    console.log(`可修复 ${id}（${summary}，未落盘）`)
    if (debug) console.log(`    [debug] 头 seq=${String(candidate.events[2].seq)} turn=${String(candidate.events[2].data.turn)} step=${String(candidate.events[2].data.step)}`)
    continue
  }
  const backup = file + '.headfix-bak'
  if (!fs.existsSync(backup)) fs.copyFileSync(file, backup)
  writeTwoFrames(file, candidateLines)
  try {
    checkFrameLayout(file)
    const reread = verify(frameLines(readFrames(file)), id, validation)
    if (!reread.ok) throw new Error(reread.error)
  } catch (error) {
    fs.copyFileSync(backup, file)
    dead += 1
    console.log(`落盘后校验失败 ${id} :: ${String(error.message).slice(0, 160)}（已还原）`)
    continue
  }
  fixed += 1
  console.log(`已修复 ${id}（${summary}，备份 ${backup}）`)
}
console.log(`${apply ? '已落盘：' : '预览：'}扫描 ${String(files.length)} 个会话：正常 ${String(healthy)}`
  + ` · 可修复 ${String(pending)} · 已修复 ${String(fixed)} · 修不了 ${String(dead)} · 跳过 ${String(skipped)}`)
