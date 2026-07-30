async function json(res) {
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail.detail || `${res.status} ${res.statusText}`)
  }
  return res.json()
}

export const getHealth = () => fetch('/api/health').then(json)

export const previewPhonemes = (text) =>
  fetch(`/api/sentences/preview-phonemes?text=${encodeURIComponent(text)}`).then(json)

export function submitAttempt({ wavBlob, expectedText, sentenceId }) {
  const form = new FormData()
  form.append('audio', wavBlob, 'attempt.wav')
  form.append('expected_text', expectedText)
  if (sentenceId != null) form.append('sentence_id', String(sentenceId))
  return fetch('/api/attempts', { method: 'POST', body: form }).then(json)
}

// --- Lector ---

export const listBooks = () => fetch('/api/books').then(json)

export function importBook(file) {
  const form = new FormData()
  form.append('epub', file, file.name)
  return fetch('/api/books/import', { method: 'POST', body: form }).then(json)
}

export const listChapters = (bookId) => fetch(`/api/books/${bookId}/chapters`).then(json)

/** Legibilidad medida sobre el propio texto. La primera llamada tarda unos
 *  segundos: fonemiza el vocabulario entero para contar sílabas de verdad. */
export const bookDifficulty = (bookId) =>
  fetch(`/api/books/${bookId}/difficulty`).then(json)

export const readChapter = (chapterId) => fetch(`/api/chapters/${chapterId}`).then(json)

export const startTranslation = (chapterId) =>
  fetch(`/api/chapters/${chapterId}/translate`, { method: 'POST' }).then(json)

export const translationProgress = (chapterId) =>
  fetch(`/api/chapters/${chapterId}/translation`).then(json)

export const getResume = (bookId) => fetch(`/api/books/${bookId}/resume`).then(json)

/** Dónde reanudar sin importar el libro: para la pantalla de inicio. */
export const getLatestResume = () => fetch('/api/resume').then(json)

export const weekSummary = () => fetch('/api/progress/week').then(json)

export function savePosition(chapterId, sentenceId) {
  // Se dispara seguido mientras lees: si falla, no vale interrumpir la lectura.
  return fetch(`/api/chapters/${chapterId}/position`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sentence_id: sentenceId }),
  }).catch(() => {})
}

/** IPA local: responde en milisegundos, sin tocar el LLM. */
export const getPhonetics = (word) =>
  fetch(`/api/phonetics?word=${encodeURIComponent(word)}`).then(json)

export const glossWord = (word, sentence, sentenceId) => {
  const params = new URLSearchParams({ word, sentence })
  if (sentenceId != null) params.set('sentence_id', String(sentenceId))
  return fetch(`/api/gloss?${params}`).then(json)
}

export const getVocab = (limit = 40) => fetch(`/api/vocab?limit=${limit}`).then(json)

// --- Narración ---

/** URL del audio. La misma petición siempre da el mismo archivo: el navegador
 *  la cachea de forma inmutable y el servidor no vuelve a sintetizar. */
export const speechUrl = (text, { slow = false } = {}) => {
  const params = new URLSearchParams({ text })
  if (slow) params.set('slow', 'true')
  return `/api/speech?${params}`
}

export const speechMarks = (text, { slow = false } = {}) => {
  const params = new URLSearchParams({ text })
  if (slow) params.set('slow', 'true')
  return fetch(`/api/speech/marks?${params}`).then(json)
}

// --- Progreso ---

export const phonemeProgress = (days = 30) =>
  fetch(`/api/progress/phonemes?days=${days}`).then(json)

export const patternProgress = (days = 30) =>
  fetch(`/api/progress/patterns?days=${days}`).then(json)

/** Ventana más larga que el resto: aquí se mide el nivel, no la tendencia. */
export const baselineProgress = (days = 90) =>
  fetch(`/api/progress/baseline?days=${days}`).then(json)

/** Sin `ipa`, el backend elige el sonido que peor llevas.
 *  La primera llamada fonemiza el vocabulario del libro: puede tardar segundos. */
export const getDrill = (limit = 6, ipa) => {
  const params = new URLSearchParams({ limit: String(limit) })
  if (ipa) params.set('ipa', ipa)
  return fetch(`/api/drills?${params}`).then(json)
}

/** Tu ritmo contra el del modelo, palabra por palabra. */
export const compareRhythm = (attemptId) =>
  fetch(`/api/shadowing/compare?attempt_id=${attemptId}`).then(json)

/** Tu velocidad medida leyendo en voz alta, para el marcapasos. */
export const readingPace = (days = 90) =>
  fetch(`/api/progress/pace?days=${days}`).then(json)

/** Sin argumento, la última sesión. Se derivan del ritmo de grabación. */
export const sessionReport = (sessionId) =>
  fetch(`/api/sessions/report${sessionId ? `?session_id=${sessionId}` : ''}`).then(json)
