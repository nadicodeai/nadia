import { Box, Text } from '@nadia/ink'

import { HOTKEYS } from '../content/hotkeys.js'
import { t as tr } from '../i18n/index.js'
import type { Theme } from '../theme.js'

const commonCommands = (): [string, string][] => [
  ['/help', tr('helpHint.commands.help')],
  ['/clear', tr('helpHint.commands.clear')],
  ['/resume', tr('helpHint.commands.resume')],
  ['/details', tr('helpHint.commands.details')],
  ['/copy', tr('helpHint.commands.copy')],
  ['/quit', tr('helpHint.commands.quit')]
]

export function HelpHint({ t }: { t: Theme }) {
  const commands = commonCommands()
  const hotkeyPreview = HOTKEYS.slice(0, 8)
  const labelW = Math.max(...commands.map(([k]) => k.length), ...hotkeyPreview.map(([k]) => k.length))

  const pad = (s: string) => s + ' '.repeat(Math.max(0, labelW - s.length + 2))

  return (
    <Box alignItems="flex-start" bottom="100%" flexDirection="column" left={0} position="absolute" right={0}>
      <Box
        alignSelf="flex-start"
        borderColor={t.color.primary}
        borderStyle="round"
        flexDirection="column"
        marginBottom={1}
        opaque
        paddingX={1}
      >
        <Text>
          <Text bold color={t.color.primary}>
            {tr('helpHint.title')}
          </Text>
          <Text color={t.color.muted}>{tr('helpHint.subtitle')}</Text>
        </Text>

        <Box marginTop={1}>
          <Text bold color={t.color.accent}>
            {tr('helpHint.commonCommandsTitle')}
          </Text>
        </Box>

        {commands.map(([k, v]) => (
          <Text key={k}>
            <Text color={t.color.label}>{pad(k)}</Text>
            <Text color={t.color.muted}>{v}</Text>
          </Text>
        ))}

        <Box marginTop={1}>
          <Text bold color={t.color.accent}>
            {tr('helpHint.hotkeysTitle')}
          </Text>
        </Box>

        {hotkeyPreview.map(([k, v]) => (
          <Text key={k}>
            <Text color={t.color.label}>{pad(k)}</Text>
            <Text color={t.color.muted}>{v}</Text>
          </Text>
        ))}
      </Box>
    </Box>
  )
}
