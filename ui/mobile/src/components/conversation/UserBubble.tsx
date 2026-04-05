import { View, Text, StyleSheet } from 'react-native';

interface Props {
  content: string;
}

export function UserBubble({ content }: Props) {
  return (
    <View style={styles.row}>
      <View style={styles.bubble}>
        <Text style={styles.text}>{content}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    paddingHorizontal: 16,
    paddingVertical: 6,
    alignItems: 'flex-end',
  },
  bubble: {
    maxWidth: '75%',
    backgroundColor: '#7c6af5',
    borderRadius: 18,
    borderBottomRightRadius: 4,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  text: {
    color: '#ffffff',
    fontSize: 15,
    lineHeight: 21,
  },
});
