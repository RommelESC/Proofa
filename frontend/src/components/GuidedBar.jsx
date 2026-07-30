/**
 * Controles del marcapasos.
 *
 * La velocidad se ofrece como pasos sobre TU velocidad medida, no como cifras
 * absolutas sacadas de una tabla. «140 wpm» no significa nada por sí solo;
 * «+20% sobre lo tuyo» sí, y deja claro que empujar es una decisión tuya y no
 * un ajuste escondido.
 */
const STEPS = [
  { factor: 0.9, label: 'cómodo' },
  { factor: 1, label: 'tu ritmo' },
  { factor: 1.2, label: '+20%' },
  { factor: 1.45, label: '+45%' },
]

export default function GuidedBar({ guided, pace, onExit }) {
  const { playing, wpm, setWpm, toggle, stop, word, words, remaining } = guided
  const base = pace?.wpm ?? 110
  const done = words ? Math.round((word / words) * 100) : 0

  return (
    <aside className="guided-bar" role="region" aria-label="Lectura guiada">
      <div className="bar-inner">
        <div className="guided-main">
          <div className="transport">
            <button className="primary" onClick={toggle}>
              {playing ? 'Pausa' : word > 0 ? 'Continuar' : 'Empezar'}
            </button>
            <button onClick={stop} disabled={!word} title="Volver al principio">
              ⟲
            </button>
          </div>

          <span className="pace mono">{Math.round(wpm)} wpm</span>

          <div className="rates" role="group" aria-label="Velocidad">
            {STEPS.map((s) => {
              const target = Math.round(base * s.factor)
              return (
                <button
                  key={s.label}
                  className={Math.round(wpm) === target ? 'active' : ''}
                  onClick={() => setWpm(target)}
                  title={`${target} palabras por minuto`}
                >
                  {s.label}
                </button>
              )
            })}
          </div>

          <button className="dismiss" onClick={onExit} aria-label="Salir de Guiada">
            &times;
          </button>
        </div>

        <div className="guided-progress">
          <span className="track">
            <span className="fill" style={{ width: `${done}%` }} />
          </span>
          <span className="counter mono">
            {word}/{words} palabras
            {remaining != null && word < words && ` · ~${remaining} min`}
          </span>
        </div>

        {pace && (
          <p className="hint">
            {pace.measured
              ? `Tu ritmo son ${pace.wpm} wpm, la mediana de ${pace.samples} lecturas tuyas en voz alta (${pace.slowest}–${pace.fastest}).`
              : `Todavía no hay lecturas limpias suficientes para medir tu ritmo, así que se parte de ${pace.wpm} wpm. Se ajustará solo cuando grabes más.`}{' '}
            No vuelvas atrás aunque pierdas algo: releer es el hábito que se
            viene a quitar.
          </p>
        )}
      </div>
    </aside>
  )
}
