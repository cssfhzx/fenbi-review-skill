// 把粉笔解析结果归档到 kaogong-study-tracker
// 用法: node fb_archive.js <parsed.json> [--date 2026-11-04] [--analyses <analyses.json>] [--skip-stats]
//   --analyses   把错因分析 JSON 的 cause/tag/note/colloc/analysis 首句写进错题本，error_reason 不再留「未说明」
//   --skip-stats 只刷新 wrong_questions.json，不重复累加 daily 与 stats_cache（用于给已有条目回填字段）
const fs = require('fs');
const path = require('path');
const os = require('os');

const HOME = process.env.KAOGONG_TRACKER_HOME || path.join(os.homedir(), '.kaogong-study-tracker');
const DATA = process.env.KAOGONG_DATA_DIR || path.join(HOME, 'data');

const TYPE_TO_MODULE = {
  '资料分析': '资料分析',
  '数学运算': '数量关系',
  '逻辑判断': '判断推理',
  '图形推理': '判断推理',
  '类比推理': '判断推理',
  '定义判断': '判断推理',
  '逻辑填空': '言语理解',
  '片段阅读-中心理解': '言语理解',
  '片段阅读-意图判断': '言语理解',
  '片段阅读-细节判断': '言语理解',
  '标题填入': '言语理解',
  '语句排序': '言语理解',
  '语句填空': '言语理解',
  '语句表达-下文推断': '言语理解',
  '语句表达-前文推断': '言语理解',
  '常识判断': '常识判断',
};

function ensureDir(d) {
  if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true });
}

// 读取错因分析 JSON（键为题号）。文件不存在/损坏时给警告并返回 null，绝不静默退化成「未说明」
function loadAnalyses(p) {
  if (!p) return null;
  if (!fs.existsSync(p)) {
    console.warn(`[archive] 警告: --analyses 文件不存在: ${p}`);
    return null;
  }
  try {
    return JSON.parse(fs.readFileSync(p, 'utf-8'));
  } catch (e) {
    console.warn(`[archive] 警告: --analyses 解析失败: ${e.message}`);
    return null;
  }
}

function aFor(analyses, no) {
  if (!analyses) return null;
  return analyses[String(no)] || analyses[no] || null;
}

// 去掉 analyses 文本里残留的 markdown 加粗标记，避免 docx 里出现字面 **
function clean(s) {
  return String(s == null ? '' : s).replace(/\*\*/g, '');
}

// 把 cause/tag/note/colloc/analysis 写进一条错题记录；返回是否成功
function enrich(item, a) {
  if (!a) return false;
  item.error_reason = clean(a.cause) || item.error_reason || '未说明';
  if (a.tag) item.tag = clean(a.tag);
  if (a.note) item.note = clean(a.note);
  if (a.colloc) item.colloc = clean(Array.isArray(a.colloc) ? a.colloc.join('；') : a.colloc);
  const an = Array.isArray(a.analysis) ? a.analysis : [a.analysis];
  const first = an.filter(Boolean).join(' ').trim();
  if (first) item.analysis = clean(first).slice(0, 240);
  return true;
}

