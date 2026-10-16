/**
 * 修复「受保护系统头」类损坏导致的会话打不开（v3 日志，DSH 0.1.7+/v4 迁移拒绝）。
 *
 * 报错形态：
 *   Session migration from v3 to v4 refuses the transformed artifact:
 *   system/message requires a protected first surface head
 *
 * 成因（worker.cjs:10403-10425）：只有当某个 system/message 以 surfaceOp="append"
 * 进入、且此刻表面还没有任何事件时，它才被登记为受保护头 head。从 reasonix 导入的
 * import-desktop-* 会话，表面节点 0 是用户消息，系统提示被记在很靠后的 seq 上
 * （首次在 DSH 里继续该会话时由循环追加），于是 v4 迁移在读到那个 system/message
 * 时发现「表面已开始、受保护头仍空缺」，直接拒绝整个会话。
 *
 * 修法：把这类 system/message 降级为**未知可忽略事件**（保留 seq/time/载荷/坐标，
 * 只改 type 并打上 ignorable: true）。依据 worker.cjs:2677-2692 的 surfaceOpOf：
 * 未知类型 + ignorable === true 时，事件保留不透明元数据、但不参与表面折叠 —— 即
 * 迁移不再对它做关系校验，对话正文一个字节不丢，代价是这条旧系统提示不再进入模型
 * 可见上下文（它本来就是旧会话的运行期产物，而非用户数据）。
 *
 * 用法：
 *   node tools/repair-surface-head.mjs "<会话文件或目录>"            # 预览，不写盘（默认）
 *   node tools/repair-surface-head.mjs "<会话文件或目录>" --apply    # 落盘，留 .head-repair-bak 备份
 *   node tools/repair-surface-head.mjs "<会话文件或目录>" --apply --debug
 * 依赖 DSH 模块位置可用 DSH_MODULES 覆盖。
 */
import fs from 'node:fs'
import path from 'node:path'
import zlib from 'node:zlib'
import { pathToFileURL } from 'node:url'

const DSH_MODULES = process.env.DSH_MODULES
  ?? 'C:\\Users\\seeku\\AppData\\Roaming\\npm\\node_modules\\@deepseek-ai\\dsh\\node_modules'

const MAGIC = Buffer.from([0x28, 0xb5, 0x2f, 0xfd])
/** 降级后的类型名：必须不是 DSH 已知类型，且带 ignorable: true。 */
const ORPHAN_TYPE = 'repair-surface-head-orphan'
/** 与 worker.cjs 受保护头校验一致的表面事件类型集合。 */
const SURFACE_TYPES = new Set(['system/message', 'user/message', 'assistant/message', 'tool/result'])
/** 最近仍在写入的会话不动（与 community 工具同样的活动窗口）。 */
const ACTIVE_WINDOW_MS = 45 * 1000
const MAX_ROUNDS = 10

const args = process.argv.slice(2)
const apply = args.includes('--apply')
const debug = args.includes('--debug')
const target = args.find((value) => !value.startsWith('-'))
if (target === undefined) {
  console.error('用法: node tools/repair-surface-head.mjs <会话文件或目录> [--apply] [--debug]')
  process.exit(2)
}

const catalog = await import(pathToFileURL(path.join(DSH_MODULES, '@deepseek-ai/dsh-session-format-catalog', 'lib', 'index.js')).href)
const persistence = await import(pathToFileURL(path.join(DSH_MODULES, '@deepseek-ai/dsh-session-persistence', 'lib', 'index.js')).href)

/** 按 zstd 魔数切帧后逐帧解压；保留帧边界，落盘时只重写内容变化的帧。 */
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
    frames.push({ raw, text, changed: false })
  }
  return frames
}

function writeFrames(file, frames) {
  const parts = frames.map((frame) => {
    if (frame.text === null) return frame.raw
    return frame.changed === true ? zlib.zstdCompressSync(Buffer.from(frame.text, 'utf8')) : frame.raw
  })
  fs.writeFileSync(file, Buffer.concat(parts))
}

/** 把帧里的行摊平成带归属的条目，改完能原样落回各自的帧。 */
function flatten(frames) {
  const entries = []
  for (const frame of frames) {
    if (frame.text === null) continue
    const parts = frame.text.split('\n')
    if (parts.length > 0 && parts[parts.length - 1] === '') parts.pop()
    for (const line of parts) entries.push({ frame, line })
  }
  return entries
}

function commit(entries) {
  for (const entry of entries) {
    const frame = entry.frame
    const own = entries.filter((candidate) => candidate.frame === frame).map((candidate) => candidate.line)
    if (own.length === 0) continue
    const next = own.join('\n') + '\n'
    if (next !== frame.text) {
      frame.text = next
      frame.changed = true
    }
  }
}

function linesOf(entries) {
  return entries.map((entry) => entry.line)
}

