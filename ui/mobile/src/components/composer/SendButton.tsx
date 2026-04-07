import { TouchableOpacity, ActivityIndicator, StyleSheet } from 'react-native';
import { SendIcon, StopCircleIcon } from '../common/Icons';
import { useTheme } from '../../theme/ThemeContext';
import type { ComposerState } from './types';

interface Props {
  state: ComposerState;
  onPress: () => void;
}

export function SendButton({ state, onPress }: Props) {
  const colors = useTheme();
  const isDisabled =
    state === 'idle_empty' || state === 'sending' || state === 'cancelling';
  const bg = state === 'idle_empty' ? '#E5E5EA' : colors.accent;

  return (
    <TouchableOpacity
      style={[styles.btn, { backgroundColor: bg }]}
      onPress={onPress}
      disabled={isDisabled}
      activeOpacity={0.7}
    >
      {state === 'sending' || state === 'cancelling' ? (
        <ActivityIndicator size="small" color="#FFFFFF" />
      ) : state === 'streaming' ? (
        <StopCircleIcon size={18} color="#FFFFFF" />
      ) : (
        <SendIcon size={18} color="#FFFFFF" />
      )}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  btn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
