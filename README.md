# Lectura en voz alta

Lee libros en inglés con traducción paralela al español, y **léelos en voz alta
para recibir corrección fonética en contexto**, con la taxonomía de errores
típicos de un hispanohablante.

La apuesta del proyecto: como siempre lees un texto conocido, el sistema sabe
qué *deberías* estar diciendo. Eso convierte "evaluar pronunciación libre"
(difícil, poco confiable) en "verificar una lectura contra su referencia"
(mucho más resuelto y preciso). El formato de libro no es solo contenido: es lo
que hace viable la corrección.

## Qué hace

Importas un EPUB tuyo y lo lees de cinco maneras distintas. No son cinco
secciones de la aplicación: son cinco formas de leer **el mismo texto**, y se
cambia entre ellas sin perder el libro ni la posición.

| Modo | Para qué |
|---|---|
| **Leer** | El español al lado, graduable. Toca una palabra y te dice qué significa *en esa oración*. |
| **Escuchar** | Narración con resaltado palabra por palabra, con los tiempos que da el sintetizador — no estimados. |
| **Guiada** | Lectura silenciosa con marcapasos a **tu** velocidad medida. Entrena a no volver atrás. |
| **Shadowing** | Escuchas una oración, la repites encima, y compara tu **ritmo** con el del modelo. |
| **Coach** | Lees en voz alta y recibes corrección fonética al cerrar cada oración. |

La ayuda en español es graduable: el modo **ayuda graduada** muestra la
traducción solo en una fracción de las oraciones. Bajas el porcentaje conforme
mejoras. Un lector bilingüe que siempre te da la traducción termina haciendo
que leas en español.

Y lo que corrige se mide **contra ti**, no contra un umbral fijo. Un sonido que
siempre te sale en 70 cuando el resto te sale en 85 es lo peor que haces, y
ningún umbral absoluto lo ve. Pero una debilidad solo se declara cuando la
diferencia sobrevive a su propio margen de error: con siete muestras ruidosas
cualquier fonema parece débil, y un diagnóstico convincente construido sobre
ruido te manda a practicar lo que no toca.

De ahí salen las dos cosas que cierran el círculo: **práctica dirigida** con
frases de tu propio libro para el sonido que peor llevas, e **informe de
sesión** al terminar.

## Arquitectura

Dos capas que se mantienen separadas a propósito:

| Capa | Responsabilidad | Implementación |
|---|---|---|
| **Oreja** | audio → fonemas, alineación contra el texto esperado, score por palabra y fonema | `app/engines/` — `mock`, `azure`, `local` |
| **Maestro** | interpretar ese JSON, diagnosticar el patrón, explicar y generar el drill | `app/phonology/patterns.py` |
| **Contenido** | EPUB → capítulos → oraciones; traducción y glosas en contexto | `app/content/`, `app/llm/` |

Un motor no sabe nada de pedagogía y la pedagogía no sabe nada de audio.
Por eso se puede empezar con un motor de pago para validar la UX y cambiarlo
después por uno local sin tocar el resto. La capa LLM sigue el mismo patrón:
sin llave de API el lector funciona igual, solo que en inglés.

> **Nota:** un ASR optimizado para exactitud (Whisper, por ejemplo) **no sirve**
> aquí. Está entrenado para entenderte a pesar de tu acento: si dices *"I sink
> so"* transcribe *"I think so"* y borra justo el error que queremos medir.
> Por eso los motores reales usan reconocimiento **fonémico**.

### Jerarquía de verdad de los datos

1. **el WAV en disco** — nunca se borra
2. **`attempts.raw` (jsonb)** — payload íntegro del motor, sin tocar
3. **`word_scores` / `phoneme_scores`** — derivado, recalculable
4. **`pattern_hits`** — derivado, recalculable al afinar reglas

Cada `attempt` registra con qué motor y versión se midió. Sin eso, al cambiar
de motor el historial se vuelve incomparable sin que te des cuenta.

## Requisitos

- Python 3.11+
- Node 20+
- PostgreSQL 16+

## Puesta en marcha

### 1. Base de datos

Crea el rol y la base. Cambia la contraseña por una tuya — la de aquí es solo
un ejemplo, y va a acabar en tu `.env`:

```bash
psql -U postgres -c "CREATE ROLE ingles LOGIN PASSWORD 'cambia-esto'; CREATE DATABASE ingles OWNER ingles;"
```

Si tu Postgres no está en el 5432, añade `-p <puerto>` y ajusta después
`DATABASE_URL`. En Windows quizá tengas que dar la ruta completa a `psql`
(`"/c/Program Files/PostgreSQL/16/bin/psql"`).