/** 走 DSH 真实加载路径：v3→v4 迁移 + 存储形状校验。 */
function verify(lines, id) {
  try {
    const header = JSON.parse(lines[0])
    if (header.version !== 3) return { ok: true, skippedVersion: true }
    const restore = catalog.createSessionFormatCatalogWithChildren([])
      .createRestore(header, { recovery: 'recoverable', validation: 'transformed' })
    for (let i = 1; i < lines.length; i += 1) restore.decodeRow(JSON.parse(lines[i]))
    const artifact = restore.finish()
    persistence.validateStoredEvents(
      { id, version: artifact.header.version, kind: 'jsonl', path: '' },
      (artifact.events ?? []).slice(),
      id,
    )
    return { ok: true }
  } catch (error) {
    return { ok: false, error: String(error.message) }
  }
}

/** 第一帧必须恰好一行 header。 */
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

/** 单步重放受保护系统头状态机，返回所有触发拒绝的 seq。 */
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

/** 降级变体 A：保留不透明元数据（surfaceOp/sourceEventSeqs）。 */
function toOrphanKeepingMetadata(event) {
  return Object.assign({}, event, { type: ORPHAN_TYPE, ignorable: true })
}

/** 降级变体 B：连表面元数据一起去掉。 */
function toOrphanStrippingMetadata(event) {
  const next = Object.assign({}, event, { type: ORPHAN_TYPE, ignorable: true })
  delete next.surfaceOp
  delete next.sourceEventSeqs
  return next
}

function repairEntries(entries, id) {
  const seen = new Set()
  for (let round = 0; round < MAX_ROUNDS; round += 1) {
    const result = verify(linesOf(entries), id)
    if (result.ok) return { ok: true, touched: seen.size }
    if (!/requires a protected first surface head/.test(result.error)) {
      return { ok: false, error: result.error, touched: seen.size, reason: '非受保护系统头类损坏' }
    }
    const events = []
    for (let i = 1; i < entries.length; i += 1) {
      try {
        events.push(JSON.parse(entries[i].line))
      } catch { /* 坏行留给校验报错 */ }
    }
    const targets = headViolationSeqs(events).filter((seq) => !seen.has(seq))
    if (targets.length === 0) {
      return { ok: false, error: result.error, touched: seen.size, reason: '找不到可降级的 system/message' }
    }
    for (const seq of targets) {
      const index = entries.findIndex((entry, i) => i > 0 && (() => {
        try {
          return JSON.parse(entry.line).seq === seq
        } catch {
          return false
        }
      })())
      if (index < 0) continue
      const event = JSON.parse(entries[index].line)
      const keep = toOrphanKeepingMetadata(event)
      entries[index].line = JSON.stringify(keep)
      if (verify(linesOf(entries), id).ok) {
        seen.add(seq)
        if (debug) console.log(`    [debug] seq=${String(seq)} 降级（保留元数据）后校验通过`)
        break
      }
      entries[index].line = JSON.stringify(toOrphanStrippingMetadata(event))
      seen.add(seq)
      if (debug) console.log(`    [debug] seq=${String(seq)} 降级（去掉表面元数据）`)
    }
  }
  const result = verify(linesOf(entries), id)
  return result.ok
    ? { ok: true, touched: seen.size }
    : { ok: false, error: result.error, touched: seen.size, reason: '超过最大轮次' }
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
let repairable = 0
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
  const entries = flatten(frames)
  if (entries.length === 0) continue
  const before = verify(linesOf(entries), id)
  if (before.ok) {
    healthy += 1
    continue
  }
  const repaired = repairEntries(entries, id)
  if (!repaired.ok) {
    dead += 1
    console.log(`修不了 ${id} :: [${String(repaired.reason)}] ${String(repaired.error).slice(0, 160)}`)
    continue
  }
  repairable += 1
  if (!apply) {
    console.log(`可修复 ${id}（降级 ${String(repaired.touched)} 个 system/message，未落盘）`)
    continue
  }
  const backup = file + '.head-repair-bak'
  if (!fs.existsSync(backup)) fs.copyFileSync(file, backup)
  commit(entries)
  writeFrames(file, frames)
  try {
    checkFrameLayout(file)
    const after = verify(linesOf(flatten(readFrames(file))), id)
    if (!after.ok) throw new Error(String(after.error))
  } catch (error) {
    fs.copyFileSync(backup, file)
    dead += 1
    console.log(`落盘后校验失败 ${id} :: ${String(error.message).slice(0, 160)}（已从备份还原）`)
    continue
  }
  fixed += 1
  console.log(`已修复 ${id}（降级 ${String(repaired.touched)} 个 system/message，备份 ${backup}）`)
}
console.log(`${apply ? '已落盘：' : '预览：'}扫描 ${String(files.length)} 个会话：正常 ${String(healthy)}`
  + ` · 可修复 ${String(repairable)} · 已修复 ${String(fixed)} · 修不了 ${String(dead)} · 跳过 ${String(skipped)}`)
