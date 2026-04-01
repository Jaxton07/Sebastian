import { registerRootComponent } from 'expo';

// Expo Router entry point
// @ts-ignore - expo-router/entry is not typed but works correctly
import App from 'expo-router/entry';

// registerRootComponent calls AppRegistry.registerComponent('main', () => App);
// It also ensures that whether you load the app in Expo Go or in a native build,
// the environment is set up appropriately
registerRootComponent(App);
