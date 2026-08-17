// api.js · 所有 /api/* 调用(单一事实源)
// 改前必读:对应端点契约见 _v25/api_contract.md
// 任何 /api/* 调用必须走这里,禁止直接 fetch
import { TIMEOUTS } from './core/constants.js';  // 2026-08-14 加:中心常量
const BASE = '';  // 同源,走当前端口 9002

async function _json(res) {
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.error || `HTTP ${res.status}`);
  return body;
}

function _url(path, params) {
  const qs = params ? '?' + new URLSearchParams(params).toString() : '';
  return BASE + path + qs;
}
// 2026-07-24 加:export-pdf.js 需要直接用 _url 拼 fetch URL(返回 HTML,不走 _json)
export { _url };

// ===== 搜索 / 收藏 =====
export async function search(params = {}) {
  return _json(await fetch(_url('/api/search', params)));
}
// 2026-07-24 加:多数据库切换(图片库 / 分析图库 / ...)
export async function getDatabases() {
  return _json(await fetch(_url('/api/db')));
}
export async function switchDatabase(id) {
  return _json(await fetch(_url('/api/db'), {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id }),
  }));
}
export async function facets() {
  return _json(await fetch(_url('/api/facets')));
}
export async function getFavorites() {
  return _json(await fetch(_url('/api/favorites')));
}
export async function toggleFavorite(id) {
  return _json(await fetch(_url('/api/favorites'), {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id }),
  }));
}

// ===== 上传 / AI 生图 =====
export async function uploadImage(file) {
  // 2026-07-09 修复:后端要 base64(JSON),不要 FormData(FileReader.readAsDataURL)
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = async () => {
      try {
        const res = await fetch(_url('/api/upload_image'), {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ image: reader.result, name: file.name }),
        });
        resolve(await _json(res));
      } catch (e) { reject(e); }
    };
    reader.onerror = () => reject(reader.error || new Error('FileReader failed'));
    reader.readAsDataURL(file);
  });
}
export async function uploadSearch(dataUrl) {
  return _json(await fetch(_url('/api/upload_search'), {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ image_base64: dataUrl }),
  }));
}
export async function aiImage({ prompt, style_id, reference_images, aspect_ratio, resolution }) {
  // 2026-07-09 修复:后端契约字段是 reference_images(不是 input_urls)
  // 后端返 {path, cdn_url, local_path,...},前端契约要 {ok, url}
  const body = await _json(await fetch(_url('/api/ai_image'), {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt, style_id, reference_images: reference_images || [], aspect_ratio, resolution }),
  }));
  if (body.error) throw new Error(body.error);
  return {
    ok: true,
    url: body.path || body.url || body.cdn_url,
    style: body.style_name || style_id,
    ...body,  // 保留原字段供调试
  };
}

// 2026-07-09 加:异步启动 AI 生图(立即返 task_id,不阻塞前端)
// 用于:页面关掉后服务端继续生成,重开页面通过轮询拿结果
export async function aiImageStart({ prompt, style_id, reference_images, aspect_ratio, resolution }) {
  const body = await _json(await fetch(_url('/api/ai_image_start'), {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      prompt, style_id,
      reference_images: reference_images || [],
      aspect_ratio, resolution,
    }),
  }));
  if (body.error) throw new Error(body.error);
  return body;   // { task_id, status: 'pending', poll_url, poll_interval_ms }
}

// 2026-07-09 加:查异步任务状态
// 返 { task_id, status: 'pending'|'done'|'error'|'not_found', local_url, filename, error, ... }
export async function aiTaskStatus(task_id) {
  return _json(await fetch(_url('/api/ai_task/' + encodeURIComponent(task_id))));
}
export async function aiStyles() {
  return _json(await fetch(_url('/api/ai_styles')));
}

// 2026-07-24 加:多视角批生成(6 视角预设一次提交)
export async function aiViews() {
  return _json(await fetch(_url('/api/ai_views')));
}
export async function aiImageBatchStart({ prompt, style_id, resolution, views, reference_images }) {
  const body = await _json(await fetch(_url('/api/ai_image_batch_start'), {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      prompt, style_id, resolution,
      views: views || [],
      reference_images: reference_images || [],
    }),
  }));
  if (body.error) throw new Error(body.error);
  return body;   // { batch_id, tasks: [...], poll_url_template, poll_interval_ms }
}
export async function aiBatchStatus(batch_id) {
  return _json(await fetch(_url('/api/ai_batch/' + encodeURIComponent(batch_id))));
}

