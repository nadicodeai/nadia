/*
 * Italian catalog. Fork-authored, so the product name is written "Nadia"
 * directly (no rename pass needed). Mirrors `Catalog` exactly — the compiler
 * rejects any missing key, keeping it structurally in step with en.
 */
import type { Catalog } from './types'

export const it: Catalog = {
  welcome: {
    tagline: 'L’agente che cresce con te. Prepareremo tutto in background — bastano pochi minuti.',
    installCta: 'Installa Nadia'
  },
  progress: {
    titleInstall: 'Configurazione di Nadia Agent',
    titleUpdate: 'Aggiornamento di Nadia',
    titleDone: 'Fatto',
    descInstall:
      'Questa è una configurazione una tantum. Il programma di installazione di Nadia sta scaricando le dipendenze e configurando il tuo computer. Gli avvii successivi salteranno questo passaggio.',
    descUpdate: 'Nadia si sta aggiornando all’ultima versione — richiede solo un momento.',
    stepsComplete: (done, total) => `${done} di ${total} passaggi completati`,
    liveOutput: 'Output in tempo reale',
    lineCount: (n) => `${n} ${n === 1 ? 'riga' : 'righe'}`,
    showDetails: 'Mostra dettagli',
    hideDetails: 'Nascondi dettagli',
    cancel: 'Annulla',
    loading: 'Caricamento…'
  },
  success: {
    ready: 'Nadia è pronta',
    launchHintBefore: 'Puoi avviarla da qui, o in qualsiasi momento dal terminale con ',
    launchHintAfter: '.',
    launch: 'Avvia Nadia',
    launching: 'Avvio in corso',
    launchErrorTitle: 'Impossibile avviare l’app desktop',
    launchErrorGeneric: 'Impossibile avviare l’app desktop. Consulta i dettagli qui sotto.'
  },
  failure: {
    titleInstall: 'Installazione non completata',
    titleUpdate: 'Aggiornamento non completato',
    defaultErrorInstall: 'Qualcosa è andato storto durante l’installazione.',
    defaultErrorUpdate: 'Qualcosa è andato storto durante l’aggiornamento.',
    retryInstall: 'Riprova installazione',
    retryUpdate: 'Riprova aggiornamento',
    openLogs: 'Apri i log',
    logLabel: 'Log:'
  },
  // Terse register (house style): the stage row narrows to half-width with the
  // log panel open and truncates — keep each label short enough to read whole.
  stages: {
    prerequisites: 'Prerequisiti di sistema',
    uv: 'Gestore pacchetti uv',
    python: 'Ambiente Python',
    git: 'Installazione di Git',
    node: 'Runtime Node',
    'system-packages': 'Pacchetti di sistema',
    repository: 'Clonazione del repository',
    repo: 'Clonazione del repository',
    venv: 'Ambiente virtuale Python',
    dependencies: 'Dipendenze Python',
    'python-deps': 'Dipendenze Python',
    'node-deps': 'Dipendenze Node.js',
    desktop: 'Compilazione app desktop',
    path: 'Aggiunta al PATH',
    config: 'Configurazione e competenze',
    'config-templates': 'Modelli di configurazione',
    'platform-sdks': 'SDK di messaggistica',
    'bootstrap-marker': 'Installazione completata',
    setup: 'Chiavi API e impostazioni',
    configure: 'Chiavi API e modelli',
    gateway: 'Servizio gateway',
    complete: 'Completamento',
    handoff: 'Preparazione',
    update: 'Download aggiornamento',
    rebuild: 'Ricompilazione app desktop',
    install: 'Installazione aggiornamento'
  },
  causes: {
    alreadyRunning: 'Nadia è ancora in esecuzione. Chiudi tutte le finestre di Nadia e riprova.',
    notInstalled:
      'Nadia non è installata qui. Riesegui il programma di installazione per ripararla.',
    rebuild:
      'Impossibile ricompilare l’app desktop. L’aggiornamento è stato applicato — avvia `nadia desktop` dal terminale per completarlo.',
    desktopMissing:
      'App desktop non trovata. Il passaggio di compilazione potrebbe essere stato saltato — avvia `nadia desktop` dal terminale.',
    gitMissing:
      'Git non è installato e non è stato possibile installarlo automaticamente. Installa Git dal link indicato sopra, poi riprova.',
    download: 'Download non riuscito. Verifica la connessione a internet e riprova.',
    disk: 'Spazio su disco insufficiente. Libera spazio e riprova.',
    permission: 'Autorizzazioni insufficienti. Riprova con i permessi necessari.',
    cancelled: 'Operazione annullata.'
  },
  errorDetailLabel: 'Dettagli:'
}
