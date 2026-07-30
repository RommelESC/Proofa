import { useEffect, useRef, useState } from 'react'

import {
  baselineProgress,
  bookDifficulty,
  getLatestResume,
  getResume,
  importBook,
  listBooks,
  listChapters,
  weekSummary,
} from '../api'
import StartPanel from '../components/StartPanel'
import { Import, Resume } from '../components/icons'

export default function Library({ onOpenChapter, onPractice }) {
  const [books, setBooks] = useState([])
  const [openBook, setOpenBook] = useState(null)
  const [chapters, setChapters] = useState([])
  const [resume, setResume] = useState(null)
  const [difficulty, setDifficulty] = useState(null)
  const [importing, setImporting] = useState(false)
  const [error, setError] = useState(null)
  const [latest, setLatest] = useState(null)
  const [week, setWeek] = useState(null)
  const [baseline, setBaseline] = useState(null)
  const fileInput = useRef(null)

  useEffect(() => {
    listBooks().then(setBooks).catch((e) => setError(e.message))
    // Los tres paneles de inicio fallan en silencio: sin historial todavía no
    // tienen nada que decir, y un error ahí sería ruido en la primera pantalla.
    getLatestResume().then((d) => setLatest(d.resume)).catch(() => {})
    weekSummary().then(setWeek).catch(() => {})
    baselineProgress(90).then(setBaseline).catch(() => {})
  }, [])

  /** Abre el capítulo donde lo dejaste, ya en el modo que elegiste. */
  async function openLatest(mode) {
    if (!latest) return
    try {
      const chs = await listChapters(latest.book_id)
      const chapter = chs.find((c) => c.id === latest.chapter_id)
      if (chapter) onOpenChapter(chapter, mode)
    } catch (e) {
      setError(e.message)
    }
  }

  async function handleFile(event) {
    const file = event.target.files?.[0]
    if (!file) return
    setImporting(true)
    setError(null)
    try {
      const book = await importBook(file)
      setBooks((prev) => [book, ...prev])
    } catch (e) {
      setError(e.message)
    } finally {
      setImporting(false)
      event.target.value = ''
    }
  }

  async function toggleBook(book) {
    if (openBook?.id === book.id) {
      setOpenBook(null)
      return
    }
    setOpenBook(book)
    setChapters([])
    setResume(null)
    setDifficulty(null)
    // Aparte y sin bloquear: el primer cálculo fonemiza el libro entero.
    bookDifficulty(book.id).then(setDifficulty).catch(() => {})
    try {
      const [chs, res] = await Promise.all([listChapters(book.id), getResume(book.id)])
      setChapters(chs)
      setResume(res.resume)
    } catch (e) {
      setError(e.message)
    }
  }

  function openResume() {
    const chapter = chapters.find((c) => c.id === resume.chapter_id)
    if (chapter) onOpenChapter(chapter)
  }

  return (
    <div className="page dashboard">
      <header className="library-head">
        <h1>Biblioteca</h1>
        <button className="solid" onClick={() => fileInput.current?.click()} disabled={importing}>
          <Import size={15} />
          {importing ? 'Importando…' : 'Importar EPUB'}
        </button>
        <input ref={fileInput} type="file" accept=".epub" onChange={handleFile} hidden />
      </header>

      {error && <p className="error">{error}</p>}

      <StartPanel
        resume={latest}
        week={week}
        baseline={baseline}
        onOpen={openLatest}
        onPractice={onPractice}
      />

      <div className="dash-main">
        <h2 className="section-head">Tus libros</h2>
        <p className="hint">
          Los libros no vienen incluidos: importa los tuyos o descarga de dominio público.
          Se procesan en tu máquina y no salen de ella.
        </p>

        {books.length === 0 && !error && (
          <p className="muted">Todavía no hay libros. Importa un .epub para empezar.</p>
        )}

        <ul className="books">
        {books.map((book) => (
          // Abierto ocupa la fila entera: su celda crece con los capítulos y
          // desalinearía el resto de la rejilla.
          <li key={book.id} className={openBook?.id === book.id ? 'open' : undefined}>
            <button className="book" onClick={() => toggleBook(book)}>
              <span className="title">{book.title}</span>
              {book.author && <span className="author">{book.author}</span>}
              <span className="meta">
                {book.chapters} cap · {book.sentences.toLocaleString('es-MX')} oraciones
              </span>
            </button>

            {openBook?.id === book.id && (
              <>
                {difficulty?.measured && (
                  <p className="difficulty">
                    <strong>{difficulty.label}</strong> · Flesch {difficulty.flesch} ·{' '}
                    {difficulty.words_per_sentence} palabras por oración
                    <span className="approx"> (~{difficulty.cefr_approx}, orientativo)</span>
                    {/* Flesch no ve la gramática arcaica: «Meditations» puntúa
                        «normal» y aun así 1 de cada 21 palabras es un «thou» o
                        un «whatsoever». Se dice aparte porque el número solo
                        se quedaría corto. */}
                    {difficulty.archaic_heavy && (
                      <span className="archaic">
                        Inglés antiguo: {difficulty.archaic_per_1000} de cada 1000 palabras
                        son formas arcaicas (thou, hast, whatsoever). Cuesta más de lo que
                        dice el número.
                      </span>
                    )}
                  </p>
                )}

                {resume && (
                  <button className="resume" onClick={openResume}>
                    <Resume size={15} />
                    <span>
                      Reanudar en {resume.chapter_title || `capítulo ${resume.chapter_idx + 1}`}
                    </span>
                  </button>
                )}

                <ol className="chapters">
                  {chapters.map((ch) => {
                    const pct = ch.sentences ? (ch.reached / ch.sentences) * 100 : 0
                    return (
                      <li key={ch.id}>
                        <button onClick={() => onOpenChapter(ch)}>
                          <span className="ch-title">
                            {ch.title || `Capítulo ${ch.idx + 1}`}
                          </span>
                          <span className="ch-progress" title={`${ch.reached} de ${ch.sentences} alcanzadas`}>
                            <span className="track">
                              <span className="fill" style={{ width: `${pct}%` }} />
                            </span>
                            <span className="meta">
                              {ch.reached}/{ch.sentences}
                              {/* «Practicado» es distinto de «leído»: haber pasado
                                  por una oración no es haberla dicho en voz alta. */}
                              {ch.practiced > 0 && (
                                <em title={`${ch.practiced} leídas en voz alta`}>
                                  {' '}· {ch.practiced} ✦
                                </em>
                              )}
                            </span>
                          </span>
                        </button>
                      </li>
                    )
                  })}
                </ol>
              </>
            )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