### 2. Configuración

```bash
cp .env.example .env
```

Ajusta `DATABASE_URL` si usaste otras credenciales.

### 3. Backend

```bash
cd backend && python -m venv .venv && ./.venv/Scripts/python.exe -m pip install -r requirements.txt
```

Genera y aplica la migración inicial (autogenerate valida el esquema contra
tu base real, que es más confiable que una migración escrita a mano):

```bash
cd backend && ./.venv/Scripts/alembic.exe revision --autogenerate -m "initial" && ./.venv/Scripts/alembic.exe upgrade head
```

Arranca:

```bash
cd backend && ./.venv/Scripts/uvicorn.exe app.main:app --reload --port 8000
```

Verifica en `http://localhost:8000/api/health` — reporta el motor activo, el
g2p en uso y el estado de la base.

### 4. Frontend

```bash
cd frontend && npm install && npm run dev
```

Abre `http://localhost:5173`.

## Motores de pronunciación

Se elige con `PRONUNCIATION_ENGINE` en `.env`.

| Motor | Costo | Calidad | Para qué |
|---|---|---|---|
| `mock` | 0 | ninguna (scores **falsos**) | validar el circuito completo sin llaves ni descargas |
| `azure` | ~1 USD/hora de audio | la mejor disponible | validar rápido si la corrección es útil de verdad |
| `local` | 0 | por medir | el entregable open source: sin llaves, sin nube, sin que la voz salga de la máquina |

El orden recomendado es **azure primero para validar, local después para
liberar**: una herramienta open source que exige una API key de pago tiene
adopción prácticamente nula.

Detalle que no es obvio: el motor local devuelve la secuencia de fonemas
**realmente producida**, mientras que Azure solo puntúa la esperada. Para los
detectores de `patterns.py` — que buscan sustituciones concretas — el motor
local es *mejor*, no solo más barato.

### Conectar Azure

