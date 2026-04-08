import { useRef, useEffect } from 'react';
import { Animated, Dimensions, StyleSheet, TouchableOpacity, View } from 'react-native';
import { PanGestureHandler, State } from 'react-native-gesture-handler';
import { useTheme } from '../../theme/ThemeContext';

const SIDEBAR_WIDTH = Dimensions.get('window').width * 0.75;
const SWIPE_THRESHOLD = 50;

type Side = 'left' | 'right';

interface Props {
  visible: boolean;
  onOpen: () => void;
  onClose: () => void;
  children: React.ReactNode;
  side?: Side;
}

export function Sidebar({ visible, onClose, children, side = 'left' }: Props) {
  const colors = useTheme();
  const hiddenX = side === 'left' ? -SIDEBAR_WIDTH : SIDEBAR_WIDTH;
  const translateX = useRef(new Animated.Value(hiddenX)).current;

  useEffect(() => {
    Animated.timing(translateX, {
      toValue: visible ? 0 : hiddenX,
      duration: 250,
      useNativeDriver: true,
    }).start();
  }, [visible, hiddenX]);

  function handleSidebarGesture({ nativeEvent }: any) {
    if (nativeEvent.state !== State.END) return;
    // Close gesture: left sidebar closes on left swipe, right sidebar closes on right swipe
    if (side === 'left' && nativeEvent.translationX < -SWIPE_THRESHOLD) {
      onClose();
    } else if (side === 'right' && nativeEvent.translationX > SWIPE_THRESHOLD) {
      onClose();
    }
  }

  const panelStyle = [
    styles.sidebarBase,
    side === 'left' ? styles.sidebarLeft : styles.sidebarRight,
    {
      transform: [{ translateX }],
      backgroundColor: colors.secondaryBackground,
      shadowOffset: { width: side === 'left' ? 2 : -2, height: 0 },
    },
  ];

  return (
    <View style={[StyleSheet.absoluteFill, { pointerEvents: visible ? 'auto' : 'box-none' }]}>
      <TouchableOpacity
        style={[styles.overlay, { display: visible ? 'flex' : 'none', backgroundColor: colors.overlay }]}
        activeOpacity={1}
        onPress={onClose}
      />
      <PanGestureHandler onHandlerStateChange={handleSidebarGesture} enabled={visible}>
        <Animated.View collapsable={false} style={panelStyle} pointerEvents={visible ? 'auto' : 'none'}>
          {children}
        </Animated.View>
      </PanGestureHandler>
    </View>
  );
}

const styles = StyleSheet.create({
  overlay: { ...StyleSheet.absoluteFillObject },
  sidebarBase: {
    position: 'absolute',
    top: 0,
    bottom: 0,
    width: SIDEBAR_WIDTH,
    shadowColor: '#000',
    shadowOpacity: 0.12,
    shadowRadius: 8,
    elevation: 8,
  },
  sidebarLeft: { left: 0 },
  sidebarRight: { right: 0 },
});
