// 把粉笔解析结果归档到 kaogong-study-tracker
// 用法: node fb_archive.js <parsed.json> [--date 2026-11-04]
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

function main() {
  const args = process.argv.slice(2);
  if (!args[0]) {
    console.error('用法: node fb_archive.js <parsed.json> [--date YYYY-MM-DD]');
    process.exit(1);
  }
  const jsonPath = args[0];
  let date = new Date().toISOString().slice(0, 10);
  const di = args.indexOf('--date');
  if (di >= 0 && args[di + 1]) date = args[di + 1];

  const d = JSON.parse(fs.readFileSync(jsonPath, 'utf-8'));
  const qs = d.questions || [];
  const stats = d.stats || {};

  ensureDir(DATA);

  // 1. 每日记录（按模块聚合）
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

  const dayDir = path.join(DATA, 'daily');
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

  // 2. 错题本
  const wqPath = path.join(DATA, 'wrong_questions.json');
  let wq = [];
  if (fs.existsSync(wqPath)) {
    try { wq = JSON.parse(fs.readFileSync(wqPath, 'utf-8')); } catch (_) { wq = []; }
  }
  const added = [];
  // 同一天可能做多套卷子，题号会重复，用「日期+来源文件名+题号」做唯一键
  const srcTag = path.basename(d.file).replace(/_parsed\.json$/, '').replace(/[^\w\u4e00-\u9fa5-]/g, '');
  for (const q of qs) {
    if (q.right !== false) continue;
    const id = `fb-${date}-${srcTag}-${q.no}`;
    if (wq.some(x => x.id === id)) continue;
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
    wq.push(item);
    added.push(id);
  }
  fs.writeFileSync(wqPath, JSON.stringify(wq, null, 2), 'utf-8');
  console.log(`[archive] 错题本: ${wqPath}  新增 ${added.length} 条，共 ${wq.length} 条`);

  // 3. 统计缓存
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
