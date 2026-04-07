import { View, StyleSheet } from 'react-native';
import { ThinkButton } from './ThinkButton';
import { SendButton } from './SendButton';
import type { ComposerState } from './types';

interface Props {
  state: ComposerState;
  thinkActive: boolean;
  onThinkToggle: () => void;
  onSendOrStop: () => void;
}

export function ActionsRow({ state, thinkActive, onThinkToggle, onSendOrStop }: Props) {
  const isWorking =
    state === 'streaming' || state === 'cancelling' || state === 'sending';
  return (
    <View style={styles.row}>
      <ThinkButton
        active={thinkActive}
        onPress={onThinkToggle}
        disabled={isWorking}
      />
      <SendButton state={state} onPress={onSendOrStop} />
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 8,
    height: 36,
  },
});