// 2026-07-24 加:用户/协作 API
function _authHeaders(token) {
  return token ? { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' };
}
export async function usersRegister({ username, password, display_name }) {
  return _json(await fetch(_url('/api/users/register'), {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password, display_name }),
  }));
}
export async function usersLogin({ username, password }) {
  return _json(await fetch(_url('/api/users/login'), {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  }));
}
export async function usersLogout(token) {
  return _json(await fetch(_url('/api/users/logout'), {
    method: 'POST', headers: { 'Authorization': 'Bearer ' + token },
  }));
}
export async function usersMe(token) {
  return _json(await fetch(_url('/api/users/me'), { headers: { 'Authorization': 'Bearer ' + token } }));
}
export async function canvasLockAcquire(canvas_id, token) {
  return _json(await fetch(_url('/api/canvas_lock'), {
    method: 'POST', headers: _authHeaders(token),
    body: JSON.stringify({ canvas_id }),
  }));
}
export async function canvasLockGet(canvas_id, token) {
  return _json(await fetch(_url('/api/canvas_lock?canvas_id=' + canvas_id), {
    headers: { 'Authorization': 'Bearer ' + token },
  }));
}
export async function canvasLockRelease(canvas_id, token) {
  return _json(await fetch(_url('/api/canvas_lock?canvas_id=' + canvas_id), {
    method: 'DELETE', headers: { 'Authorization': 'Bearer ' + token },
  }));
}

// 2026-07-09 加:AI 生视频 API(矩阵 matrix_gen_videos · 图生视频为主)
export async function aiVideoStyles() {
  return _json(await fetch(_url('/api/ai_video_styles')));
}
export async function aiVideo({ prompt, style_id, duration, resolution,
                                  reference_image, reference_type }) {
  const body = await _json(await fetch(_url('/api/ai_video'), {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      prompt, style_id,
      duration: duration || 6,
      resolution: resolution || '768P',
      reference_image: reference_image || '',
      reference_type: reference_type || 'first_frame',
    }),
  }));
  if (body.error) throw new Error(body.error);
  return {
    ok: true,
    url: body.path || body.cdn_url,
    style: body.style_name || style_id,
    duration: body.duration,
    resolution: body.resolution,
    archived: body.archived,
    ...body,
  };
}
export async function aiVideosList(params = {}) {
  return _json(await fetch(_url('/api/ai_videos', params)));
}

// ===== 语义搜索 =====
export async function semanticSearch(q, limit = 20) {
  return _json(await fetch(_url('/api/semantic_search'), {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ q, limit }),
  }));
}

// ===== LLM =====
export async function llmStatus() {
  return _json(await fetch(_url('/api/llm_status')));
}
export async function llmGetConfig() {
  // 2026-07-09 修复:后端返回 {config:{...}, loaded},前端要解包 .config
  const body = await _json(await fetch(_url('/api/llm_config')));
  return body.config || body;
}
export async function llmSaveConfig(cfg) {
  // 2026-07-22 修复:包成 {config: cfg} 再发,后端从 body.config 解(契约:同 GET 响应结构)
  // 之前直接发 cfg,后端 body.get('config') 拿到 None,等价于"啥都没保存",点保存完全无效
  return _json(await fetch(_url('/api/llm_config'), {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ config: cfg }),
  }));
}
export async function llmTest(overrides = {}) {
  return _json(await fetch(_url('/api/llm_test'), {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(overrides),
  }));
}
export async function llmCall(messages, opts = {}) {
  // 2026-08-14 加:timeout 选项(默认用 TIMEOUTS.LLM_CALL_MS 中心常量)· AbortController 让前端能主动中断
  // 不传 = 用默认 60s;传 0 = 不超时(危险,慎用)
  const { timeout = TIMEOUTS.LLM_CALL_MS, ...rest } = opts;
  const controller = new AbortController();
  let timer = null;
  if (timeout > 0) {
    timer = setTimeout(() => controller.abort(new Error(`LLM timeout after ${timeout / 1000}s`)), timeout);
  }
  try {
    return await _json(await fetch(_url('/api/llm'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages, ...rest }),
      signal: controller.signal,
    }));
  } finally {
    if (timer) clearTimeout(timer);
  }
}
// 2026-07-28 加:便捷版 - 带画布图(多模态)LLM 调用
// 旧 llmCall 仍可用(纯文字 system),本函数自动处理 imageUrls → messages
export async function llmCallWithCanvas(messages, { system, imageUrls, tools, temperature = 0.6, max_tokens = 1500 } = {}) {
  // 把 imageUrls 拼到第一条 user 消息(如果有 user 消息),否则新建一条
  const msgs = [...messages];
  if (imageUrls && imageUrls.length) {
    const userIdx = msgs.findIndex(m => m.role === 'user');
    if (userIdx >= 0) {
      const orig = msgs[userIdx].content;
      const blocks = typeof orig === 'string'
        ? [{ type: 'text', text: orig }]
        : (Array.isArray(orig) ? orig : [{ type: 'text', text: String(orig) }]);
      const imgBlocks = imageUrls.map(url => ({ type: 'image_url', image_url: { url } }));
      msgs[userIdx] = { ...msgs[userIdx], content: [...imgBlocks, ...blocks] };
    } else {
      msgs.unshift({
        role: 'user',
        content: [
          ...imageUrls.map(url => ({ type: 'image_url', image_url: { url } })),
          { type: 'text', text: '【以下是当前画布的参考图,供你理解视觉风格】' },
        ],
      });
    }
  }
  return llmCall(msgs, { system, tools, temperature, max_tokens });
}

