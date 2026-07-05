export type Locale = 'en' | 'it'

export type PlaceholderCatalog = readonly [string, string, string, string, string, string, string]

export interface Catalog {
  appLayout: {
    backgroundTaskRunningPlural: string
    backgroundTaskRunningSingular: string
    interruptPlaceholder: string
  }
  helpHint: {
    commands: {
      clear: string
      copy: string
      details: string
      help: string
      quit: string
      resume: string
    }
    commonCommandsTitle: string
    hotkeysTitle: string
    subtitle: string
    title: string
  }
  helpPanel: {
    detailsGlobalDescription: string
    detailsSectionDescription: string
    fortuneDescription: string
    hotkeysTitle: string
    tuiTitle: string
  }
  hotkeys: {
    applyCompletion: string
    completionsQueueHistory: string
    copySelection: string
    copySelectionInterruptClearDraftExit: string
    copySelectionWhenForwarded: string
    deleteToStartEnd: string
    deleteWord: string
    exit: string
    homeEndLine: string
    insertNewline: string
    interpolateShellOutput: string
    interruptClearDraftExit: string
    jumpWord: string
    multilineContinuation: string
    openEditor: string
    openLiveSessionSwitcher: string
    pasteTextAttachImage: string
    redraw: string
    runShellCommand: string
    startEndLine: string
    undoRedo: string
  }
  modelPicker: {
    cancelHint: string
    configureProviderPrefix: string
    currentPrefix: string
    disconnectConfirmHint: string
    disconnecting: string
    disconnectProviderPrefix: string
    emptyKey: string
    errorPrefix: string
    escapeBack: string
    filterPrefix: string
    fullModelIdsHint: string
    failedToSaveKey: string
    invalidOptionsResponse: string
    keyPrompt: string
    keySaveHint: string
    loadingModels: string
    modelCountPlural: string
    modelCountSingular: string
    modelStageHintWithModels: string
    modelStageHintWithoutModels: string
    more: string
    needsSetup: string
    noKey: string
    noModelMatchesFilter: string
    noModelsForProvider: string
    noProvidersAvailable: string
    noProvidersMatch: string
    pasteKeyToActivate: string
    persistGlobal: string
    persistOnly: string
    persistPrefix: string
    persistSession: string
    persistToggle: string
    providerStageHint: string
    runNadiaModelToConfigure: string
    savedCredentialsRemoval: string
    saving: string
    selectModelTitle: string
    selectProviderTitle: string
    typeToFilterSelect: string
    unknown: string
    unknownProvider: string
    reauthenticateLater: string
    warningPrefix: string
  }
  placeholders: PlaceholderCatalog
  setup: {
    actionsTitle: string
    body: string
    exitAction: string
    modelAction: string
    setupAction: string
    title: string
  }
}

type StringLeafPaths<T, Prefix extends string = ''> = {
  [K in keyof T & string]: T[K] extends string
    ? `${Prefix}${K}`
    : T[K] extends readonly string[]
      ? never
      : StringLeafPaths<T[K], `${Prefix}${K}.`>
}[keyof T & string]

export type CatalogKey = StringLeafPaths<Catalog>
