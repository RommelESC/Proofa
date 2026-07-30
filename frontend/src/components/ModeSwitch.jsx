import { Coach, Guided, Listen, Read, Shadowing } from './icons'

/**
 * Los cinco modos de lectura, dentro del lector.
 *
 * `ready: false` marca lo que todavía no existe. Se muestran igual — la
 * estructura del producto se entiende mejor completa — pero cambiar a uno
 * dice honestamente que falta construirlo, en vez de fingir una pantalla
 * vacía que parezca rota.
 */
export const MODES = [
  {
    key: 'read',
    label: 'Leer',
    Icon: Read,
    ready: true,
    blurb: 'Lectura con ayuda graduada en español.',
  },
  {
    key: 'listen',
    label: 'Escuchar',
    Icon: Listen,
    ready: true,
    blurb: 'Lectura pasiva: la app lee y marca la palabra actual, con la velocidad al frente.',
  },
  {
    key: 'guided',
    label: 'Guiada',
    Icon: Guided,
    ready: true,
    blurb: 'Lectura silenciosa con marcapasos: una banda avanza a tu velocidad objetivo.',
  },
  {
    key: 'shadowing',
    label: 'Shadowing',
    Icon: Shadowing,
    ready: true,
    blurb:
      'Escuchas una oración y la repites encima. Compara tu ritmo con el del modelo, ' +
      'palabra por palabra.',
  },
  {
    key: 'coach',
    label: 'Coach',
    Icon: Coach,
    ready: true,
    blurb: 'Lees en voz alta y Profa corrige al cerrar cada oración.',
  },
]

export default function ModeSwitch({ mode, onChange }) {
  return (
    <div className="mode-switch" role="tablist" aria-label="Modo de lectura">
      {MODES.map(({ key, label, Icon, ready }) => (
        <button
          key={key}
          role="tab"
          aria-selected={mode === key}
          className={`${mode === key ? 'active' : ''} ${ready ? '' : 'pending'}`}
          onClick={() => onChange(key)}
          title={ready ? label : `${label} — todavía no construido`}
        >
          <Icon size={16} />
          <span>{label}</span>
        </button>
      ))}
    </div>
  )
}
