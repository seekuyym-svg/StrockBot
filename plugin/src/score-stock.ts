/**
 * stock-scorer —— 股票评分插件（DSH Plugin）
 *
 * 注册一个 `score_stocks` 工具：对单个或多个 A 股代码计算
 * 综合评分(0-100) + 优选分(0-25)，同时输出股票名称和所属行业。
 *
 * 架构：本插件只是薄壳 —— execute 时用 child_process 调用项目内的
 * Python 评分桥 `backtest/score_api.py`（复用现有 HistoricalStockScorer
 * 引擎：mootdx 本地通达信数据 / 腾讯 API 降级），解析 stdout JSON 后
 * 返回 Markdown 表格。评分逻辑不在此处复制，修改评分策略只需改 Python。
 *
 * 环境变量（可选）：
 *   STOCK_SCORE_PYTHON   Python 解释器路径，默认 "python"
 *   STOCK_SCORE_ROOT     项目根目录（含 config.yaml / local / backtest），
 *                        默认取本文件所在目录的上级上级（plugin/src -> 项目根）
 *
 * 挂载（cordis.yml，路径必须为绝对路径）：
 *   - insert:
 *     - id: stock-scorer
 *       name: '/abs/path/to/project/plugin/src/score-stock.ts'
 * 启动：pnpm dsh web --patch ./plugin/cordis.yml
 */

import type { Context } from '@deepseek-ai/cordis'
// 注意：dsh 0.1.0-rc.7 的 defineTool 在 @deepseek-ai/dsh-tools，不在 dsh-base（dsh-base 已为空垫片）
import { defineTool } from '@deepseek-ai/dsh-tools'
import { execFile } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

export const name = 'stock-scorer'
export const inject = ['tools'] // 声明需要 tools 服务

/** 单次评分超时（毫秒）。网络模式约 1-2 秒/只，30 只给足余量 */
const EXEC_TIMEOUT_MS = 180_000
/** 子进程 stdout 缓冲上限（JSON 输出可能到百 KB 级） */
const MAX_BUFFER = 10 * 1024 * 1024

function pythonPath(): string {
    return process.env.STOCK_SCORE_PYTHON || 'python'
}

function projectRoot(): string {
    if (process.env.STOCK_SCORE_ROOT) return process.env.STOCK_SCORE_ROOT
    // ESM 下没有 __dirname：用 import.meta.url 推导 <root>/plugin/src -> 项目根
    return path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
}

/** 调用 Python 评分桥，返回 stdout 原文 */
function runScoreApi(args: string[]): Promise<string> {
    return new Promise((resolve, reject) => {
        const script = path.join(projectRoot(), 'backtest', 'score_api.py')
        execFile(
            pythonPath(),
            [script, ...args],
            {
                cwd: projectRoot(),
                timeout: EXEC_TIMEOUT_MS,
                maxBuffer: MAX_BUFFER,
                // 强制子进程 Python 用 UTF-8 输出，避免 Windows GBK 导致中文乱码
                env: { ...process.env, PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8' },
            },
            (err, stdout, stderr) => {
                if (err) {
                    const detail = (stderr || '').trim().split('\n').slice(-5).join('\n')
                    if ((err as NodeJS.ErrnoException).code === 'ENOENT') {
                        reject(new Error(`未找到 Python 解释器 "${pythonPath()}"，请设置环境变量 STOCK_SCORE_PYTHON`))
                    } else if (err.killed) {
                        reject(new Error(`评分超时（>${EXEC_TIMEOUT_MS / 1000}s）或进程被终止`))
                    } else {
                        reject(new Error(`评分脚本执行失败（exit ${err.code}）:\n${detail || stdout}`))
                    }
                    return
                }
                resolve(stdout)
            },
        )
    })
}

/** 把评分 JSON 渲染成 Markdown 表格 */
function renderMarkdown(data: { date?: string; count?: number; results?: any[] }): string {
    const lines: string[] = []
    const results = data.results ?? []

    lines.push(`📅 分析日期：${data.date ?? '未知'} ｜ 共 ${results.length} 只`)
    lines.push('')
    lines.push('| 代码 | 名称 | 行业 | 综合评分 | 优选分 | 备注 |')
    lines.push('| --- | --- | --- | --- | --- | --- |')

    for (const r of results) {
        const name = r.name || r.code
        const industry = r.industry || '-'
        if (r.error && r.score === undefined) {
            lines.push(`| ${r.code} | ${name} | ${industry} | - | - | ⚠️ ${r.error} |`)
            continue
        }
        const score = Math.round(r.score)
        const pref = Math.round(r.pref_score)
        const tag = score <= 10 ? '⚠️ 可能超跌（综合分≤10）' : ''
        lines.push(`| ${r.code} | ${name} | ${industry} | ${score} | ${pref} | ${tag} |`)
    }

    lines.push('')
    lines.push('综合评分满分 100（量能/趋势/动量/形态/风险五因子），优选分满分 25（强势延续性五项评估）。')
    return lines.join('\n')
}

export function apply(ctx: Context) {
    ctx.tools.register(defineTool({
        name: 'score_stocks',
        description: '对单个或多个A股股票代码计算综合评分(0-100)与优选分(0-25)，同时输出股票名称和所属行业。' +
            '当用户询问某只或某几只股票的评分、技术面得分、当前强弱状态，或要求对若干代码批量打分时使用。' +
            '代码格式支持 sh.600519 / 600519 / 600519,000001 或空格分隔的多个代码。',
        parameters: {
            codes: {
                type: 'string',
                required: true,
                description: '股票代码列表，逗号或空格分隔，如 "600519,000001" 或 "sh.600519 sz.000001"',
            },
            date: {
                type: 'string',
                description: '分析日期 YYYY-MM-DD，默认最近交易日（今天是周末则取最后一个交易日）',
            },
            industry: {
                type: 'boolean',
                description: '是否查询所属行业（走东方财富接口，每只需约 0.3 秒），默认 true',
            },
        },
        output: {
            schema: {
                type: 'object',
                additionalProperties: false,
                properties: {
                    date: { type: 'string' },
                    count: { type: 'integer' },
                    results: {
                        type: 'array',
                        items: {
                            type: 'object',
                            // 条目字段不固定（成功含 score/pref_score，失败含 error），放行额外字段
                            additionalProperties: true,
                            properties: {
                                code: { type: 'string', required: true },
                                name: { type: 'string', required: true },
                            },
                        },
                    },
                },
            },
            render: (_args: any, value: any) => [{ type: 'text', text: renderMarkdown(value) }],
        },
        async execute(params: { codes: string; date?: string; industry?: boolean }) {
            if (!params.codes || !params.codes.trim()) {
                return { results: [{ code: '-', name: '-', error: '参数 codes 不能为空，请提供至少一个股票代码。' }] }
            }

            const args = ['--codes', params.codes]
            if (params.date) args.push('--date', params.date)
            if (params.industry === false) args.push('--no-industry')

            try {
                const stdout = await runScoreApi(args)
                // 防御：local/utils.py 的调试 print 可能混入 stdout，从第一个 { 开始解析 JSON
                const jsonText = stdout.slice(stdout.indexOf('{'))
                const data = JSON.parse(jsonText)
                if (data.error) {
                    return { results: [{ code: '-', name: '-', error: `评分脚本报错：${data.error}` }] }
                }
                return { date: data.date, count: data.count, results: data.results }
            } catch (e: any) {
                return { results: [{ code: '-', name: '-', error: String(e?.message || e) }] }
            }
        },
    }))

    console.log('[stock-scorer] plugin loaded!')
}
