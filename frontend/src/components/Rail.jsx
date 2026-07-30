import { Library, Phonemes, Progress, Read, Settings } from './icons'

/**
 * Riel de navegación: los cinco destinos reales de la app.
 *
 * Los modos de lectura (Escuchar, Guiada, Shadowing, Coach) NO están aquí a
 * propósito. No son destinos: son maneras de leer un mismo texto, y viven
 * como conmutador dentro del lector para que nunca pierdas el libro ni la
 * posición al cambiar de uno a otro.
 */
const DESTINATIONS = [
  { key: 'library', label: 'Biblioteca', Icon: Library },
  { key: 'read', label: 'Leer', Icon: Read },
  { key: 'phonemes', label: 'Fonemas', Icon: Phonemes },
  { key: 'progress', label: 'Progreso', Icon: Progress },
  { key: 'settings', label: 'Ajustes', Icon: Settings },
]

export default function Rail({ active, onNavigate, health }) {
  const engineOk = health?.database?.ok && health?.engines?.[health.active_engine]?.ready

  return (
    <nav className="rail" aria-label="Navegación principal">
      <div className="rail-mark" title="Profa">
        <span>P</span>
      </div>

      <ul>
        {DESTINATIONS.map(({ key, label, Icon }) => (
          <li key={key}>
            <button
              className={active === key ? 'active' : ''}
              onClick={() => onNavigate(key)}
              aria-current={active === key ? 'page' : undefined}
            >
              <Icon />
              <span>{label}</span>
            </button>
          </li>
        ))}
      </ul>

      {/* La línea técnica del original se reduce a un punto. El detalle
          completo vive en Ajustes, que es donde se busca cuando algo falla. */}
      <button
        className="rail-status"
        onClick={() => onNavigate('settings')}
        title={
          health
            ? `motor ${health.active_engine} · base ${health.database.ok ? 'conectada' : 'sin conexión'}`
            : 'comprobando…'
        }
        aria-label="Estado del sistema"
      >
        <span className={`dot ${health ? (engineOk ? 'ok' : 'warn') : ''}`} />
      </button>
    </nav>
  )
}
