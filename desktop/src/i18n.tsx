import { useState, useSyncExternalStore } from 'react'

/** Participant-facing language (2026-11-22): English or Japanese. Only what a participant sees is translated (session, final list,
 * start/personalize controls, sound descriptions); researcher tools stay English. Chosen once at first start, changeable in the headers,
 * kept in this browser only. ponytail: one flat dictionary keyed by the English text; move to message ids if a third language comes. */
export type Lang = 'en' | 'ja'
const KEY = 'evlab.lang'
let current: Lang | null = (() => { try { const v = localStorage.getItem(KEY); return v === 'en' || v === 'ja' ? v : null } catch { return null } })()
const listeners = new Set<() => void>()
export function setLang(lang: Lang) {
  current = lang
  try { localStorage.setItem(KEY, lang) } catch { /* private window: the choice lasts this visit */ }
  listeners.forEach(listener => listener())
}
// Another window (dashboard, overlay, first window) changed the language: follow it, so every open window switches together.
if (typeof window !== 'undefined') window.addEventListener('storage', event => {
  if (event.key !== KEY || (event.newValue !== 'en' && event.newValue !== 'ja') || event.newValue === current) return
  current = event.newValue; listeners.forEach(listener => listener())
})
export const useLang = () => useSyncExternalStore(listener => { listeners.add(listener); return () => { listeners.delete(listener) } }, () => current)

