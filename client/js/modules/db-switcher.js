// db-switcher.js · 顶部数据库下拉(2026-07-24 加, 2026-08-17 扩展)
// 改前必读:本文件管顶部 #db-switcher 和 #canvas-db-switcher 两个下拉
// 职责:加载 DB 列表 + 当前激活 + 切库 + emit bus 事件
//
// 2026-08-17 加:画布 DB 切换(独立维度)
//   顶部并排放 2 个下拉: 🎨 图片库(原 db-switcher) | 🎯 画布库(新)
//   各管各的,后端 /api/db 用 type=image/canvas 区分
import { bus } from '../core/events.js';
import { $, el, toast } from '../core/dom.js';
import * as api from '../api.js';

let _picSelectEl = null;
let _canvasSelectEl = null;
let _picInfoEl = null;
let _canvasInfoEl = null;
let _currentPicId = null;
let _currentCanvasId = null;
let _picDatabases = [];
let _canvasDatabases = [];

const LS_PIC = 'canvasweb.activeDbId';
const LS_CANVAS = 'canvasweb.activeCanvasDbId';

export async function init() {
  _picSelectEl = document.getElementById('db-switcher');
  _canvasSelectEl = document.getElementById('canvas-db-switcher');
  _picInfoEl = document.getElementById('db-info');
  _canvasInfoEl = document.getElementById('canvas-db-info');
  // 任一不存在就跳过(HTML 没装对应 UI)
  if (!_picSelectEl && !_canvasSelectEl) return;

  // 并行加载两类 DB
  await Promise.all([_loadPic(), _loadCanvas()]);

  // 图片库切换监听
  if (_picSelectEl) {
    _picSelectEl.addEventListener('change', async (e) => {
      const newId = e.target.value;
      if (newId === _currentPicId) return;
      await _switchPic(newId);
    });
    // 监听后端事件(其他 tab 切换时同步)
    bus.on('db:switched', ({ id, name }) => {
      if (id === _currentPicId) return;
      _currentPicId = id;
      _picSelectEl.value = id;
      _renderPicInfo();
    });
  }

  // 画布库切换监听(2026-08-17 加)
  if (_canvasSelectEl) {
    _canvasSelectEl.addEventListener('change', async (e) => {
      const newId = e.target.value;
      if (newId === _currentCanvasId) return;
      await _switchCanvas(newId);
    });
    bus.on('canvas-db:switched', ({ id, name }) => {
      if (id === _currentCanvasId) return;
      _currentCanvasId = id;
      _canvasSelectEl.value = id;
      _renderCanvasInfo();
    });
  }
}

// ===== 图片库 =====
async function _loadPic() {
  if (!_picSelectEl) return;
  try {
    const data = await api.getDatabases();
    _picDatabases = data.databases || [];
    _currentPicId = data.active_id;
    _renderPicOptions();
    _renderPicInfo();
  } catch (e) { console.warn('[db-switcher] pic load failed', e); }
}

async function _switchPic(dbId) {
  try {
    const resp = await api.switchDatabase(dbId);
    _currentPicId = resp.active_id;
    _renderPicInfo();
    try { localStorage.setItem(LS_PIC, dbId); } catch (_) {}
    bus.emit('db:switched', { id: resp.active_id, name: resp.active_name });
    toast(`图片库 → ${resp.active_name}`, 'ok', 1800);
  } catch (e) {
    toast('切图库失败: ' + e.message, 'err', 3000);
    if (_picSelectEl) _picSelectEl.value = _currentPicId || '';
  }
}

function _renderPicOptions() {
  if (!_picSelectEl) return;
  _picSelectEl.innerHTML = '';
  for (const d of _picDatabases) {
    const opt = el('option', { value: d.id }, `${d.name}${!d.exists ? ' (无)' : ''}`);
    if (d.id === _currentPicId) opt.selected = true;
    _picSelectEl.appendChild(opt);
  }
  for (const opt of _picSelectEl.querySelectorAll('option')) {
    const d = _picDatabases.find(x => x.id === opt.value);
    if (d && !d.exists) opt.disabled = true;
  }
}

function _renderPicInfo() {
  if (!_picInfoEl) return;
  const d = _picDatabases.find(x => x.id === _currentPicId);
  if (!d) { _picInfoEl.textContent = ''; return; }
  _picInfoEl.textContent = `${d.image_count ?? 0} 张图`;
  _picInfoEl.title = d.db_path;
}

// ===== 画布库(2026-08-17 加)=====
async function _loadCanvas() {
  if (!_canvasSelectEl) return;
  try {
    const data = await api.getCanvasDatabases();
    _canvasDatabases = data.databases || [];
    _currentCanvasId = data.active_id;
    _renderCanvasOptions();
    _renderCanvasInfo();
  } catch (e) { console.warn('[db-switcher] canvas load failed', e); }
}

async function _switchCanvas(dbId) {
  try {
    const resp = await api.switchCanvasDatabase(dbId);
    _currentCanvasId = resp.active_id;
    _renderCanvasInfo();
    try { localStorage.setItem(LS_CANVAS, dbId); } catch (_) {}
    // 通知其他模块重载画布列表(canvas-list.js 监听)
    bus.emit('canvas-db:switched', { id: resp.active_id, name: resp.active_name, db_path: resp.db_path });
    toast(`画布库 → ${resp.active_name}`, 'ok', 1800);
    // 切完刷画布列表(直接 reload 是最稳的)
    setTimeout(() => location.reload(), 1200);
  } catch (e) {
    toast('切画布库失败: ' + e.message, 'err', 3000);
    if (_canvasSelectEl) _canvasSelectEl.value = _currentCanvasId || '';
  }
}

function _renderCanvasOptions() {
  if (!_canvasSelectEl) return;
  _canvasSelectEl.innerHTML = '';
  for (const d of _canvasDatabases) {
    const label = `${d.icon || ''} ${d.name.replace(/^[^\s]+\s/, '')}  (${d.canvas_count ?? 0} 个画布)${!d.exists ? ' [新]' : ''}`;
    const opt = el('option', { value: d.id, title: d.desc || d.name }, label);
    if (d.id === _currentCanvasId) opt.selected = true;
    _canvasSelectEl.appendChild(opt);
  }
  for (const opt of _canvasSelectEl.querySelectorAll('option')) {
    const d = _canvasDatabases.find(x => x.id === opt.value);
    if (d && !d.exists) opt.disabled = true;
  }
}

function _renderCanvasInfo() {
  if (!_canvasInfoEl) return;
  const d = _canvasDatabases.find(x => x.id === _currentCanvasId);
  if (!d) { _canvasInfoEl.textContent = ''; return; }
  _canvasInfoEl.textContent = `${d.canvas_count ?? 0} 画布`;
  _canvasInfoEl.title = d.db_path;
}

export function getCurrentId() { return _currentPicId; }
export function getCurrentCanvasId() { return _currentCanvasId; }