function main() {
  const args = process.argv.slice(2);
  if (!args[0]) {
    console.error('用法: node fb_archive.js <parsed.json> [--date YYYY-MM-DD] [--analyses <analyses.json>] [--skip-stats]');
    process.exit(1);
  }
  const jsonPath = args[0];
  let date = new Date().toISOString().slice(0, 10);
  const di = args.indexOf('--date');
  if (di >= 0 && args[di + 1]) date = args[di + 1];
  const ai = args.indexOf('--analyses');
  const analyses = loadAnalyses(ai >= 0 ? args[ai + 1] : null);
  const skipStats = args.includes('--skip-stats');

  const d = JSON.parse(fs.readFileSync(jsonPath, 'utf-8'));
  const qs = d.questions || [];
  const stats = d.stats || {};

  ensureDir(DATA);
  // dayDir 与 modules 一样必须在 if 之外：统计缓存段（第 3 步）也要用它
  const dayDir = path.join(DATA, 'daily');

  // 1. 每日记录（按模块聚合）。--skip-stats 时跳过写入，避免回填字段把成绩重复累加。
  // modules 必须在 if 之外计算：统计缓存段（第 3 步）也要用它。
  const modules = {};
  for (const q of qs) {
    const mod = TYPE_TO_MODULE[q.type] || '未分类';
    if (!modules[mod]) modules[mod] = { total: 0, right: 0, wrong: 0 };
    modules[mod].total += 1;
    if (q.right) modules[mod].right += 1;
    else modules[mod].wrong += 1;
  }
  for (const m of Object.values(modules)) {
    m.accuracy = m.total ? Math.round((m.right / m.total) * 1000) / 10 : 0;
  }

  if (!skipStats) {
  ensureDir(dayDir);
  const dayPath = path.join(dayDir, `${date}.json`);
  let day = {};
  if (fs.existsSync(dayPath)) {
    try { day = JSON.parse(fs.readFileSync(dayPath, 'utf-8')); } catch (_) { day = {}; }
  }
  day.date = date;
  day.skipped = false;
  day.modules = day.modules || {};
  for (const [mod, v] of Object.entries(modules)) {
    const prev = day.modules[mod] || { total: 0, right: 0, wrong: 0 };
    day.modules[mod] = {
      total: prev.total + v.total,
      right: prev.right + v.right,
      wrong: prev.wrong + v.wrong,
    };
    day.modules[mod].accuracy = day.modules[mod].total
      ? Math.round((day.modules[mod].right / day.modules[mod].total) * 1000) / 10 : 0;
  }
  day.note = `${path.basename(d.file)} ${stats.total}题 对${stats.right}错${stats.wrong} 正确率${stats.rate}%`;
  day.updated_at = new Date().toISOString();
  fs.writeFileSync(dayPath, JSON.stringify(day, null, 2), 'utf-8');
  console.log(`[archive] 每日记录: ${dayPath}`);
  } // end if (!skipStats)

  // 2. 错题本
  const wqPath = path.join(DATA, 'wrong_questions.json');
  let wq = [];
  if (fs.existsSync(wqPath)) {
    try { wq = JSON.parse(fs.readFileSync(wqPath, 'utf-8')); } catch (_) { wq = []; }
  }
  const added = [];
  const refreshed = [];
  const unmatched = [];
  const aByNo = new Map();
  if (analyses) {
    for (const [k, v] of Object.entries(analyses)) {
      if (k === '_plan' || !v || typeof v !== 'object') continue;
      aByNo.set(String(k), v);
    }
  }
  // 同一天可能做多套卷子，题号会重复，用「日期+来源文件名+题号」做唯一键
  const srcTag = path.basename(d.file).replace(/_parsed\.json$/, '').replace(/[^\w\u4e00-\u9fa5-]/g, '');
  for (const q of qs) {
    if (q.right !== false) continue;
    const id = `fb-${date}-${srcTag}-${q.no}`;
    const existing = wq.find(x => x.id === id);
    const a = aByNo.get(String(q.no)) || null;
    if (analyses && !a) unmatched.push(q.no);
    if (existing) {
      // 已存在的条目：只补/刷新分析字段，不动 date/module/status/created_at
      if (a && enrich(existing, a)) refreshed.push(id);
      continue;
    }
    const item = {
      id,
      date,
      module: TYPE_TO_MODULE[q.type] || '未分类',
      source: path.basename(d.file),
      question_no: q.no,
      stem: q.stem,
      options: q.options,
      my_answer: q.my,
      correct_answer: q.answer,
      error_reason: '未说明',
      status: '待二刷',
      created_at: new Date().toISOString(),
    };
    enrich(item, a);
    wq.push(item);
    added.push(id);
  }
  fs.writeFileSync(wqPath, JSON.stringify(wq, null, 2), 'utf-8');
  console.log(`[archive] 错题本: ${wqPath}  新增 ${added.length} 条，回填 ${refreshed.length} 条，共 ${wq.length} 条`);
  if (!analyses) {
    console.warn('[archive] 警告: 未提供 --analyses，error_reason 保留「未说明」。建议跑 fb_pipeline.py 生成 analyses JSON 后带上本参数。');
  } else if (unmatched.length) {
    console.warn(`[archive] 警告: ${unmatched.length} 道错题在 analyses JSON 中无对应项: Q${unmatched.join(' Q')}`);
  }

  // 3. 统计缓存（--skip-stats 时跳过，避免回填时重复累加）
  if (skipStats) return;
  const cachePath = path.join(DATA, 'stats_cache.json');
  let cache = { last_updated: date, total_days_studied: 0, streak: 0, module_accuracy: {} };
  if (fs.existsSync(cachePath)) {
    try { cache = JSON.parse(fs.readFileSync(cachePath, 'utf-8')); } catch (_) {}
  }
  cache.last_updated = date;
  cache.module_accuracy = cache.module_accuracy || {};
  for (const [mod, v] of Object.entries(modules)) {
    const prev = cache.module_accuracy[mod] || { total: 0, right: 0 };
    const t = prev.total + v.total;
    const r = prev.right + v.right;
    cache.module_accuracy[mod] = { total: t, right: r, accuracy: t ? Math.round((r / t) * 1000) / 10 : 0 };
  }
  const files = fs.readdirSync(dayDir).filter(f => /^\d{4}-\d{2}-\d{2}\.json$/.test(f));
  cache.total_days_studied = files.length;
  fs.writeFileSync(cachePath, JSON.stringify(cache, null, 2), 'utf-8');
  console.log(`[archive] 统计缓存: ${cachePath}  累计 ${cache.total_days_studied} 天`);
  console.log('[archive] 模块正确率:');
  for (const [m, v] of Object.entries(cache.module_accuracy)) {
    console.log(`  ${m}: ${v.right}/${v.total} = ${v.accuracy}%`);
  }
}

main();