// Japanese, keyed by the English text; {name} marks a value filled in by t().
const JA: Record<string, string> = {
  'Personalize sound': 'サウンドをカスタマイズ',
  'Resume session': 'セッションを再開',
  'Start sound': 'サウンド開始',
  'Stop sound': 'サウンド停止',
  'Starting…': '起動中…',
  START: 'スタート',
  STOP: 'ストップ',
  'Start vehicle': '車両をスタート',
  'Stop vehicle': '車両をストップ',
  Rising: 'ライジング',
  Evolving: 'エボルビング',
  Close: '閉じる',
  'Connecting to simulator…': 'シミュレーターに接続中…',
  'Leave the session?': 'セッションを離れますか？',
  'Pause keeps your answers so far: Resume session continues it. End stops it without picking a final sound.':
    '「一時停止」ではこれまでの回答が保存され、「セッションを再開」で続けられます。「セッションを終了」では最終サウンドを選ばずに終了します。',
  'Keep working': '続ける',
  Pause: '一時停止',
  'End session': 'セッションを終了',
  'Broad sound discovery': 'サウンド探索',
  '{n} / {total} comparisons': '{n} / {total} 回の比較',
  'Final round {n} / {total} · ': '決勝 {n} / {total} · ',
  'New session': '新しいセッション',
  'Start session': 'セッション開始',
  'Start a session to compare sources.': 'セッションを開始して、サウンドを比較してください。',
  'Session complete · {n} comparisons.': 'セッション完了 · {n} 回比較しました。',
  ' Choose your final sound from your shortlist below.': '下の候補から最終サウンドを選んでください。',
  'Session finished after {n} comparisons.': '{n} 回の比較でセッションを終了しました。',
  '▶ Now playing:': '▶ 再生中：',
  'Preparing…': '準備中…',
  'Final round: your four finalists, compared head to head. Pick the one you prefer.': '決勝：4つの候補を直接比較します。好きな方を選んでください。',
  'Sound {x}': 'サウンド {x}',
  'Your sound': 'あなたのサウンド',
  'Your pick (Sound {x})': 'あなたの選択（サウンド {x}）',
  'Previous {label}': '前の{label}',
  'Prefer A': 'A が好き',
  'Prefer B': 'B が好き',
  Neither: 'どちらも好きではない',
  'Both good': 'どちらも良い',
  Dislike: '嫌い',
  Like: '好き',
  Next: '次へ',
  'Retry preparation': '準備を再試行',
  'One last question': '最後の質問',
  'Would you be happy with this sound in your car?': 'このサウンドを自分の車で使いたいと思いますか？',
  '▶ Play it again': '▶ もう一度再生',
  Yes: 'はい',
  No: 'いいえ',
  'Saved · thank you!': '保存しました · ありがとうございました！',
  'Your final sound is #{n} of your ranked sounds. This session is saved in Sound trace.': '最終サウンドはランキングの {n} 位です。このセッションは Sound trace に保存されました。',
  'Play your final sound': '最終サウンドを再生',
  'Ranking your best sounds…': 'ベストサウンドをランキング中…',
  'Preparing your top three so each one plays at once.': 'すぐに再生できるよう、上位3つを準備しています。',
  'Your top three · choose your final sound': 'トップ3 · 最終サウンドを選んでください',
  'Ranked by all your choices in this session. The final choice is yours.': 'このセッションでのすべての選択からランキングしました。最終的な選択はあなたが決めてください。',
  '▶ Play': '▶ 再生',
  'won {w} of {g} choices': '{g} 回中 {w} 回選ばれました',
  'not compared yet': 'まだ比較されていません',
  'Choose this sound': 'このサウンドを選ぶ',
  'Show more ({n})': 'さらに表示（{n}）',
  'Are you sure this is your final sound?': 'このサウンドを最終サウンドにしますか？',
  'You picked #{n}. It will be saved as the result of this session.': '{n} 位を選びました。このセッションの結果として保存されます。',
  'Go back': '戻る',
  'Yes, save it': 'はい、保存します',
  Language: '言語',
  '●  CONTROLLER CONNECTED': '●  コントローラー接続済み',
  '○  CONTROLLER DISCONNECTED': '○  コントローラー未接続',
  'W throttle · S brake · controller triggers': 'W アクセル · S ブレーキ · コントローラーのトリガー',
  'Controller enabled': 'コントローラーを使用',
  Automatic: '自動',
  BRAKE: 'ブレーキ',
  THROTTLE: 'アクセル',
  DISPLAY: '表示',
  SIGNAL: '波形',
  SOUND: 'サウンド',
  'Customize dashboard display': 'ダッシュボードの表示を設定',
  'Show or hide the sound signal panel': 'サウンド波形パネルの表示／非表示',
  Display: '表示',
  'Set your instrument style.': 'メーターのスタイルを設定します。',
  'Instrument display': 'メーター表示',
  Classic: 'クラシック',
  Sport: 'スポーツ',
  Digital: 'デジタル',
  'Drive audio': 'ドライブサウンド',
  SIMULATOR: 'シミュレーター',
  'BEAMNG LINK': 'BeamNG 接続',
  DISCONNECTED: '未接続',
  INPUT: '入力',
  'MOTOR LOAD': 'モーター負荷',
  'EV SOUND LAB': 'EV サウンドラボ',
  'DRIVE SIMULATOR': 'ドライブシミュレーター',
  'SOUND TRACE': 'サウンド履歴',
  'RESEARCH RECORDS': '研究記録',
  'Toggle sidebar': 'サイドバーの表示切替',
  'What are you driving with?': '何で運転しますか？',
  Simulator: 'シミュレーター',
  'Built-in simulator with the full dashboard. Drive with W/S or a controller.': 'ダッシュボード付きの内蔵シミュレーター。W/S キーまたはコントローラーで運転します。',
  'Small overlay over the game. Telemetry comes from the BeamNG mod.': 'ゲームの上に表示される小さなオーバーレイ。走行データは BeamNG の mod から取得します。',
  'Sound trace': 'サウンド履歴',
  Dashboard: 'ダッシュボード',
  DASHBOARD: 'ダッシュボード',
  TRACE: '履歴',
  'Sound Lab': 'サウンドラボ',
  'SOUND LAB': 'サウンドラボ',
  'No saved sessions yet. Sound discovery sessions save here automatically.': '保存されたセッションはまだありません。サウンド探索のセッションはここに自動で保存されます。',
  '{n} comparisons · {state}': '{n} 回の比較 · {state}',
  'favorite chosen': 'お気に入り決定',
  'finalists ranked': '候補をランキング済み',
  'Select a session to inspect.': '確認するセッションを選んでください。',
  '{n} rated pairs · {m} final-round pairs': '評価したペア {n} · 決勝のペア {m}',
  'Starred: kept at the top. Click to unstar.': 'スター付き：一番上に表示されます。クリックで解除。',
  'Star to mark this session as one to keep': 'スターを付けて、残しておくセッションとして印を付ける',
  'Star session': 'セッションにスター',
  Keep: '残す',
  'Delete starred session': 'スター付きセッションを削除',
  Delete: '削除',
  'Delete session': 'セッションを削除',
  Expand: '開く',
  ' · ★ chosen': ' · ★ 選択',
  ' · rated {n}/7': ' · 評価 {n}/7',
  'neither liked': 'どちらも好きではない',
  'both good': 'どちらも良い',
  'liked equally': '同じくらい好き',
  'Pair {n}': 'ペア {n}',
  ' · new pick': ' · 新しい選択',
  '— no pick —': '— 選択なし —',
  'Final round {n}': '決勝 {n}',
  'Sound {x} preferred': 'サウンド {x} を選択',
  ' · preferred': ' · 選択',
  'Ranked finalists': 'ランキングされた候補',
  ' · favorite': ' · お気に入り',
  '{w}/{g} wins · mean rating {r}': '{w}/{g} 勝 · 平均評価 {r}',
  'Your pick from pair {n}, defending': 'ペア {n} での選択（防衛中）',
  'Same sound, {motion}': '同じサウンド、{motion}',
  'Opening: typical sound': 'オープニング：代表的なサウンド',
  'Styles compete': 'スタイル同士の比較',
  'Challenger from your leading styles': '上位スタイルからの挑戦者',
  '{move} version of your pick': 'あなたの選択の {move} 版',
  'The original of your pick': 'あなたの選択のオリジナル',
  'Sound {id}': 'サウンド {id}',
  Preview: 'プレビュー',
  Stop: '停止',
  '▶ Play on the 22 s drive': '▶ 22 秒のドライブで再生',
  Settings: '設定',
  'Generating sound…': 'サウンドを生成中…',
  'Generated on demand and discarded when you close this or leave the page.': '必要なときに生成され、閉じるかページを離れると破棄されます。',
  Ratings: '評価',
  Parameters: 'パラメーター',
  'Spectrum (energy share by Hz band)': 'スペクトル（周波数帯ごとのエネルギー割合）',
}

