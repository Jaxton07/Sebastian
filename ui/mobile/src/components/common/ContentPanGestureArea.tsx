import { PanGestureHandler, State } from 'react-native-gesture-handler';
import { View, StyleSheet } from 'react-native';

const SWIPE_THRESHOLD = 50;

interface Props {
  onOpenLeft?: () => void;
  onOpenRight?: () => void;
  children: React.ReactNode;
}

/**
 * Page-level horizontal pan gesture.
 *
 * Wraps the conversation content area. Detects horizontal pans and opens
 * the left or right sidebar based on direction. Vertical scrolls pass
 * through to child FlatList via failOffsetY.
 *
 * Placed INSIDE the page but OUTSIDE the composer/header, so swipes on the
 * message list trigger sidebars while swipes on the input field do not.
 */
export function ContentPanGestureArea({ onOpenLeft, onOpenRight, children }: Props) {
  function handleState({ nativeEvent }: any) {
    if (nativeEvent.state !== State.END) return;
    const { translationX, velocityX } = nativeEvent;

    if (translationX > SWIPE_THRESHOLD && velocityX >= 0 && onOpenLeft) {
      onOpenLeft();
    } else if (translationX < -SWIPE_THRESHOLD && velocityX <= 0 && onOpenRight) {
      onOpenRight();
    }
  }

  return (
    <PanGestureHandler
      onHandlerStateChange={handleState}
      activeOffsetX={[-10, 10]}
      failOffsetY={[-15, 15]}
    >
      <View style={styles.container}>{children}</View>
    </PanGestureHandler>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
});