// ===== 画布 =====
export async function listCanvases() {
  return _json(await fetch(_url('/api/canvases')));
}
export async function getCanvas(id) {
  return _json(await fetch(_url('/api/canvas/' + encodeURIComponent(id))));
}
// 2026-07-27 加:跨画布全局搜索
export async function globalSearch(q) {
  return _json(await fetch(_url('/api/canvases/search?q=' + encodeURIComponent(q))));
}
export async function canvasAction({ action, id, name, layout }) {
  return _json(await fetch(_url('/api/canvas'), {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, id, name, layout }),
  }));
}

// ===== 图生文(image2text 节点 · 2026-07-15 加)=====
export async function i2tStyles() {
  return _json(await fetch(_url('/api/i2t_styles')));
}
// 同步(立即返结果)· 适合小图/快速测试
export async function i2tText({ template_id, user_prompt, image_data_urls }) {
  return _json(await fetch(_url('/api/i2t_text'), {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ template_id, user_prompt, image_data_urls }),
  }));
}
// 异步(立即返 task_id)· 适合真实使用
export async function i2tTextStart({ template_id, user_prompt, image_data_urls }) {
  return _json(await fetch(_url('/api/i2t_text_start'), {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ template_id, user_prompt, image_data_urls }),
  }));
}
export async function i2tTaskStatus(task_id) {
  return _json(await fetch(_url('/api/i2t_task/' + encodeURIComponent(task_id))));
}

// ===== 文字转声音(TTS 节点 · 2026-07-15 加)=====
export async function ttsVoices() {
  return _json(await fetch(_url('/api/tts_voices')));
}
// 同步
export async function ttsCall({ text, voice_id, speed }) {
  return _json(await fetch(_url('/api/tts'), {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, voice_id, speed }),
  }));
}
// 异步
export async function ttsStart({ text, voice_id, speed }) {
  return _json(await fetch(_url('/api/tts_start'), {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, voice_id, speed }),
  }));
}
export async function ttsTaskStatus(task_id) {
  return _json(await fetch(_url('/api/tts_task/' + encodeURIComponent(task_id))));
}

// ===== 文字生成音乐(music 节点 · 2026-07-15 加)=====
export async function musicStyles() {
  return _json(await fetch(_url('/api/music_styles')));
}
// 同步
export async function musicCall({ style_id, prompt, lyrics, instrumental, sample_rate, bitrate }) {
  return _json(await fetch(_url('/api/music'), {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ style_id, prompt, lyrics, instrumental, sample_rate, bitrate }),
  }));
}
// 异步
export async function musicStart({ style_id, prompt, lyrics, instrumental, sample_rate, bitrate }) {
  return _json(await fetch(_url('/api/music_start'), {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ style_id, prompt, lyrics, instrumental, sample_rate, bitrate }),
  }));
}
export async function musicTaskStatus(task_id) {
  return _json(await fetch(_url('/api/music_task/' + encodeURIComponent(task_id))));
}


// ===== 2026-08-17 加:画布 DB 切换(按工作类型分库)=====
export async function getCanvasDatabases() {
  // GET /api/db?type=canvas
  return _json(await fetch(_url('/api/db', { type: 'canvas' })));
}
export async function switchCanvasDatabase(id) {
  // POST /api/db {id, type: 'canvas'}
  return _json(await fetch(_url('/api/db'), {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id, type: 'canvas' }),
  }));
}

// ===== 2026-08-05 加:AI 提示词优化(建筑外观方向)=====
export async function optimizePrompt({ canvas_id, node_id, mode = 'architecture' }) {
  return _json(await fetch(_url('/api/optimize_prompt'), {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ canvas_id, node_id, mode }),
  }));
}

export async function optimizePromptReplace({ canvas_id, node_id, prompt, lang = 'cn' }) {
  return _json(await fetch(_url('/api/optimize_prompt_replace'), {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ canvas_id, node_id, prompt, lang }),
  }));
}

export async function optimizePromptRollback({ canvas_id, node_id, version_index }) {
  return _json(await fetch(_url('/api/optimize_prompt_rollback'), {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ canvas_id, node_id, version_index }),
  }));
}

// ===== 2026-08-05 v3.5.39 加:chat 历史服务端持久化 =====
// 2026-08-11 v3.5.49 改 (R222 P0):不再传 user_id,走 Bearer token(从 auth.js getToken() 拿),
//   防多用户串台 + 前端 bug 写死 user_id 覆盖他人历史
import { getToken } from './modules/auth.js';
export async function getChatState() {
  return _json(await fetch(_url('/api/chat_state'), { headers: _authHeaders(getToken()) }));
}
export async function setChatState({ history }) {
  return _json(await fetch(_url('/api/chat_state'), {
    method: 'POST',
    headers: _authHeaders(getToken()),
    body: JSON.stringify({ history }),
  }));
}
export async function clearChatState() {
  return _json(await fetch(_url('/api/chat_state'), {
    method: 'DELETE',
    headers: _authHeaders(getToken()),
  }));
}