export type T = (en: string, values?: Record<string, string | number>) => string
export function translate(lang: Lang | null, en: string, values?: Record<string, string | number>) {
  let text = lang === 'ja' ? JA[en] ?? en : en
  for (const [k, v] of Object.entries(values ?? {})) text = text.replaceAll(`{${k}}`, String(v))
  return text
}
export function useT(): T { const lang = useLang(); return (en, values) => translate(lang, en, values) }

/** Building-block sound in plain words, in the chosen language (the backend label is English). */
type Blocks = { body: string; top: string; level: string; pitch: number; brightness: number; space: string; buzz?: number; chord?: string; bell?: boolean; vowel?: boolean; partner?: string | null }
const PITCHES = [47.2, 59.5, 75, 94.5, 119.1]  // = experiment/sound_blocks.py PITCHES
const NAMES: Record<string, [string, string]> = { soft: ['Soft', 'ソフト'], blocks: ['Blocks', 'ブロック'], electric: ['Electric', 'エレクトリック'], glass: ['Glass', 'グラス'],
  plain: ['Plain', 'プレーン'], synth: ['Synth', 'シンセ'], bell: ['Bell synth', 'ベルシンセ'], moody: ['Moody', 'ムーディー'] }
const LEVELS: Record<string, string> = { soft: '弱', medium: '中', strong: '強' }
export function describeBlocks(b: Blocks, motion: string | undefined, lang: Lang | null) {
  if (lang !== 'ja') return null
  const synth = b.top === 'synth' || b.top === 'bell'
  const words = [`ボディ: ${NAMES[b.body]?.[1] ?? b.body}`, `トップ: ${NAMES[b.top]?.[1] ?? b.top}（${LEVELS[b.level] ?? b.level}）` + (b.partner ? ` + 最上層: ${NAMES[b.partner]?.[1] ?? b.partner}` : ''), `${PITCHES[b.pitch] ?? ''} Hz`, `明るさ ${b.brightness.toFixed(2)}`]
  if (synth && b.buzz) words.push(`バズ ${b.buzz > 1 ? '強' : '弱'}`)
  if (synth && b.chord && b.chord !== 'off') words.push('和音')
  if (synth && b.bell) words.push('ベル')
  if (synth && b.vowel) words.push('声')
  words.push(b.space === 'dry' ? 'ドライ' : '広い空間')
  if (motion === 'evolving') words.push('エボルビング')
  return words.join(' · ')
}

/** Header slider: thumb slides between English (left) and 日本語 (right). className kept for callers, unused. */
export function LanguageSelect(_: { className?: string }) {
  const ja = useLang() === 'ja'
  return <LangSlider ja={ja} onToggle={() => setLang(ja ? 'en' : 'ja')} />
}

function LangSlider({ ja, onToggle }: { ja: boolean; onToggle: () => void }) {
  return <button type="button" role="switch" aria-checked={ja} aria-label="Language / 言語" title="Language / 言語" onClick={onToggle}
    className="relative inline-grid h-9 w-32 shrink-0 grid-cols-2 items-center rounded-full border border-neutral-600 bg-neutral-900 text-sm">
    <span aria-hidden className="absolute left-0.5 top-0.5 h-[calc(100%-4px)] w-[calc(50%-2px)] rounded-full bg-neutral-100 transition-transform duration-200" style={{ transform: ja ? 'translateX(100%)' : 'none' }} />
    <span className={'relative z-10 text-center ' + (ja ? 'text-neutral-300' : 'text-neutral-900')}>EN</span>
    <span className={'relative z-10 text-center ' + (ja ? 'text-neutral-900' : 'text-neutral-300')}>日本語</span>
  </button>
}

/** First start: ask once, before anything else. Slider top right picks, Continue commits (the slider alone would close the popup on first click). */
export function LanguageGate() {
  const lang = useLang()
  const [ja, setJa] = useState(false)
  if (lang) return null
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"><div className="panel max-w-md p-6" role="dialog" aria-modal="true" aria-label="Language / 言語">
    <div className="flex items-start justify-between gap-4"><h2 className="text-xl">Language / 言語</h2><LangSlider ja={ja} onToggle={() => setJa(v => !v)} /></div>
    <p className="my-4 text-sm text-neutral-300">Choose a language. You can change it later in the header.<br />言語を選んでください。後でヘッダーから変更できます。</p>
    <button className="control" autoFocus onClick={() => setLang(ja ? 'ja' : 'en')}>{ja ? '続ける' : 'Continue'}</button>
  </div></div>
}
