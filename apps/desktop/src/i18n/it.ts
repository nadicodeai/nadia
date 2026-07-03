import { defineFieldCopy } from '@/app/settings/field-copy'

import { defineLocale } from './define-locale'

const FIELD_LABELS = defineFieldCopy({
  display: {
    showReasoning: 'Blocchi di ragionamento'
  }
})

const FIELD_DESCRIPTIONS = defineFieldCopy({
  display: {
    showReasoning: 'Mostra il ragionamento quando il backend lo fornisce.'
  }
})

export const it = defineLocale({
  common: {
    apply: 'Applica',
    back: 'Indietro',
    save: 'Salva',
    saving: 'Salvataggio…',
    cancel: 'Annulla',
    change: 'Cambia',
    choose: 'Scegli',
    clear: 'Cancella',
    close: 'Chiudi',
    collapse: 'Comprimi',
    confirm: 'Conferma',
    connect: 'Connetti',
    connecting: 'Connessione',
    continue: 'Continua',
    copied: 'Copiato',
    copy: 'Copia',
    copyFailed: 'Copia non riuscita',
    delete: 'Elimina',
    docs: 'Documentazione',
    done: 'Fatto',
    error: 'Errore',
    failed: 'Non riuscito',
    free: 'Gratuito',
    loading: 'Caricamento…',
    notSet: 'Non impostato',
    refresh: 'Aggiorna',
    remove: 'Rimuovi',
    replace: 'Sostituisci',
    retry: 'Riprova',
    run: 'Esegui',
    send: 'Invia',
    set: 'Imposta',
    skip: 'Salta',
    update: 'Aggiorna',
    on: 'Attivo',
    off: 'Disattivo'
  },

  boot: {
    ready: 'Nadia Desktop è pronto',
    desktopBootFailedWithMessage: message => `Avvio del desktop non riuscito: ${message}`,
    steps: {
      connectingGateway: 'Connessione al gateway desktop in tempo reale',
      loadingSettings: 'Caricamento delle impostazioni di Nadia',
      loadingSessions: 'Caricamento delle sessioni recenti',
      startingDesktopConnection: 'Avvio della connessione desktop',
      startingNadiaDesktop: 'Avvio di Nadia Desktop…'
    },
    errors: {
      backgroundExited: 'Il processo in background di Nadia si è chiuso.',
      backgroundExitedDuringStartup: "Il processo in background di Nadia si è chiuso durante l'avvio.",
      backendStopped: 'Backend arrestato',
      desktopBootFailed: 'Avvio del desktop non riuscito',
      gatewayConnectionLost: 'Connessione al gateway persa',
      gatewaySignInRequired: 'Accesso al gateway richiesto',
      ipcBridgeUnavailable: 'Bridge IPC desktop non disponibile.'
    },
    failure: {
      title: 'Nadia non è riuscita ad avviarsi',
      description:
        'Il gateway in background non si è avviato. Prova una delle azioni di recupero qui sotto. Chat e impostazioni non verranno eliminate.',
      remoteTitle: 'Accesso al gateway remoto richiesto',
      remoteDescription:
        'La sessione del gateway remoto è scaduta. Accedi di nuovo per riconnetterti. Chat e impostazioni non verranno eliminate.',
      retry: 'Riprova',
      repairInstall: 'Ripara installazione',
      useLocalGateway: 'Usa gateway locale',
      openLogs: 'Apri log',
      repairHint: "La riparazione riesegue l'installer e può richiedere alcuni minuti su una macchina nuova.",
      remoteSignInHint: 'Apre la finestra di accesso al gateway. Usa il gateway locale per passare al backend incluso.',
      hideRecentLogs: 'Nascondi log recenti',
      showRecentLogs: 'Mostra log recenti',
      signedInTitle: 'Accesso effettuato',
      signedInMessage: 'Riconnessione al gateway remoto…',
      signInIncompleteTitle: 'Accesso incompleto',
      signInIncompleteMessage: "La finestra di login è stata chiusa prima del completamento dell'autenticazione.",
      signInFailed: 'Accesso non riuscito',
      signInToRemoteGateway: 'Accedi al gateway remoto',
      signInWithProvider: provider => `Accedi con ${provider}`,
      identityProvider: 'il provider di identità'
    }
  },

  notifications: {
    region: 'Notifiche',
    hide: 'Nascondi',
    show: 'Mostra',
    more: count => `${count} ${count === 1 ? 'notifica' : 'notifiche'} in più`,
    clearAll: 'Cancella tutto',
    dismiss: 'Ignora notifica',
    details: 'Dettagli',
    copyDetail: 'Copia dettaglio',
    copyDetailFailed: 'Impossibile copiare il dettaglio della notifica',
    backendOutOfDateTitle: 'Backend non aggiornato',
    backendOutOfDateMessage:
      'Il backend di Nadia è più vecchio di questa build desktop e potrebbe non funzionare correttamente. Aggiornalo per allinearli.',
    updateNadia: 'Aggiorna Nadia',
    updateReadyTitle: 'Aggiornamento pronto',
    updateReadyMessage: count => `${count} ${count === 1 ? 'modifica disponibile' : 'modifiche disponibili'}.`,
    seeWhatsNew: 'Guarda le novità',
    native: {
      approvalTitle: 'Approvazione richiesta',
      approveAction: 'Approva',
      rejectAction: 'Rifiuta',
      inputTitle: 'Input richiesto',
      inputBody: 'Nadia attende una tua risposta.',
      turnDoneTitle: 'Nadia ha finito',
      turnDoneBody: 'La risposta è pronta.',
      turnErrorTitle: 'Turno non riuscito',
      backgroundDoneTitle: 'Attività in background completata',
      backgroundFailedTitle: 'Attività in background non riuscita'
    }
  },

  language: {
    label: 'Lingua',
    description: "Scegli la lingua dell'interfaccia desktop.",
    saving: 'Salvataggio lingua…',
    saveError: 'Aggiornamento della lingua non riuscito',
    switchTo: 'Cambia lingua',
    searchPlaceholder: 'Cerca lingue…',
    noResults: 'Nessuna lingua trovata'
  },

  assistant: {
    tool: {
      actions: {
        read: 'Letto',
        reading: 'Lettura'
      },
      titleTemplates: {
        actionTarget: (action, target) => `${action} ${target}`
      },
      titles: {
        read_file: { done: 'File letto', pending: 'Lettura file', pendingAction: 'Lettura' },
        web_extract: { done: 'Pagina letta', pending: 'Lettura pagina', pendingAction: 'Lettura' }
      }
    }
  },

  settings: {
    closeSettings: 'Chiudi impostazioni',
    exportConfig: 'Esporta configurazione',
    importConfig: 'Importa configurazione',
    resetToDefaults: 'Ripristina predefiniti',
    resetConfirm: 'Ripristinare tutte le impostazioni predefinite di Nadia?',
    exportFailed: 'Esportazione non riuscita',
    resetFailed: 'Ripristino non riuscito',
    nav: {
      providers: 'Provider',
      providerAccounts: 'Account',
      providerApiKeys: 'Chiavi API',
      gateway: 'Gateway',
      apiKeys: 'Strumenti e chiavi',
      keysTools: 'Strumenti',
      keysSettings: 'Impostazioni',
      mcp: 'MCP',
      archivedChats: 'Chat archiviate',
      about: 'Informazioni',
      notifications: 'Notifiche'
    },
    sections: {
      model: 'Modello',
      chat: 'Chat',
      appearance: 'Aspetto',
      workspace: 'Area di lavoro',
      safety: 'Sicurezza',
      memory: 'Memoria e contesto',
      voice: 'Voce',
      advanced: 'Avanzate'
    },
    searchPlaceholder: {
      about: 'Informazioni su Nadia Desktop',
      config: 'Cerca impostazioni...',
      gateway: 'Connessione gateway...',
      keys: 'Cerca chiavi API...',
      mcp: 'Cerca server MCP...',
      sessions: 'Cerca sessioni archiviate...'
    },
    modeOptions: {
      light: { label: 'Chiaro', description: 'Superfici desktop luminose' },
      dark: { label: 'Scuro', description: 'Area di lavoro a bassa luminosità' },
      system: { label: 'Sistema', description: "Segui l'aspetto del sistema operativo" }
    },
    appearance: {
      title: 'Aspetto',
      intro:
        'Preferenze di visualizzazione solo per il desktop. La modalità controlla la luminosità; il tema controlla la palette di accento e lo stile della chat.',
      colorMode: 'Modalità colore',
      colorModeDesc: 'Scegli una modalità fissa o lascia che Nadia segua il sistema.',
      toolViewTitle: 'Visualizzazione chiamate strumento',
      toolViewDesc: 'Prodotto nasconde i payload grezzi degli strumenti; Tecnica mostra input/output completi.',
      translucencyTitle: 'Traslucenza finestra',
      translucencyDesc: 'Mostra il desktop attraverso tutta la finestra. Solo macOS e Windows.',
      embedsTitle: 'Embed inline',
      embedsDesc:
        'Le anteprime ricche si caricano da siti di terze parti (YouTube, X, …). Chiedi mostra un segnaposto finché non autorizzi ciascun servizio; Sempre le carica automaticamente; Disattivato mantiene link semplici.',
      embedsAsk: 'Chiedi',
      embedsAlways: 'Sempre',
      embedsOff: 'Disattivato',
      product: 'Prodotto',
      productDesc: 'Attività degli strumenti leggibile, con riepiloghi concisi.',
      technical: 'Tecnica',
      technicalDesc: 'Include argomenti/risultati grezzi degli strumenti e dettagli di basso livello.',
      themeTitle: 'Tema',
      themeDesc: 'Palette solo desktop. La modalità selezionata viene applicata sopra.',
      installTitle: 'Installa da VS Code',
      installDesc:
        "Incolla l'id di un'estensione Marketplace (es. dracula-theme.theme-dracula) per convertirne il tema colori in una palette desktop.",
      installPlaceholder: 'publisher.extension'
    },
    fieldLabels: FIELD_LABELS,
    fieldDescriptions: FIELD_DESCRIPTIONS
  },

  cron: {
    promptPlaceholder: 'Cosa deve fare ogni volta l’agente?'
  },

  commandCenter: {
    close: 'Chiudi centro comandi',
    paletteTitle: 'Palette comandi',
    back: 'Indietro',
    searchPlaceholder: 'Cerca sessioni, viste e azioni',
    goTo: 'Vai a',
    goToSession: 'Vai alla sessione',
    branches: 'Branch',
    startInBranch: branch => `Nuova conversazione in ${branch}`,
    commandCenter: 'Centro comandi',
    appearance: 'Aspetto',
    settings: 'Impostazioni',
    changeTheme: 'Cambia tema',
    changeColorMode: 'Cambia modalità colore...',
    nav: {
      newChat: { title: 'Nuova sessione', detail: 'Avvia una sessione nuova' },
      settings: { title: 'Impostazioni', detail: 'Configura Nadia Desktop' },
      skills: { title: 'Skill e strumenti', detail: 'Abilita skill, toolset e provider' },
      messaging: { title: 'Messaggistica', detail: 'Configura Telegram, Slack, Discord e altro' },
      artifacts: { title: 'Artefatti', detail: 'Sfoglia gli output generati' }
    }
  }
})