1. En [portal.azure.com](https://portal.azure.com), crea un recurso **Speech service**
   (dentro de Azure AI services). El **tier F0 es gratuito**: 5 horas de audio al
   mes, de sobra para validar si la corrección sirve.
2. Elige una región cercana — desde México, `southcentralus` es la de menor latencia.
3. En **Keys and Endpoint**, copia *Key 1* y *Location/Region*.
4. En `.env`:

```
PRONUNCIATION_ENGINE=azure
AZURE_SPEECH_KEY=<tu llave>
AZURE_SPEECH_REGION=southcentralus
```

```bash
cd backend && ./.venv/Scripts/python.exe -m pip install -r requirements-azure.txt
```

Para probarlo con una grabación real, usa el script de diagnóstico. Graba una
frase desde la interfaz (queda en `data/assets/recordings/`) y reevalúala:

```bash
cd backend && ./.venv/Scripts/python.exe scripts/check_engine.py ../data/assets/recordings/2026-07/<archivo>.wav "I think so" --engine azure --raw
```

`--raw` vuelca el payload íntegro de Azure, que es lo que hay que mirar cuando
un score no cuadra con lo que oíste. Como las grabaciones nunca se borran,
puedes reevaluar la misma muestra con distintos motores y compararlos
directamente.

#### Qué NO es `NBestPhonemes`

Azure devuelve, por fonema, una lista de candidatos con un `Score`. **Ese
score no es la probabilidad de haber producido ese sonido**: es un ranking
normalizado donde el primer candidato casi siempre saca 100, incluso cuando
el fonema esperado se pronunció bien.

Medición real de `/b/` en *breathe*, bien pronunciada:

```
/b/  AccuracyScore=60  NBest=[ʊ:100, b:95, w:59, v:53, ə:50]
```

La `/b/` sonó — ese `/ʊ/` es la vocal contigua filtrándose en la ventana de
alineación. Leer `NBest[0]` como "lo que dijiste" fabrica errores inexistentes.

La señal confiable es el `AccuracyScore` propio del fonema; `NBest` solo sirve
para *nombrar* el sustituto cuando ya se sabe que el esperado falló. Por eso
`_produced_phoneme` exige las tres condiciones a la vez (accuracy baja, otro
candidato por encima, margen amplio) y ante la duda devuelve el esperado.

### Motor local

```bash
cd backend && ./.venv/Scripts/python.exe -m pip install -r requirements-local.txt
```

## Traducción paralela

Se traduce **oración por oración**, no el texto corrido. Eso hace que la
alineación bilingüe salga perfecta por construcción, sin alineadores
automáticos: la salida estructurada de la API garantiza un elemento por
oración de entrada.

```bash
cd backend && ./.venv/Scripts/python.exe -m pip install -r requirements-llm.txt
```

Luego pon `LLM_PROVIDER=claude` y tu `ANTHROPIC_API_KEY` en `.env`. Sin eso el
lector muestra solo el inglés — degrada, no falla.

Detalles de costo: el prompt de sistema va marcado con `cache_control` (idéntico
en cada lote, así que importar un libro entero es mucho más barato), y la
traducción corre con `effort: "low"` porque es una tarea mecánica. Las glosas
usan `medium`: desambiguar el sentido en contexto sí es un juicio fino.

## Escuchar la pronunciación correcta

Después de cada intento, las palabras que fallaste traen dos botones: **🔊
normal** y **🐢 lento**. Y cada patrón detectado trae sus **pares mínimos**
(*think / sink*, *very / berry*) con audio en ambos lados.

Los pares no son un adorno. Oír los dos sonidos seguidos es como se aprende a
percibir un contraste que tu idioma no distingue — decirte *"pronuncia /θ/"* no
sirve de nada si no puedes oír en qué se diferencia de /s/. Y la velocidad
reducida es lo que permite percibir un sonido dentro de un grupo consonántico
como la `/t/` final de *asked*.

Usa la **misma llave de Azure** que la evaluación, con voz neuronal. El tier F0
incluye 0.5 M de caracteres al mes y una palabra son ~6: para este uso es
efectivamente ilimitado.

Dos detalles de implementación que importan:

- **Se fuerza la pronunciación con SSML fonético** (`<phoneme alphabet="ipa">`)
  en lugar de dejar que el motor adivine leyendo la grafía. Para enseñar un
  fonema concreto eso no es un lujo: el IPA viaja desde `phoneme_scores`, así
  que oyes exactamente el sonido que falló.
- **Caché en disco** por petición (voz + texto + IPA + velocidad). Medido:
  0.90 s la primera vez, **0.21 s desde caché**. Las palabras que fallas se
  repiten mucho; sin caché cada repaso volvería a pagar la llamada.

## Taxonomía de errores

`app/phonology/patterns.py` define 12 patrones de interferencia del español:
`TH_TO_S`, `DH_TO_D`, `EPENTHETIC_E` (*"espeak"* por *speak*), `VOWEL_IY_IH`
(*ship/sheep*), `SCHWA_FULL`, `B_V_MERGE`, `Z_TO_S`, `ED_ENDING`,
`FINAL_CLUSTER`, `Y_TO_JH`, `NG_TO_N`, `WORD_STRESS`.

Cada uno lleva explicación en español y pares mínimos. La definición vive en
código y se sincroniza a la tabla `error_patterns` al arrancar.

Los detectores son **derivados**: si afinas una regla, puedes recalcular
`pattern_hits` sobre todo el historial sin volver a grabar nada.

## Calibración

El riesgo número uno del proyecto no es técnico, es de confianza: **si el
sistema te dice que pronunciaste mal algo que dijiste bien, dejas de creerle
y abandonas**. Por eso los umbrales son deliberadamente indulgentes
(`PHONEME_FAIL = 55`, `MIN_WEIGHT = 0.4` en `scoring.py`).

Siendo una herramienta personal tienes una ventaja que un producto comercial
no tiene: **eres el dataset**. Grábate diciendo 30 palabras bien y 30 mal a
propósito (con tu /θ/→/s/, tu *e-* de apoyo, tu /ɪ/ vs /iː/) y úsalas como
suite de regresión cada vez que muevas un umbral o cambies de motor.

## Privacidad y datos

- Todo es local. No hay cuentas, no hay servidor remoto, la voz no sale de la máquina.
- Las grabaciones **no se borran**: permiten re-evaluar todo el historial al
  cambiar de motor y comparar ambos contra las mismas muestras. 20 min diarios
  a 16 kHz mono son ~14 GB al año.
- `data/`, `.env` y cualquier dump están en `.gitignore` desde el primer commit.

## Licencia

MIT — ver [LICENSE](LICENSE). Úsalo, modifícalo y redistribúyelo como quieras.

## Contenido: los libros son otra cosa

La licencia de arriba cubre **el código**. El repositorio **no distribuye
libros**: distribuye la herramienta, y el contenido lo importa cada quien en su
propia máquina.

Ojo con un detalle que se pasa por alto: una traducción al español tiene
copyright propio, independiente del original. Que *Moby Dick* sea de dominio
público no hace que su traducción de 1990 lo sea. La salida limpia es traducir
tú mismo la obra de dominio público — y como se traduce oración por oración,
la alineación bilingüe sale perfecta por construcción.

## Estado

Funciona de punta a punta contra Postgres real con Azure como motor, medido con
voz humana. Los cinco modos están construidos. 114 pruebas.

Lo que hay, además de los modos:

- **Línea base personal por fonema**, con control de significancia. Cuando no
  hay evidencia suficiente lo dice, y calcula cuántas lecturas faltan para
  saberlo — en lugar de callar o de inventarse una certeza.
- **Práctica dirigida** con palabras y frases de tu propio libro, filtradas por
  CMUdict para no acabar practicando restos de la extracción del EPUB.
- **Informe de sesión**, con las sesiones derivadas del ritmo de grabación (no
  hay botón de empezar ni terminar: se olvidan y envenenan los agregados).
- **Dificultad por libro**: Flesch con sílabas contadas por pronunciación real,
  más un recuento de arcaísmos, porque la fórmula no ve la gramática del XVII.

Falta:

- `local.py` no se ha probado contra el modelo descargado.
- Los umbrales absolutos (`PHONEME_FAIL`) siguen sin calibrarse contra un
  corpus propio; la línea base personal los complementa pero no los sustituye.
- Sin versión móvil.

## ¿Es confiable la corrección?

Sí. Es la pregunta que decidía si el proyecto valía la pena, y está medida con
voz humana real (misma frase, mismo hablante, misma sesión):

| Lectura | Global | Patrones detectados |
|---|---|---|
| Normal (×3) | 89.5 – 92.3 | **2**, siempre los mismos |
| Con errores forzados a propósito | 68.5 | **6** |

Las tres lecturas normales detectaron exactamente el mismo error real y
repetible —la `/t/` final de *asked* (`æ s k t`), score 41— y nada más. La
lectura con errores deliberados bajó 23 puntos y sumó cuatro patrones. **La
señal discrimina, y no hay ruido en las lecturas limpias.**

### La limitación que hay que conocer

Azure identifica de forma fiable **que** un fonema falló, pero rara vez **con
qué lo sustituiste**. En una lectura donde se dijo *"sink"* por *think* a
propósito, la `/θ/` cayó de 100 a 60 y aun así vino reportada como `/θ/`.

Por eso `_substitution` tiene tres niveles de confianza: **0.9** con
sustitución explícita, **0.55** cuando solo se sabe que el fonema salió mal, y
**0.5** cuando no se articuló. Exigir la sustitución explícita dejaba mudos a
la mitad de los detectores; afirmarla sin evidencia sería inventar.

### La línea base personal, y por qué lleva un freno

Los umbrales absolutos (`PHONEME_FAIL = 55`) no ven este caso: una `/θ/` en 60
no es "mala" en abstracto, pero para quien normalmente la produce en 100 sí es
una caída real. El umbral correcto es **personal y por fonema**, y sale de
`phoneme_scores` — que existe justamente para esto.

Está construido (`services/baseline_service.py`), y la parte que importa no es
la media sino el freno. Cada fonema se compara contra la media del **resto** de
los tuyos, y solo se declara debilidad si la diferencia sobrevive a su propio
margen de error. Medido sobre datos reales: un `/ʃ/` con media 72.9 parecía un
punto débil evidente, pero con n=7 y desviación 26.3 su intervalo llegaba a
92.4 — indistinguible del resto. Sin ese freno, el sistema habría redactado un
diagnóstico convincente sobre ruido.

Cuando no alcanza, no calla: dice cuántas lecturas más hacen falta para
resolverlo, al ritmo real de ese fonema en concreto.

El mapeo de campos de `azure.py` está verificado con casos que vienen de
mediciones reales, incluidos los que costaron un bug: `tests/` alimenta el
parser con payloads de la forma real del servicio y comprueba scores, tiempos,
sustituciones vía `NBestPhonemes` y que la taxonomía dispare sobre datos de
Azure sin tocar una línea.

```bash
cd backend && ./.venv/Scripts/python.exe -m pytest -q
```

- La traducción con Claude no se ha ejecutado contra la API real; con Ollama sí,
  y es el camino recomendado (no sale texto de tu máquina).
- pgvector no está instalado en este Postgres; los embeddings van en una
  migración posterior.
- El TTS neuronal ya sustituyó a la Web Speech API del navegador, cacheado por
  oración y con marcas de tiempo por palabra — que es lo que permite el
  resaltado del modo Escuchar y la comparación de ritmo de Shadowing. La voz
  del navegador sigue disponible detrás de la misma interfaz, como respaldo
  gratuito.
