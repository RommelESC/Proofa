import { useEffect, useState } from 'react'

import { getHealth } from './api'
import Rail from './components/Rail'
import Library from './views/Library'
import Phonemes from './views/Phonemes'
import Progress from './views/Progress'
import Reader from './views/Reader'
import Settings from './views/Settings'

export default function App() {
  const [view, setView] = useState('library')
  const [chapter, setChapter] = useState(null)
  // Modo con el que abrir el lector. La pantalla de inicio ofrece tres puertas
  // al mismo capítulo — leer, escuchar, coach — y cada una tiene que llegar ya
  // en su modo, no dejarte buscándolo en la pestaña de arriba.
  const [mode, setMode] = useState('read')
  const [health, setHealth] = useState(null)
  // Sonido con el que abrir Fonemas cuando llegas desde «Practicar /aɪ/».
  const [sound, setSound] = useState(null)

  useEffect(() => {
    getHealth().then(setHealth).catch(() => {})
  }, [])

  function navigate(key) {
    // «Leer» sin capítulo abierto no tiene nada que mostrar: manda a elegirlo.
    if (key === 'read' && !chapter) {
      setView('library')
      return
    }
    setView(key)
  }

  /** Ir a practicar un sonido concreto, desde donde se haya señalado. */
  function practise(ipa = null) {
    setSound(ipa)
    setView('phonemes')
  }

  function openChapter(next, startMode = 'read') {
    setChapter(next)
    setMode(startMode)
    setView('read')
  }

  return (
    <div className="shell">
      <Rail active={view} onNavigate={navigate} health={health} />

      <main className="main">
        {view === 'library' && (
          <Library onOpenChapter={openChapter} onPractice={() => practise(null)} />
        )}
        {view === 'read' && chapter && (
          <Reader
            key={`${chapter.id}:${mode}`}
            chapter={chapter}
            initialMode={mode}
            onOpenChapter={openChapter}
            onPractice={practise}
            onBack={() => setView('library')}
          />
        )}
        {view === 'phonemes' && <Phonemes key={sound ?? 'auto'} initialSound={sound} />}
        {view === 'progress' && <Progress />}
        {view === 'settings' && <Settings health={health} />}
      </main>
    </div>
  )
}
